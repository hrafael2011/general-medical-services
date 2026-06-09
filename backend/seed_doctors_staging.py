"""
Script standalone para crear 42 doctores sintéticos en staging.

Uso:
    python backend/seed_doctors_staging.py          (desde la raíz del proyecto)
    cd backend && python seed_doctors_staging.py    (desde backend/)

ADVERTENCIA: NO ejecutar en producción — el script aborta automáticamente
si detecta que app_env == "production".
"""

import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

# Asegura que la raíz del proyecto esté en sys.path para `from backend.app...`
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from backend.app.core.config import settings

# ═══════════════════════════════════════════════════════════════════════════════
# GUARD: producir está rotundamente prohibido
# ═══════════════════════════════════════════════════════════════════════════════

if settings.app_env == "production":
    print("=" * 60)
    print("  ERROR: app_env = 'production'")
    print("  Este script solo puede ejecutarse en staging.")
    print("  Saliendo sin hacer nada.")
    print("=" * 60)
    sys.exit(1)

# ═══════════════════════════════════════════════════════════════════════════════
# Conexión a la base de datos
# ═══════════════════════════════════════════════════════════════════════════════

engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine)
session: Session = SessionLocal()

# ═══════════════════════════════════════════════════════════════════════════════
# Catálogos sintéticos
# ═══════════════════════════════════════════════════════════════════════════════

RANKS = [
    ("Coronel",             "coronel",             "Cor."),
    ("Teniente Coronel",    "teniente coronel",    "Tte. Cor."),
    ("Mayor",               "mayor",               "My."),
    ("Capitán",             "capitán",             "Cap."),
    ("Primer Teniente",     "primer teniente",     "1er. Tte."),
]

DEPARTMENTS = [
    "Medicina General",
    "Cirugía",
    "Pediatría",
    "Ginecología",
    "Cardiología",
    "Traumatología",
    "Dermatología",
    "Psiquiatría",
]

MALE_FIRST = [
    "Carlos", "Juan", "Pedro", "Miguel", "José",
    "Luis", "Rafael", "Manuel", "Francisco", "Antonio",
    "David", "Alejandro", "Roberto", "Fernando", "Jorge",
    "Ricardo", "Eduardo", "Daniel", "Andrés", "Gabriel",
    "Sergio",
]

