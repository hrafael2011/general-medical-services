"""Copy doctor config + catalogs + calendar from PROD to STAGING (fake names/WhatsApp).

Usage:
    PROD_DATABASE_URL=postgresql://... STAGING_DATABASE_URL=postgresql://... \
      python backend/scripts/seed_fake_doctors.py

What it copies:
    1. Catalogs: ranks, departments, service_areas, service_inactive_reasons
    2. Doctors: same sex/rank/dept/active/limits/areas → fake names + WhatsApp
    3. Calendar: versions + assignments (doctor IDs remapped to new fake doctors)

Staging data is wiped before insert. PROD is never modified.
"""

import os
import random
import sys
import uuid
from datetime import UTC, datetime

from sqlalchemy import create_engine, text

# ---------------------------------------------------------------------------
# Fake data pools
# ---------------------------------------------------------------------------

MALE_FIRST = [
    "Carlos", "Manuel", "Rafael", "Antonio", "Francisco",
    "Miguel", "Ramón", "Daniel", "Alejandro", "Fernando",
    "Luis", "Pedro", "Jorge", "Andrés", "Roberto",
    "Felipe", "Ricardo", "Eduardo", "Alberto", "Gabriel",
    "Samuel", "Enrique", "Víctor", "Héctor", "Cristian",
]

FEMALE_FIRST = [
    "María", "Carmen", "Ana", "Laura", "Isabel",
    "Rosa", "Teresa", "Elena", "Patricia", "Claudia",
    "Diana", "Katherine", "Paola", "Carolina", "Gabriela",
    "Sofía", "Valentina", "Lucía", "Andrea", "Natalia",
    "Victoria", "Julia", "Daniela", "Camila", "Adriana",
]

LAST_NAMES = [
    "García", "Rodríguez", "Martínez", "Hernández", "López",
    "González", "Pérez", "Sánchez", "Ramírez", "Cruz",
    "Jiménez", "Reyes", "Morales", "Ortiz", "Castillo",
    "Vargas", "Mejía", "Peña", "Guzmán", "Fernández",
    "Torres", "Núñez", "Santos", "Rivas", "Méndez",
    "Medina", "Díaz", "Flores", "Rivera", "Peralta",
]


def fake_phone() -> str:
    prefix = random.choice(["809", "829", "849"])
    suffix = "".join(str(random.randint(1, 9)) for _ in range(7))
    return f"+1{prefix}{suffix}"


def fake_name(sex: str) -> str:
    first = random.choice(MALE_FIRST if sex == "M" else FEMALE_FIRST)
    last1 = random.choice(LAST_NAMES)
    last2 = random.choice(LAST_NAMES)
    return f"{first} {last1} {last2}"


# Tables to mirror from PROD (no FK dependencies on doctors)
CATALOG_TABLES = [
    "ranks",
    "departments",
    "service_areas",
    "service_inactive_reasons",
]

# Tables that reference doctors via doctor_id → need ID remapping
DOCTOR_DEPENDENT_TABLES = [
    # (table, fk_column)
    ("calendar_assignments", "doctor_id"),
    ("mission_participants", "doctor_id"),
]


