#!/usr/bin/env python3
"""Seed compartido para tests E2E (PostgreSQL descartable en el puerto 5434).

Siembra el mínimo necesario para ejercitar el flujo crítico del modo manual:
- 1 usuario admin (login HTTP real, password hasheada con el hasher de la app)
- Catálogos mínimos: 3 áreas (emergencia/pista/disponible), 1 rango,
  1 departamento, 1 razón de desactivación
- 2 médicos con disponibilidad semanal fija (availability_mode="fixed")
- 1 médico en modo mensual SIN disponibilidad del mes actual (candidato
  "no disponible" con razón no-dura para el flujo de justificación)

Uso:
  cd <raíz del repo>
  DATABASE_URL=postgresql+psycopg://postgres:postgres@127.0.0.1:5434/medical_shifts_test \
      ./.venv/bin/python -m backend.scripts.seed_e2e

También se puede importar `seed(session)` desde el conftest de E2E (que hace
drop/create del schema por corrida y re-siembra sobre la base vacía).
"""
from __future__ import annotations

import os
import sys
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from backend.app.application.catalogs.service import normalize_name
from backend.app.core.security import hash_password
from backend.app.infrastructure.db.models.availability import DoctorAvailabilityModel
from backend.app.infrastructure.db.models.catalogs import (
    DeactivationReasonModel,
    DepartmentModel,
    RankModel,
    ServiceAreaModel,
)
from backend.app.infrastructure.db.models.doctors import (
    DoctorAllowedAreaModel,
    DoctorModel,
)
from backend.app.infrastructure.db.models.user import UserModel

# Credenciales del admin del seed (SSOT usado también por los tests).
ADMIN_EMAIL = "admin@turnos.com"
ADMIN_PASSWORD = "AdminTest2026!"

# Nombres de los médicos (SSOT para localizar por nombre en las respuestas).
DOCTOR_WEEKLY_A_NAME = "Dra. Ana E2E"
DOCTOR_WEEKLY_B_NAME = "Dr. Bruno E2E"
DOCTOR_MONTHLY_NAME = "Dr. Carlos E2E"

DEFAULT_DATABASE_URL = (
    "postgresql+psycopg://postgres:postgres@127.0.0.1:5434/medical_shifts_test"
)

# load_weight según AREA_WEIGHTS (SSOT del dominio): emergencia 3, pista 2, disponible 1.
AREA_SPECS = [
    {"code": "emergencia", "display_name": "Emergencia", "load_weight": 3,
     "required_for_daily_coverage": True},
    {"code": "pista", "display_name": "Pista", "load_weight": 2,
     "required_for_daily_coverage": True},
    {"code": "disponible", "display_name": "Disponible", "load_weight": 1,
     "required_for_daily_coverage": False},
]


def _now() -> datetime:
    return datetime.now(UTC)


