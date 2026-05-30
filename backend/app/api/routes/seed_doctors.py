"""
Endpoint temporal para seed de 42 doctores sintéticos en staging.

Solo se registra si app_env == "staging".
POST /api/admin/seed-doctors
"""

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.api.dependencies import require_admin
from backend.app.core.config import settings
from backend.app.infrastructure.db.models.user import UserModel
from backend.app.infrastructure.db.session import get_db_session

router = APIRouter(prefix="/admin", tags=["admin"])

RANKS = [
    ("Coronel", "coronel", "Cor."),
    ("Teniente Coronel", "teniente coronel", "Tte. Cor."),
    ("Mayor", "mayor", "My."),
    ("Capitán", "capitán", "Cap."),
    ("Primer Teniente", "primer teniente", "1er. Tte."),
]

DEPARTMENTS = [
    "Medicina General", "Cirugía", "Pediatría", "Ginecología",
    "Cardiología", "Traumatología", "Dermatología", "Psiquiatría",
]

MALE_FIRST = [
    "Carlos", "Juan", "Pedro", "Miguel", "José", "Luis", "Rafael",
    "Manuel", "Francisco", "Antonio", "David", "Alejandro", "Roberto",
    "Fernando", "Jorge", "Ricardo", "Eduardo", "Daniel", "Andrés",
    "Gabriel", "Sergio",
]

FEMALE_FIRST = [
    "María", "Ana", "Carmen", "Rosa", "Laura", "Isabel", "Elena",
    "Sofía", "Patricia", "Marta", "Teresa", "Cristina", "Andrea",
    "Paula", "Raquel", "Silvia", "Claudia", "Verónica", "Natalia",
    "Lourdes", "Beatriz",
]

LAST_NAMES = [
    "García", "Rodríguez", "Martínez", "López", "Hernández",
    "González", "Pérez", "Sánchez", "Ramírez", "Torres",
    "Flores", "Rivera", "Castillo", "Vargas", "Reyes",
    "Cruz", "Ortiz", "Morales", "Silva", "Jiménez",
    "Medina", "Castro", "Romero", "Delgado", "Peña",
    "Guzmán", "Moya", "Santana", "Herrera", "Mendoza",
    "Guerrero", "Rojas", "Figueroa", "Ramos", "Vásquez",
    "Molina", "Núñez", "Cabrera", "Acosta", "Blanco",
    "Paredes", "Velásquez",
]

INSERT_DOCTOR = text("""
    INSERT INTO doctors (
        id, first_name, last_name, name, normalized_name, sex,
        rank_id, department_id, active, service_active,
        participa_misiones, whatsapp_phone,
        monthly_service_target, monthly_service_max,
        monthly_service_limit_mode, availability_mode,
        created_at, updated_at
    ) VALUES (
        :id, :first_name, :last_name, :name, :normalized_name, :sex,
        :rank_id, :department_id, :active, :service_active,
        :participa_misiones, :whatsapp_phone,
        :monthly_service_target, :monthly_service_max,
        :monthly_service_limit_mode, :availability_mode,
        :created_at, :updated_at
    )
""")


class SeedDoctorsResult(BaseModel):
    ok: bool
    created: int
    total_in_db: int
    male_count: int
    female_count: int
    detail: str


def _make_phone(index: int) -> str:
    return f"+1-809-{index:03d}-{index * 7 % 10000:04d}"


