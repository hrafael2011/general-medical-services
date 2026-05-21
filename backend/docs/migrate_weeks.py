"""
Create missing weeks for calendar versions that have assignments but no weeks.
Also applies the corrected compute_weeks logic.

Usage: python -m backend.docs.migrate_weeks
"""

import sys
import uuid
from datetime import date, datetime, UTC

sys.path.insert(0, "/home/hendrick-rafael/Desktop/Proyectos Oficiales/Turnos medicos system")

from sqlalchemy import create_engine, text
from backend.app.core.config import settings
from backend.app.domain.calendars.weeks import compute_weeks

engine = create_engine(settings.database_url)

def ensure_weeks_for_version(conn, version_id: str, cal_id: str, year: int, month: int):
    """Create weeks for a version if it doesn't have them yet."""
    # Check if weeks already exist for this version
    existing = conn.execute(
        text("SELECT COUNT(*) FROM calendar_weeks WHERE calendar_version_id = :vid"),
        {"vid": version_id},
    ).scalar()

    if existing > 0:
        # Already has weeks, skip (we handled updates separately)
        return False

    # Generate weeks using corrected logic
    weeks = compute_weeks(year, month)

    for w in weeks:
        week_id = str(uuid.uuid4())
        conn.execute(
            text("""
                INSERT INTO calendar_weeks
                    (id, calendar_id, calendar_version_id, week_number, label,
                     start_date, end_date, status, created_at, updated_at)
                VALUES
                    (:id, :cal_id, :vid, :wnum, :label,
                     :sdate, :edate, 'draft', :now, :now)
            """),
            {
                "id": week_id,
                "cal_id": cal_id,
                "vid": version_id,
                "wnum": w[0],
                "label": w[1],
                "sdate": date(w[2], w[3], w[4]),
                "edate": date(w[5], w[6], w[7]),
                "now": datetime.now(UTC),
            },
        )

    return True


def link_assignments(conn, version_id: str):
    """Link assignments to the correct week by service_date."""
    result = conn.execute(
        text("""
            UPDATE calendar_assignments a
            SET calendar_week_id = w.id
            FROM calendar_weeks w
            WHERE a.calendar_version_id = :vid
              AND a.calendar_version_id = w.calendar_version_id
              AND a.calendar_week_id IS NULL
              AND a.service_date >= w.start_date
              AND a.service_date <= w.end_date
        """),
        {"vid": version_id},
    )
    return result.rowcount


def main():
    with engine.begin() as conn:
        # Get all versions that have assignments
        versions = conn.execute(
            text("""
                SELECT DISTINCT v.id as version_id, c.id as cal_id, c.year, c.month,
                       COUNT(a.id) OVER (PARTITION BY v.id) as assign_count
                FROM calendar_assignments a
                JOIN calendar_versions v ON a.calendar_version_id = v.id
                JOIN calendars c ON v.calendar_id = c.id
                ORDER BY c.year, c.month, v.id
            """)
        ).all()

        created = 0
        linked = 0

        for row in versions:
            vid, cid, yr, mo = row.version_id, row.cal_id, row.year, row.month

            did_create = ensure_weeks_for_version(conn, vid, cid, yr, mo)
            if did_create:
                created += 1
                print(f"  Created weeks for version {vid[:8]} (cal {cid[:8]}, {yr}-{mo:02d})")

            # Link assignments to weeks
            n = link_assignments(conn, vid)
            if n > 0:
                linked += n

        print(f"\nSummary: weeks created for {created} versions, {linked} assignments linked")


if __name__ == "__main__":
    main()
