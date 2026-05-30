"""TEMPORARY: POST /api/admin/seed-staging — copy PROD doctors → STAGING (anonymized).

Only works in staging. Production DB is READ-ONLY (SELECT only).
Delete this file after use.
"""

import logging
import random
import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from backend.app.api.dependencies import require_admin
from backend.app.core.config import settings
from backend.app.infrastructure.db.models.user import UserModel
from backend.app.infrastructure.db.session import get_db_session

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])

PROD_DATABASE_URL = "postgresql+psycopg://postgres:cHmyJqHczfWxhwVDLPmDqfHFJJZLRyQU@postgres.railway.internal:5432/railway"

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

CATALOG_TABLES = [
    "ranks",
    "departments",
    "service_areas",
    "service_inactive_reasons",
]


def _fake_phone() -> str:
    prefix = random.choice(["809", "829", "849"])
    suffix = "".join(str(random.randint(1, 9)) for _ in range(7))
    return f"+1{prefix}{suffix}"


def _fake_name(sex: str) -> str:
    first = random.choice(MALE_FIRST if sex == "M" else FEMALE_FIRST)
    last1 = random.choice(LAST_NAMES)
    last2 = random.choice(LAST_NAMES)
    return f"{first} {last1} {last2}"


class SeedResult(BaseModel):
    doctors_copied: int
    active: int
    inactive: int
    male: int
    female: int
    service_active: int
    ranks: int
    departments: int
    service_areas: int
    service_inactive_reasons: int
    calendar_versions: int
    calendar_assignments: int
    mission_participants: int


@router.post("/seed-staging", response_model=SeedResult)
def seed_staging_from_production(
    _current_user: Annotated[UserModel, Depends(require_admin)],
    session: Annotated[Session, Depends(get_db_session)],
) -> SeedResult:
    """Copy doctors + catalogs + calendar from PROD to STAGING with fake names/WhatsApp.

    PROD is read-only (SELECT). All writes go to STAGING.
    Only runs when APP_ENV=staging.
    """
    if settings.app_env != "staging":
        raise HTTPException(status_code=403, detail="Only available in staging")

    prod_engine = create_engine(PROD_DATABASE_URL, connect_args={"connect_timeout": 10})

    # Quick connectivity test first
    try:
        with prod_engine.connect() as test_conn:
            test_conn.execute(text("SELECT 1"))
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
                            allowed_area_ids, created_at, updated_at
                        ) VALUES (
                            :id, :fn, :ln, :name, :nn, :sex,
                            :rank_id, :dept_id, :notes,
                            :active, :svc_active,
                            :reason_id, :reason_detail,
                            :participa,
                            :wp,
                            :mst, :msm, :mslm, :am,
                            :areas, :now, :now
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
                        "areas": d["allowed_area_ids"] or [],
                        "now": now,
                    },
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

    result = SeedResult(
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

    logger.info("Seed from production completed: %s", result.model_dump())
    return result
