"""POST /api/admin/seed-staging — seed staging with demo data.

Two modes:
  * copy    — copy + anonymize from PROD (original behaviour, fixed)
  * generate— create synthetic doctors, catalogs and calendar from scratch

Only works in staging.
"""

import logging
import random
import uuid
from datetime import UTC, date, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from backend.app.api.dependencies import require_admin
from backend.app.core.config import settings
from backend.app.infrastructure.db.models.user import UserModel
from backend.app.infrastructure.db.session import get_db_session

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])

PROD_DATABASE_URL = "postgresql+psycopg://postgres:cHmyJqHczfWxhwVDLPmDqfHFJJZLRyQU@postgres.railway.internal:5432/railway"

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

SYNTHETIC_RANKS = [
    ("Cabo", "cabo", "CBO"),
    ("Sargento", "sargento", "SGT"),
    ("Sargento Mayor", "sargento mayor", "SGM"),
    ("Contrata", "contrata", "CTR"),
    ("Pasante", "pasante", "PST"),
]

SYNTHETIC_DEPARTMENTS = [
    ("Recursos Humanos", "recursos humanos"),
    ("Licencias Médicas", "licencias medicas"),
    ("Medicina General", "medicina general"),
    ("Cirugía", "cirugia"),
    ("Pediatría", "pediatria"),
    ("Ortopedia", "ortopedia"),
    ("Cardiología", "cardiologia"),
    ("Neurología", "neurologia"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_phone() -> str:
    prefix = random.choice(["809", "829", "849"])
    suffix = "".join(str(random.randint(1, 9)) for _ in range(7))
    return f"+1{prefix}{suffix}"


def _fake_name(sex: str) -> str:
    first = random.choice(MALE_FIRST if sex == "M" else FEMALE_FIRST)
    last1 = random.choice(LAST_NAMES)
    last2 = random.choice(LAST_NAMES)
    return f"{first} {last1} {last2}"


# ---------------------------------------------------------------------------
# Response schema
# ---------------------------------------------------------------------------

class SeedResult(BaseModel):
    mode: str
    doctors_created: int
    doctors_copied: int = 0
    active: int = 0
    inactive: int = 0
    male: int = 0
    female: int = 0
    service_active: int = 0
    ranks: int = 0
    departments: int = 0
    service_areas: int = 0
    service_inactive_reasons: int = 0
    calendar_versions: int = 0
    calendar_assignments: int = 0
    mission_participants: int = 0


# ---------------------------------------------------------------------------
# COPY mode (original behaviour, fixed)
# ---------------------------------------------------------------------------

CATALOG_TABLES = [
    "ranks",
    "departments",
    "service_areas",
    "service_inactive_reasons",
]


def _seed_from_production(session: Session) -> SeedResult:
    prod_engine = create_engine(PROD_DATABASE_URL, connect_args={"connect_timeout": 10})

    try:
        with prod_engine.connect() as prod:
            pass  # connectivity tested by caller
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cannot connect to PROD: {e}")

    try:
        with prod_engine.connect() as prod:
            # === 1. CATALOGS ===
            catalog_counts: dict[str, int] = {}
            for table in CATALOG_TABLES:
                rows = prod.execute(text(f"SELECT * FROM {table}")).mappings().all()
                if not rows:
                    catalog_counts[table] = 0
                    continue
                session.execute(text(f"DELETE FROM {table}"))
                for row in rows:
                    cols = ", ".join(row.keys())
                    ph = ", ".join(f":{k}" for k in row.keys())
                    session.execute(text(f"INSERT INTO {table} ({cols}) VALUES ({ph})"), dict(row))
                catalog_counts[table] = len(rows)

            # === 2. DOCTORS ===
            prod_doctors = prod.execute(
                text("SELECT * FROM doctors WHERE deleted_at IS NULL ORDER BY name")
            ).mappings().all()

            active = sum(1 for d in prod_doctors if d["active"])
            inactive = len(prod_doctors) - active
            male = sum(1 for d in prod_doctors if d["sex"] == "M")
            female = sum(1 for d in prod_doctors if d["sex"] == "F")
            svc_active = sum(1 for d in prod_doctors if d["service_active"])

            session.execute(text("DELETE FROM doctors"))
            session.execute(text("DELETE FROM doctor_allowed_areas"))
            now = datetime.now(UTC)
            used_names: set[str] = set()
            doctor_id_map: dict[str, str] = {}

            for d in prod_doctors:
                sex = d["sex"] or "M"
                while True:
                    name = _fake_name(sex)
                    if name not in used_names:
                        used_names.add(name)
                        break

                parts = name.split()
                first_name = parts[0]
                last_name = " ".join(parts[1:])
                new_id = str(uuid.uuid4())
                doctor_id_map[d["id"]] = new_id

                session.execute(
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
                            created_at, updated_at
                        ) VALUES (
                            :id, :fn, :ln, :name, :nn, :sex,
                            :rank_id, :dept_id, :notes,
                            :active, :svc_active,
                            :reason_id, :reason_detail,
                            :participa,
                            :wp,
                            :mst, :msm, :mslm, :am,
                            :now, :now
                        )
                    """),
                    {
                        "id": new_id, "fn": first_name, "ln": last_name,
                        "name": name, "nn": name.lower(), "sex": sex,
                        "rank_id": d["rank_id"], "dept_id": d["department_id"],
                        "notes": d["notes"], "active": d["active"],
                        "svc_active": d["service_active"],
                        "reason_id": d["service_inactive_reason_id"],
                        "reason_detail": d["service_inactive_detail"],
                        "participa": d["participa_misiones"],
                        "wp": _fake_phone(),
                        "mst": d["monthly_service_target"],
                        "msm": d["monthly_service_max"],
                        "mslm": d["monthly_service_limit_mode"],
                        "am": d["availability_mode"],
                        "now": now,
                    },
                )

                # Copy allowed areas via junction table (bug fix)
                area_ids = d.get("allowed_area_ids") or []
                if area_ids:
                    for area_id in area_ids:
                        session.execute(
                            text("""
                                INSERT INTO doctor_allowed_areas (doctor_id, service_area_id)
                                VALUES (:doc_id, :area_id)
                                ON CONFLICT DO NOTHING
                            """),
                            {"doc_id": new_id, "area_id": area_id},
                        )

            # === 3. CALENDAR ===
            versions = prod.execute(text("SELECT * FROM calendar_versions")).mappings().all()
            if versions:
                session.execute(text("DELETE FROM calendar_versions"))
                for v in versions:
                    cols = ", ".join(v.keys())
                    ph = ", ".join(f":{k}" for k in v.keys())
                    session.execute(text(f"INSERT INTO calendar_versions ({cols}) VALUES ({ph})"), dict(v))

            assignments = prod.execute(
                text("SELECT * FROM calendar_assignments")
            ).mappings().all()
            assignments_copied = 0
            if assignments:
                session.execute(text("DELETE FROM calendar_assignments"))
                for a in assignments:
                    new_doc_id = doctor_id_map.get(a["doctor_id"])
                    if new_doc_id is None:
                        continue
                    data = dict(a)
                    data["doctor_id"] = new_doc_id
                    cols = ", ".join(data.keys())
                    ph = ", ".join(f":{k}" for k in data.keys())
                    session.execute(text(f"INSERT INTO calendar_assignments ({cols}) VALUES ({ph})"), data)
                    assignments_copied += 1

            # === 4. MISSION PARTICIPANTS ===
            participants = prod.execute(
                text("SELECT * FROM mission_participants")
            ).mappings().all()
            participants_copied = 0
            if participants:
                session.execute(text("DELETE FROM mission_participants"))
                for p in participants:
                    new_doc_id = doctor_id_map.get(p["doctor_id"])
                    if new_doc_id is None:
                        continue
                    data = dict(p)
                    data["doctor_id"] = new_doc_id
                    cols = ", ".join(data.keys())
                    ph = ", ".join(f":{k}" for k in data.keys())
                    session.execute(text(f"INSERT INTO mission_participants ({cols}) VALUES ({ph})"), data)
                    participants_copied += 1

            session.commit()
    except Exception:
        session.rollback()
        logger.exception("Seed from production failed")
        raise HTTPException(status_code=500, detail="Seed failed — check logs")

    return SeedResult(
        mode="copy",
        doctors_copied=len(prod_doctors),
        active=active,
        inactive=inactive,
        male=male,
        female=female,
        service_active=svc_active,
        ranks=catalog_counts.get("ranks", 0),
        departments=catalog_counts.get("departments", 0),
        service_areas=catalog_counts.get("service_areas", 0),
        service_inactive_reasons=catalog_counts.get("service_inactive_reasons", 0),
        calendar_versions=len(versions),
        calendar_assignments=assignments_copied,
        mission_participants=participants_copied,
    )


# ---------------------------------------------------------------------------
# GENERATE mode (synthetic data from scratch)
# ---------------------------------------------------------------------------

def _seed_synthetic(
    session: Session,
    doctor_count: int = 42,
    year: int = 2026,
    month: int = 6,
) -> SeedResult:
    now = datetime.now(UTC)

    try:
        # === 1. CATALOGS ===
        session.execute(text("DELETE FROM doctor_allowed_areas"))
        session.execute(text("DELETE FROM calendar_assignments"))
        session.execute(text("DELETE FROM calendar_versions"))
        session.execute(text("DELETE FROM calendars"))
        session.execute(text("DELETE FROM doctors"))
        session.execute(text("DELETE FROM departments"))
        session.execute(text("DELETE FROM ranks"))

        # Ranks
        rank_ids: list[str] = []
        for name, normalized, abbrev in SYNTHETIC_RANKS:
            rid = str(uuid.uuid4())
            rank_ids.append(rid)
            session.execute(
                text("""
                    INSERT INTO ranks (id, name, normalized_name, abbreviation, active, created_at, updated_at)
                    VALUES (:id, :name, :nn, :abbr, true, :now, :now)
                """),
                {"id": rid, "name": name, "nn": normalized, "abbr": abbrev, "now": now},
            )

        # Departments
        dept_ids: list[str] = []
        for name, normalized in SYNTHETIC_DEPARTMENTS:
            did = str(uuid.uuid4())
            dept_ids.append(did)
            session.execute(
                text("""
                    INSERT INTO departments (id, name, normalized_name, active, created_at, updated_at)
                    VALUES (:id, :name, :nn, true, :now, :now)
                """),
                {"id": did, "name": name, "nn": normalized, "now": now},
            )

        # Service areas (assumed pre-seeded by migration, but count them)
        area_rows = session.execute(
            text("SELECT id FROM service_areas WHERE active = 1")
        ).mappings().all()
        area_ids = [r["id"] for r in area_rows]

        # === 2. DOCTORS ===
        used_names: set[str] = set()
        doctor_ids: list[str] = []
        male_count = 0
        female_count = 0

        for _ in range(doctor_count):
            sex = random.choice(["M", "F"])
            while True:
                name = _fake_name(sex)
                if name not in used_names:
                    used_names.add(name)
                    break

            if sex == "M":
                male_count += 1
            else:
                female_count += 1

            parts = name.split()
            first_name = parts[0]
            last_name = " ".join(parts[1:])
            doc_id = str(uuid.uuid4())
            doctor_ids.append(doc_id)

            session.execute(
                text("""
                    INSERT INTO doctors (
                        id, first_name, last_name, name, normalized_name, sex,
                        rank_id, department_id, notes,
                        active, service_active, service_inactive_reason_id, service_inactive_detail,
                        participa_misiones, whatsapp_phone,
                        monthly_service_target, monthly_service_max, monthly_service_limit_mode,
                        availability_mode, created_at, updated_at
                    ) VALUES (
                        :id, :fn, :ln, :name, :nn, :sex,
                        :rank_id, :dept_id, :notes,
                        true, true, null, null,
                        true, :wp,
                        3, 3, 'warn_only',
                        :am, :now, :now
                    )
                """),
                {
                    "id": doc_id, "fn": first_name, "ln": last_name,
                    "name": name, "nn": name.lower(), "sex": sex,
                    "rank_id": random.choice(rank_ids),
                    "dept_id": random.choice(dept_ids),
                    "notes": None,
                    "wp": _fake_phone(),
                    "am": random.choice(["monthly", "fixed"]),
                    "now": now,
                },
            )

            # Assign 1-3 allowed areas
            assigned_areas = random.sample(area_ids, k=min(random.randint(1, 3), len(area_ids)))
            for area_id in assigned_areas:
                session.execute(
                    text("""
                        INSERT INTO doctor_allowed_areas (doctor_id, service_area_id)
                        VALUES (:doc_id, :area_id)
                        ON CONFLICT DO NOTHING
                    """),
                    {"doc_id": doc_id, "area_id": area_id},
                )

        # === 3. CALENDAR ===
        cal_id = str(uuid.uuid4())
        session.execute(
            text("""
                INSERT INTO calendars (id, year, month, status, generation_mode, created_at, updated_at)
                VALUES (:id, :year, :month, 'draft', 'manual', :now, :now)
            """),
            {"id": cal_id, "year": year, "month": month, "now": now},
        )

        ver_id = str(uuid.uuid4())
        session.execute(
            text("""
                INSERT INTO calendar_versions (
                    id, calendar_id, version_number, status, created_at
                ) VALUES (:id, :cal_id, 1, 'draft', :now)
            """),
            {"id": ver_id, "cal_id": cal_id, "now": now},
        )

        # === 4. ASSIGNMENTS (1 per doctor) ===
        # Pick distinct days in the month, cycling if more doctors than days
        days_in_month = 30  # June has 30 days
        for idx, doc_id in enumerate(doctor_ids):
            day = (idx % days_in_month) + 1
            area_id = random.choice(area_ids)
            session.execute(
                text("""
                    INSERT INTO calendar_assignments (
                        id, calendar_version_id, service_date, service_area_id,
                        doctor_id, assignment_source, created_at
                    ) VALUES (
                        :id, :ver_id, :svc_date, :area_id,
                        :doc_id, 'manual', :now
                    )
                """),
                {
                    "id": str(uuid.uuid4()),
                    "ver_id": ver_id,
                    "svc_date": date(year, month, day),
                    "area_id": area_id,
                    "doc_id": doc_id,
                    "now": now,
                },
            )

        session.commit()
    except Exception:
        session.rollback()
        logger.exception("Synthetic seed failed")
        raise HTTPException(status_code=500, detail="Synthetic seed failed — check logs")

    return SeedResult(
        mode="generate",
        doctors_created=doctor_count,
        male=male_count,
        female=female_count,
        ranks=len(SYNTHETIC_RANKS),
        departments=len(SYNTHETIC_DEPARTMENTS),
        service_areas=len(area_ids),
        calendar_versions=1,
        calendar_assignments=doctor_count,
    )


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post("/seed-staging", response_model=SeedResult)
def seed_staging(
    mode: Annotated[Literal["copy", "generate"], Query(description="copy=from PROD, generate=synthetic")] = "copy",
    doctor_count: Annotated[int, Query(ge=1, le=500)] = 42,
    year: Annotated[int, Query(ge=2024, le=2030)] = 2026,
    month: Annotated[int, Query(ge=1, le=12)] = 6,
    _current_user: Annotated[UserModel, Depends(require_admin)] = None,
    session: Annotated[Session, Depends(get_db_session)] = None,
) -> SeedResult:
    """Seed staging database with demo data.

    * **copy** — copies anonymized doctors + catalogs + calendar from PROD.
    * **generate** — creates synthetic doctors, ranks, departments and 1 calendar assignment per doctor.
    """
    if settings.app_env != "staging":
        raise HTTPException(status_code=403, detail="Only available in staging")

    if mode == "copy":
        return _seed_from_production(session)
    return _seed_synthetic(session, doctor_count=doctor_count, year=year, month=month)


@router.post("/cleanup-soft-deleted-calendars")
def cleanup_soft_deleted_calendars(
    session: Annotated[Session, Depends(get_db_session)] = None,
):
    """Hard-delete all soft-deleted calendars and their related data."""
    if settings.app_env != "staging":
        raise HTTPException(status_code=403, detail="Only available in staging")

    from backend.app.infrastructure.repositories.calendars import CalendarRepository

    repo = CalendarRepository(session)
    deleted = repo.list_deleted_calendars()

    if not deleted:
        return {"deleted": 0, "entries": []}

    entries = []
    for c in deleted:
        entries.append({"id": c.id, "year": c.year, "month": c.month})
        repo.hard_delete_calendar(c.id)

    session.commit()
    return {"deleted": len(entries), "entries": entries}
