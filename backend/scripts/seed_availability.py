#!/usr/bin/env python3
"""Seed weekly availability for all service-active doctors.

Usage:
  cd /path/to/project/root
  python backend/scripts/seed_availability.py
"""
import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

DATABASE_URL = "postgresql+psycopg://postgres:postgres@localhost:5433/medical_shifts"

# Distribute doctors across weekdays to ensure calendar coverage
DAY_PATTERNS = [
    [0, 1, 2],         # Mon–Wed
    [3, 4, 5],         # Thu–Sat
    [0, 2, 4],         # Mon, Wed, Fri
    [1, 3, 5],         # Tue, Thu, Sat
    [0, 1],            # Mon–Tue
    [2, 3],            # Wed–Thu
    [4, 5],            # Fri–Sat
    [5, 6, 0],         # Sat–Mon
    [1, 2, 3, 4],      # Tue–Fri
    [3, 4],            # Thu–Fri
    [0, 3, 6],         # Mon, Thu, Sun
    [2, 5],            # Wed, Sat
    [1, 4],            # Tue, Fri
    [0, 1, 2, 3, 4, 5, 6],  # All days
    [1, 2, 3],         # Tue–Thu
    [4, 5, 6],         # Fri–Sun
]


def main() -> None:
    engine = create_engine(DATABASE_URL)
    with Session(engine) as session:
        from sqlalchemy import text

        # Fetch service-active doctors
        rows = session.execute(
            text(
                "SELECT id, name FROM doctors WHERE active = true AND service_active = true "
                "ORDER BY name"
            )
        ).all()
        print(f"Found {len(rows)} service-active doctors")

        updated = 0
        for i, row in enumerate(rows):
            doctor_id = row[0]
            doctor_name = row[1]
            days = DAY_PATTERNS[i % len(DAY_PATTERNS)]

            # Set availability_mode = 'fixed'
            session.execute(
                text("UPDATE doctors SET availability_mode = 'fixed', updated_at = :now WHERE id = :id"),
                {"now": datetime.now(timezone.utc), "id": doctor_id},
            )

            # Delete any existing weekly_fixed records for this doctor
            session.execute(
                text(
                    "DELETE FROM doctor_availability "
                    "WHERE doctor_id = :id AND availability_type = 'weekly_fixed'"
                ),
                {"id": doctor_id},
            )

            # Insert new availability record
            now = datetime.now(timezone.utc)
            session.execute(
                text(
                    "INSERT INTO doctor_availability "
                    "(id, doctor_id, availability_type, days_of_week, available_dates, "
                    " weekday, week_number, year, month, submitted_at, "
                    " effective_from, effective_to, source, review_status, "
                    " created_by, created_at, updated_at) "
                    "VALUES (:id, :doctor_id, :av_type, :days, :av_dates, "
                    " :weekday, :week_number, :year, :month, :submitted_at, "
                    " :eff_from, :eff_to, :source, :review_status, "
                    " :created_by, :created_at, :updated_at)"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "doctor_id": doctor_id,
                    "av_type": "weekly_fixed",
                    "days": json.dumps(days),
                    "av_dates": None,
                    "weekday": None,
                    "week_number": None,
                    "year": None,
                    "month": None,
                    "submitted_at": None,
                    "eff_from": None,
                    "eff_to": None,
                    "source": "manual",
                    "review_status": "approved",
                    "created_by": "seed-script",
                    "created_at": now,
                    "updated_at": now,
                },
            )
            print(f"  {doctor_name}: days={days}")
            updated += 1

        session.commit()
        print(f"\nDone. Updated {updated} doctors with weekly availability.")


if __name__ == "__main__":
    main()