FEMALE_FIRST = [
    "María", "Ana", "Carmen", "Rosa", "Laura",
    "Isabel", "Elena", "Sofía", "Patricia", "Marta",
    "Teresa", "Cristina", "Andrea", "Paula", "Raquel",
    "Silvia", "Claudia", "Verónica", "Natalia", "Lourdes",
    "Beatriz",
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

# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _make_phone(index: int) -> str:
    return f"+1-809-{index:03d}-{index * 7 % 10000:04d}"


def _ensure_catalogs(session: Session) -> None:
    """Crea ranks y departamentos sintéticos si las tablas están vacías."""
    now = datetime.now(timezone.utc)

    # ── Ranks ──
    rank_count = session.execute(text("SELECT COUNT(*) FROM ranks")).scalar()
    if rank_count == 0:
        for name, norm, abbr in RANKS:
            session.execute(
                text("""
                    INSERT INTO ranks (id, name, normalized_name, abbreviation, active, created_at, updated_at)
                    VALUES (:id, :name, :normalized_name, :abbreviation, true, :now, :now)
                """),
                {"id": str(uuid4()), "name": name, "normalized_name": norm, "abbreviation": abbr, "now": now},
            )
        session.commit()
        print("  ✓ 5 ranks sintéticos creados")
    else:
        print(f"  ✓ {rank_count} ranks existentes (sin cambios)")

    # ── Departments ──
    dept_count = session.execute(text("SELECT COUNT(*) FROM departments")).scalar()
    if dept_count == 0:
        for name in DEPARTMENTS:
            session.execute(
                text("""
                    INSERT INTO departments (id, name, normalized_name, active, created_at, updated_at)
                    VALUES (:id, :name, :normalized_name, true, :now, :now)
                """),
                {"id": str(uuid4()), "name": name, "normalized_name": name.lower().strip(), "now": now},
            )
        session.commit()
        print("  ✓ 8 departamentos sintéticos creados")
    else:
        print(f"  ✓ {dept_count} departamentos existentes (sin cambios)")


def _get_catalog_ids(session: Session) -> tuple[list[str], list[str]]:
    rank_ids = [r[0] for r in session.execute(text("SELECT id FROM ranks ORDER BY name")).fetchall()]
    dept_ids = [d[0] for d in session.execute(text("SELECT id FROM departments ORDER BY name")).fetchall()]
    return rank_ids, dept_ids


# ═══════════════════════════════════════════════════════════════════════════════
# Generación de doctores
# ═══════════════════════════════════════════════════════════════════════════════

INSERT_STMT = text("""
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


def _build_and_insert_doctors(
    session: Session, rank_ids: list[str], dept_ids: list[str]
) -> int:
    """Construye e inserta 42 doctores (21 male, 21 female) con datos sintéticos."""
    now = datetime.now(timezone.utc)
    used_norms: set[str] = set()
    total = 0
    phone_idx = 0

    # ── 21 masculinos ──
    for i in range(21):
        fn = MALE_FIRST[i]
        ln = LAST_NAMES[i % len(LAST_NAMES)]
        full_name = f"{fn} {ln}"
        norm = full_name.lower().strip()

        # Garantizar unicidad
        if norm in used_norms:
            for offset in range(1, len(LAST_NAMES)):
                candidate_ln = LAST_NAMES[(i + offset) % len(LAST_NAMES)]
                candidate_norm = f"{fn} {candidate_ln}".lower().strip()
                if candidate_norm not in used_norms:
                    ln = candidate_ln
                    full_name = f"{fn} {ln}"
                    norm = candidate_norm
                    break
        used_norms.add(norm)

        phone_idx += 1
        params = {
            "id": str(uuid4()),
            "first_name": fn,
            "last_name": ln,
            "name": full_name,
            "normalized_name": norm,
            "sex": "male",
            "rank_id": rank_ids[i % len(rank_ids)],
            "department_id": dept_ids[i % len(dept_ids)],
            "active": True,
            "service_active": True,
            "participa_misiones": True,
            "whatsapp_phone": _make_phone(phone_idx),
            "monthly_service_target": 3,
            "monthly_service_max": 3,
            "monthly_service_limit_mode": "warn_only",
            "availability_mode": "monthly",
            "created_at": now,
            "updated_at": now,
        }
        try:
            session.execute(INSERT_STMT, params)
        except Exception as e:
            print(f"  ✗ Error insertando doctor #{total+1} ({full_name}): {e}")
            session.rollback()
            continue

        print(f"  ✓ #{total+1:02d} {full_name} ({'male'}) - {params['rank_id'][:8]}... / {params['department_id'][:8]}...")
        total += 1

    session.commit()

    # ── 21 femeninos ──
    for i in range(21):
        fn = FEMALE_FIRST[i]
        ln = LAST_NAMES[(i + 21) % len(LAST_NAMES)]
        full_name = f"{fn} {ln}"
        norm = full_name.lower().strip()

        if norm in used_norms:
            for offset in range(1, len(LAST_NAMES)):
                candidate_ln = LAST_NAMES[((i + 21) + offset) % len(LAST_NAMES)]
                candidate_norm = f"{fn} {candidate_ln}".lower().strip()
                if candidate_norm not in used_norms:
                    ln = candidate_ln
                    full_name = f"{fn} {ln}"
                    norm = candidate_norm
                    break
        used_norms.add(norm)

        phone_idx += 1
        params = {
            "id": str(uuid4()),
            "first_name": fn,
            "last_name": ln,
            "name": full_name,
            "normalized_name": norm,
            "sex": "female",
            "rank_id": rank_ids[(i + 21) % len(rank_ids)],
            "department_id": dept_ids[(i + 21) % len(dept_ids)],
            "active": True,
            "service_active": True,
            "participa_misiones": True,
            "whatsapp_phone": _make_phone(phone_idx),
            "monthly_service_target": 3,
            "monthly_service_max": 3,
            "monthly_service_limit_mode": "warn_only",
            "availability_mode": "monthly",
            "created_at": now,
            "updated_at": now,
        }
        try:
            session.execute(INSERT_STMT, params)
        except Exception as e:
            print(f"  ✗ Error insertando doctor #{total+1} ({full_name}): {e}")
            session.rollback()
            continue

        print(f"  ✓ #{total+1:02d} {full_name} (female) - {params['rank_id'][:8]}... / {params['department_id'][:8]}...")
        total += 1

    session.commit()
    return total


# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    # Doble guard contra producción
    if settings.app_env == "production":
        print("=" * 60)
        print("  ERROR: app_env = 'production' — Saliendo.")
        print("=" * 60)
        sys.exit(1)

    print(f"Entorno: {settings.app_env}")
    print()

    # Verificar conexión
    try:
        session.execute(text("SELECT 1"))
        print("✓ Conexión establecida")
    except Exception as e:
        print(f"✗ Error de conexión: {e}")
        sys.exit(1)

    # Catálogos
    _ensure_catalogs(session)
    rank_ids, dept_ids = _get_catalog_ids(session)
    print(f"  ✓ {len(rank_ids)} ranks disponibles")
    print(f"  ✓ {len(dept_ids)} departamentos disponibles")
    print()

    # Doctores
    print("Insertando doctores...")
    total = _build_and_insert_doctors(session, rank_ids, dept_ids)
    print()
    print(f"✓ {total} doctores creados ({total//2} masculinos, {total - total//2} femeninos)")
    print()

    # Confirmación final
    count = session.execute(text("SELECT COUNT(*) FROM doctors")).scalar()
    male_count = session.execute(text("SELECT COUNT(*) FROM doctors WHERE sex = 'male'")).scalar()
    female_count = session.execute(text("SELECT COUNT(*) FROM doctors WHERE sex = 'female'")).scalar()
    print(f"Total doctores en la DB: {count}  (♂ {male_count} / ♀ {female_count})")
    print("Hecho.")

    session.close()
    engine.dispose()


if __name__ == "__main__":
    main()