def seed(session: Session) -> dict:
    """Siembra los datos E2E mínimos. Devuelve un dict con los ids creados.

    Idempotente: si el admin ya existe, no toca nada y devuelve {"seeded": False}.
    Espera un schema ya migrado/creado (no hace create_all).
    """
    existing_admin = session.scalars(
        select(UserModel).where(UserModel.email == ADMIN_EMAIL)
    ).first()
    if existing_admin is not None:
        return {"seeded": False}

    now = _now()

    # ── Usuario admin ────────────────────────────────────────────────────
    admin = UserModel(
        id=str(uuid4()),
        name="Administrador E2E",
        email=ADMIN_EMAIL,
        role="admin",
        permissions=[],
        is_superadmin=True,
        active=True,
        password_hash=hash_password(ADMIN_PASSWORD),
        must_change_password=False,
        token_version=1,
        failed_login_count=0,
        created_at=now,
        updated_at=now,
    )
    session.add(admin)

    # ── Catálogos mínimos ────────────────────────────────────────────────
    # Las áreas ya pueden existir: la migración
    # 20260521_0028_seed_required_service_areas las siembra con ids fijos.
    # Tras un drop/create del conftest E2E no existen y se insertan aquí.
    areas: dict[str, ServiceAreaModel] = {}
    for spec in AREA_SPECS:
        area = session.scalars(
            select(ServiceAreaModel).where(ServiceAreaModel.code == spec["code"])
        ).first()
        if area is None:
            area = ServiceAreaModel(
                id=str(uuid4()),
                code=spec["code"],
                display_name=spec["display_name"],
                active=True,
                required_for_daily_coverage=spec["required_for_daily_coverage"],
                load_weight=spec["load_weight"],
                start_hour=7,
                created_at=now,
                updated_at=now,
            )
            session.add(area)
        areas[spec["code"]] = area

    rank = RankModel(
        id=str(uuid4()),
        name="Teniente",
        normalized_name=normalize_name("Teniente"),
        abbreviation="Tte.",
        active=True,
        created_at=now,
        updated_at=now,
    )
    session.add(rank)

    department = DepartmentModel(
        id=str(uuid4()),
        name="Emergencias",
        normalized_name=normalize_name("Emergencias"),
        active=True,
        created_at=now,
        updated_at=now,
    )
    session.add(department)

    reason = DeactivationReasonModel(
        id=str(uuid4()),
        code="sin_disponibilidad_mensual",
        display_name="Sin disponibilidad mensual",
        active=True,
        requires_detail=False,
        applies_to_sex=None,
        severity="hard_block",
        created_at=now,
        updated_at=now,
    )
    session.add(reason)

    session.flush()

    # ── Médicos ──────────────────────────────────────────────────────────
    def add_doctor(
        *,
        name: str,
        sex: str,
        availability_mode: str,
        phone: str,
        target: int,
        max_services: int,
    ) -> DoctorModel:
        doctor = DoctorModel(
            id=str(uuid4()),
            name=name,
            normalized_name=normalize_name(name),
            sex=sex,
            rank_id=rank.id,
            department_id=department.id,
            active=True,
            service_active=True,
            participa_misiones=True,
            whatsapp_phone=phone,
            monthly_service_target=target,
            monthly_service_max=max_services,
            monthly_service_limit_mode="warn_only",
            availability_mode=availability_mode,
            pool_active=True,
            area_rotation_mode="auto",
            created_by=admin.id,
            created_at=now,
            updated_at=now,
        )
        session.add(doctor)
        # Flush por etapas: los modelos con FK sin relationship() (p.ej.
        # DoctorAllowedAreaModel / DoctorAvailabilityModel) no garantizan
        # orden de INSERT en el unit-of-work de SQLAlchemy.
        session.flush()
        session.add(
            DoctorAllowedAreaModel(
                doctor_id=doctor.id,
                service_area_id=areas["emergencia"].id,
            )
        )
        return doctor

    doctor_a = add_doctor(
        name=DOCTOR_WEEKLY_A_NAME,
        sex="female",
        availability_mode="fixed",
        phone="+51999000001",
        target=4,
        max_services=6,
    )
    doctor_b = add_doctor(
        name=DOCTOR_WEEKLY_B_NAME,
        sex="male",
        availability_mode="fixed",
        phone="+51999000002",
        target=4,
        max_services=6,
    )
    doctor_monthly = add_doctor(
        name=DOCTOR_MONTHLY_NAME,
        sex="male",
        availability_mode="monthly",
        phone="+51999000003",
        target=3,
        max_services=3,
    )

    # Disponibilidad semanal fija: Dra. Ana lunes-miércoles, Dr. Bruno jueves-sábado.
    for doctor, days in ((doctor_a, [0, 1, 2]), (doctor_b, [3, 4, 5])):
        session.add(
            DoctorAvailabilityModel(
                id=str(uuid4()),
                doctor_id=doctor.id,
                availability_type="weekly_fixed",
                days_of_week=days,
                available_dates=None,
                weekday=None,
                week_number=None,
                year=None,
                month=None,
                day_priority="available",
                submitted_at=None,
                effective_from=None,
                effective_to=None,
                source="manual",
                review_status="approved",
                created_by=admin.id,
                created_at=now,
                updated_at=now,
            )
        )

    # El médico mensual NO tiene disponibilidad del mes actual a propósito:
    # el flujo E2E lo usa como candidato "no disponible" con razón no-dura.

    session.flush()
    return {
        "seeded": True,
        "admin_id": admin.id,
        "areas": {code: area.id for code, area in areas.items()},
        "rank_id": rank.id,
        "department_id": department.id,
        "reason_id": reason.id,
        "weekly_doctors": [doctor_a.id, doctor_b.id],
        "monthly_doctor": doctor_monthly.id,
    }


def main() -> int:
    database_url = os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
    engine = create_engine(database_url)
    with Session(engine) as session:
        try:
            result = seed(session)
            if not result["seeded"]:
                print(f"Seed ya aplicado (existe {ADMIN_EMAIL}). Nada que hacer.")
                return 0
            session.commit()
        except Exception as exc:  # noqa: BLE001 — script de CLI: reportar y salir
            session.rollback()
            print(f"ERROR: seed_e2e falló: {exc}", file=sys.stderr)
            return 1
    print(
        f"Seed E2E aplicado: admin={ADMIN_EMAIL}, "
        f"áreas={list(result['areas'])}, "
        f"médicos semanales={[DOCTOR_WEEKLY_A_NAME, DOCTOR_WEEKLY_B_NAME]}, "
        f"médico mensual={DOCTOR_MONTHLY_NAME}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