def copy_table(prod_sess, stage_sess, table: str) -> int:
    """Copy all rows from prod to staging. Returns row count."""
    rows = prod_sess.execute(text(f"SELECT * FROM {table}")).mappings().all()
    if not rows:
        return 0
    stage_sess.execute(text(f"DELETE FROM {table}"))
    for row in rows:
        columns = ", ".join(row.keys())
        placeholders = ", ".join(f":{k}" for k in row.keys())
        stage_sess.execute(
            text(f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"),
            dict(row),
        )
    return len(rows)


def main() -> None:
    prod_url = os.environ.get("PROD_DATABASE_URL")
    staging_url = os.environ.get("STAGING_DATABASE_URL")

    if not prod_url or not staging_url:
        print("Usage:")
        print("  PROD_DATABASE_URL=... STAGING_DATABASE_URL=... python seed_fake_doctors.py")
        sys.exit(1)

    prod_engine = create_engine(prod_url)
    staging_engine = create_engine(staging_url)
    ProdSession = locals()  # placeholder, override below

    with prod_engine.connect() as prod_conn, staging_engine.connect() as stage_conn:
        # Wrap in a transaction on staging
        trans = stage_conn.begin()

        # =================================================================
        # 1. CATALOGS
        # =================================================================
        print("=" * 60)
        print("1. CATALOGS")
        for table in CATALOG_TABLES:
            rows = prod_conn.execute(
                text(f"SELECT * FROM {table}")
            ).mappings().all()
            if not rows:
                print(f"  {table}: 0 rows (skipped)")
                continue
            stage_conn.execute(text(f"DELETE FROM {table}"))
            for row in rows:
                cols = ", ".join(row.keys())
                ph = ", ".join(f":{k}" for k in row.keys())
                stage_conn.execute(text(f"INSERT INTO {table} ({cols}) VALUES ({ph})"), dict(row))
            print(f"  {table}: {len(rows)} rows copied")

        # =================================================================
        # 2. DOCTORS (fake names + WhatsApp)
        # =================================================================
        print("=" * 60)
        print("2. DOCTORS")

        prod_doctors = prod_conn.execute(
            text("""
                SELECT * FROM doctors WHERE deleted_at IS NULL ORDER BY name
            """)
        ).mappings().all()

        print(f"  PROD doctors: {len(prod_doctors)}")

        active = sum(1 for d in prod_doctors if d["active"])
        svc_active = sum(1 for d in prod_doctors if d["service_active"])
        male = sum(1 for d in prod_doctors if d["sex"] == "M")
        female = sum(1 for d in prod_doctors if d["sex"] == "F")
        print(f"  Active: {active} | Inactive: {len(prod_doctors) - active}")
        print(f"  Service-active: {svc_active}")
        print(f"  Male: {male} | Female: {female}")

        # Wipe staging doctors
        stage_conn.execute(text("DELETE FROM doctors"))

        now = datetime.now(UTC)
        used_names: set[str] = set()
        doctor_id_map: dict[str, str] = {}  # old_id → new_id

        for d in prod_doctors:
            sex = d["sex"] or "M"
            while True:
                name = fake_name(sex)
                if name not in used_names:
                    used_names.add(name)
                    break

            parts = name.split()
            first_name = parts[0]
            last_name = " ".join(parts[1:])
            new_id = str(uuid.uuid4())
            doctor_id_map[d["id"]] = new_id

            stage_conn.execute(
                text("""
                    INSERT INTO doctors (
                        id, first_name, last_name, name, normalized_name, sex,
                        rank_id, department_id, notes,
                        active, service_active,
                        service_inactive_reason_id, service_inactive_detail,
                        participa_misiones,
                        whatsapp_phone,
                        monthly_service_target, monthly_service_max,
                        monthly_service_limit_mode, availability_mode,
                        allowed_area_ids,
                        created_by, created_at, updated_at
                    ) VALUES (
                        :id, :first_name, :last_name, :name, :normalized_name, :sex,
                        :rank_id, :department_id, :notes,
                        :active, :service_active,
                        :service_inactive_reason_id, :service_inactive_detail,
                        :participa_misiones,
                        :whatsapp_phone,
                        :monthly_service_target, :monthly_service_max,
                        :monthly_service_limit_mode, :availability_mode,
                        :allowed_area_ids,
                        NULL, :created_at, :created_at
                    )
                """),
                {
                    "id": new_id,
                    "first_name": first_name,
                    "last_name": last_name,
                    "name": name,
                    "normalized_name": name.lower(),
                    "sex": sex,
                    "rank_id": d["rank_id"],
                    "department_id": d["department_id"],
                    "notes": d["notes"],
                    "active": d["active"],
                    "service_active": d["service_active"],
                    "service_inactive_reason_id": d["service_inactive_reason_id"],
                    "service_inactive_detail": d["service_inactive_detail"],
                    "participa_misiones": d["participa_misiones"],
                    "whatsapp_phone": fake_phone(),
                    "monthly_service_target": d["monthly_service_target"],
                    "monthly_service_max": d["monthly_service_max"],
                    "monthly_service_limit_mode": d["monthly_service_limit_mode"],
                    "availability_mode": d["availability_mode"],
                    "allowed_area_ids": d["allowed_area_ids"] or [],
                    "created_at": now,
                },
            )

        print(f"  Inserted: {len(doctor_id_map)} fake doctors")

        # =================================================================
        # 3. CALENDAR (versions + assignments with remapped doctor IDs)
        # =================================================================
        print("=" * 60)
        print("3. CALENDAR")

        # 3a. Calendar versions
        versions = prod_conn.execute(
            text("SELECT * FROM calendar_versions")
        ).mappings().all()

        if versions:
            stage_conn.execute(text("DELETE FROM calendar_versions"))
            for v in versions:
                cols = ", ".join(v.keys())
                ph = ", ".join(f":{k}" for k in v.keys())
                stage_conn.execute(
                    text(f"INSERT INTO calendar_versions ({cols}) VALUES ({ph})"),
                    dict(v),
                )
            print(f"  calendar_versions: {len(versions)} rows copied")

        # 3b. Calendar assignments (remap doctor_id)
        assignments = prod_conn.execute(
            text("SELECT * FROM calendar_assignments")
        ).mappings().all()

        if assignments:
            stage_conn.execute(text("DELETE FROM calendar_assignments"))
            copied = 0
            for a in assignments:
                old_doc_id = a["doctor_id"]
                new_doc_id = doctor_id_map.get(old_doc_id)
                if new_doc_id is None:
                    continue  # doctor not found, skip assignment
                data = dict(a)
                data["doctor_id"] = new_doc_id
                cols = ", ".join(data.keys())
                ph = ", ".join(f":{k}" for k in data.keys())
                stage_conn.execute(
                    text(f"INSERT INTO calendar_assignments ({cols}) VALUES ({ph})"),
                    data,
                )
                copied += 1
            print(f"  calendar_assignments: {copied}/{len(assignments)} rows copied (skipped {len(assignments) - copied} with missing doctors)")

        # =================================================================
        # 4. MISSION PARTICIPANTS (remap doctor_id)
        # =================================================================
        print("=" * 60)
        print("4. MISSION PARTICIPANTS")

        participants = prod_conn.execute(
            text("SELECT * FROM mission_participants")
        ).mappings().all()

        if participants:
            stage_conn.execute(text("DELETE FROM mission_participants"))
            copied = 0
            for p in participants:
                old_doc_id = p["doctor_id"]
                new_doc_id = doctor_id_map.get(old_doc_id)
                if new_doc_id is None:
                    continue
                data = dict(p)
                data["doctor_id"] = new_doc_id
                cols = ", ".join(data.keys())
                ph = ", ".join(f":{k}" for k in data.keys())
                stage_conn.execute(
                    text(f"INSERT INTO mission_participants ({cols}) VALUES ({ph})"),
                    data,
                )
                copied += 1
            print(f"  mission_participants: {copied}/{len(participants)} rows copied (skipped {len(participants) - copied} with missing doctors)")
        else:
            print("  mission_participants: 0 rows (skipped)")

        trans.commit()
        print("=" * 60)
        print("DONE — all data copied to staging with fake names/WhatsApp.")


if __name__ == "__main__":
    main()