@router.post("/seed-doctors", response_model=SeedDoctorsResult)
def seed_doctors(
    _current_user: UserModel = Depends(require_admin),
    session: Session = Depends(get_db_session),
) -> SeedDoctorsResult:
    # Guard: solo staging
    if settings.app_env != "staging":
        return SeedDoctorsResult(
            ok=False, created=0, total_in_db=0, male_count=0, female_count=0,
            detail="Solo disponible en staging",
        )

    now = datetime.now(timezone.utc)

    # ── Catálogos ──
    rank_count = session.execute(text("SELECT COUNT(*) FROM ranks")).scalar()
    if rank_count == 0:
        for name, norm, abbr in RANKS:
            session.execute(
                text("INSERT INTO ranks (id, name, normalized_name, abbreviation, active, created_at, updated_at) VALUES (:id, :name, :n, :a, true, :now, :now)"),
                {"id": str(uuid4()), "name": name, "n": norm, "a": abbr, "now": now},
            )
        session.commit()

    dept_count = session.execute(text("SELECT COUNT(*) FROM departments")).scalar()
    if dept_count == 0:
        for name in DEPARTMENTS:
            session.execute(
                text("INSERT INTO departments (id, name, normalized_name, active, created_at, updated_at) VALUES (:id, :name, :n, true, :now, :now)"),
                {"id": str(uuid4()), "name": name, "n": name.lower().strip(), "now": now},
            )
        session.commit()

    rank_ids = [r[0] for r in session.execute(text("SELECT id FROM ranks ORDER BY name")).fetchall()]
    dept_ids = [d[0] for d in session.execute(text("SELECT id FROM departments ORDER BY name")).fetchall()]

    if not rank_ids or not dept_ids:
        return SeedDoctorsResult(
            ok=False, created=0, total_in_db=0, male_count=0, female_count=0,
            detail="No hay ranks o departments disponibles",
        )

    # ── 42 doctores ──
    used: set[str] = set()
    phone_idx = 0
    created = 0

    for i in range(21):
        fn = MALE_FIRST[i]
        ln = LAST_NAMES[i % len(LAST_NAMES)]
        full = f"{fn} {ln}"
        norm = full.lower().strip()
        if norm in used:
            for off in range(1, len(LAST_NAMES)):
                cln = LAST_NAMES[(i + off) % len(LAST_NAMES)]
                cn = f"{fn} {cln}".lower().strip()
                if cn not in used:
                    ln, full, norm = cln, f"{fn} {cln}", cn
                    break
        used.add(norm)
        phone_idx += 1
        session.execute(INSERT_DOCTOR, {
            "id": str(uuid4()), "first_name": fn, "last_name": ln,
            "name": full, "normalized_name": norm, "sex": "male",
            "rank_id": rank_ids[i % len(rank_ids)],
            "department_id": dept_ids[i % len(dept_ids)],
            "active": True, "service_active": True, "participa_misiones": True,
            "whatsapp_phone": _make_phone(phone_idx),
            "monthly_service_target": 3, "monthly_service_max": 3,
            "monthly_service_limit_mode": "warn_only", "availability_mode": "monthly",
            "created_at": now, "updated_at": now,
        })
        created += 1
    session.commit()

    for i in range(21):
        fn = FEMALE_FIRST[i]
        ln = LAST_NAMES[(i + 21) % len(LAST_NAMES)]
        full = f"{fn} {ln}"
        norm = full.lower().strip()
        if norm in used:
            for off in range(1, len(LAST_NAMES)):
                cln = LAST_NAMES[((i + 21) + off) % len(LAST_NAMES)]
                cn = f"{fn} {cln}".lower().strip()
                if cn not in used:
                    ln, full, norm = cln, f"{fn} {cln}", cn
                    break
        used.add(norm)
        phone_idx += 1
        session.execute(INSERT_DOCTOR, {
            "id": str(uuid4()), "first_name": fn, "last_name": ln,
            "name": full, "normalized_name": norm, "sex": "female",
            "rank_id": rank_ids[(i + 21) % len(rank_ids)],
            "department_id": dept_ids[(i + 21) % len(dept_ids)],
            "active": True, "service_active": True, "participa_misiones": True,
            "whatsapp_phone": _make_phone(phone_idx),
            "monthly_service_target": 3, "monthly_service_max": 3,
            "monthly_service_limit_mode": "warn_only", "availability_mode": "monthly",
            "created_at": now, "updated_at": now,
        })
        created += 1
    session.commit()

    total = session.execute(text("SELECT COUNT(*) FROM doctors")).scalar()
    male_c = session.execute(text("SELECT COUNT(*) FROM doctors WHERE sex = 'male'")).scalar()
    female_c = session.execute(text("SELECT COUNT(*) FROM doctors WHERE sex = 'female'")).scalar()

    return SeedDoctorsResult(
        ok=True, created=created, total_in_db=total,
        male_count=male_c, female_count=female_c,
        detail=f"{created} doctores creados",
    )
