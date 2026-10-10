#!/usr/bin/env python3
"""Script unico: limpia disponibilidad huerfana cuando la modalidad del doctor cambio.

Cuando un doctor cambia de "fixed" a "monthly" (o viceversa), los registros de
disponibilidad de la modalidad anterior NO se eliminan. Esto causa que el solver
asigne doctores en dias incorrectos porque encuentra registros viejos.

Este script:
- Encuentra doctores con availability_mode="monthly" que aun tienen registros
  weekly_fixed o recurring, y los elimina.
- Encuentra doctores con availability_mode="fixed" que aun tienen registros
  monthly_variable, y los elimina.
- Imprime un reporte de lo que limpio.

Uso:
  cd /path/to/project/root
  python backend/scripts/cleanup_orphan_availability.py
"""

import sys
from datetime import UTC, datetime

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

sys.path.insert(0, "backend")

from backend.app.core.config import Settings  # noqa: E402

MONTHLY_FIXED_TYPES = ("weekly_fixed", "recurring")
MONTHLY_VARIABLE_TYPE = "monthly_variable"


def main() -> None:
    settings = Settings()  # reads DATABASE_URL from env or falls back to default
    engine = create_engine(settings.database_url)
    total_removed = 0
    total_monthly_affected = 0
    total_fixed_affected = 0

    print("=" * 70)
    print("  cleanup_orphan_availability — Limpieza de disponibilidad huerfana")
    print("=" * 70)

    with Session(engine) as session:
        # ------------------------------------------------------------------
        # 1. Doctors con availability_mode="monthly" que tienen
        #    weekly_fixed o recurring (fixed patterns)
        # ------------------------------------------------------------------
        print("\n[1/2] Doctores en modo monthly con patrones fijos huerfanos...")
        monthly_rows = session.execute(
            text("""
                SELECT d.id, d.name, d.availability_mode, da.availability_type, da.id AS avail_id
                FROM doctors d
                JOIN doctor_availability da ON da.doctor_id = d.id
                WHERE d.availability_mode = 'monthly'
                  AND da.availability_type IN (:type1, :type2)
                ORDER BY d.name, da.availability_type
            """),
            {"type1": "weekly_fixed", "type2": "recurring"},
        ).all()

        if not monthly_rows:
            print("  No se encontraron registros huerfanos.")
        else:
            doctor_monthly_map: dict[str, dict] = {}
            for row in monthly_rows:
                doc_id = row.id
                if doc_id not in doctor_monthly_map:
                    doctor_monthly_map[doc_id] = {"name": row.name, "avail_ids": []}
                doctor_monthly_map[doc_id]["avail_ids"].append((row.avail_id, row.availability_type))

            print(f"  Se encontraron {len(monthly_rows)} registros huerfanos en {len(doctor_monthly_map)} doctores:")
            for doc_id, info in sorted(doctor_monthly_map.items()):
                types_summary = ", ".join(t for _, t in info["avail_ids"])
                print(f"    - {info['name']} ({doc_id[:8]}...): {types_summary}")
                # Delete each orphan record
                for avail_id, _at in info["avail_ids"]:
                    session.execute(
                        text("DELETE FROM doctor_availability WHERE id = :id"),
                        {"id": avail_id},
                    )
                    total_removed += 1
                total_monthly_affected += 1

        # ------------------------------------------------------------------
        # 2. Doctors con availability_mode="fixed" que tienen
        #    monthly_variable
        # ------------------------------------------------------------------
        print("\n[2/2] Doctores en modo fixed con disponibilidad mensual huerfana...")
        fixed_rows = session.execute(
            text("""
                SELECT d.id, d.name, d.availability_mode,
                       da.year, da.month, da.id AS avail_id
                FROM doctors d
                JOIN doctor_availability da ON da.doctor_id = d.id
                WHERE d.availability_mode = 'fixed'
                  AND da.availability_type = :av_type
                ORDER BY d.name, da.year, da.month
            """),
            {"av_type": MONTHLY_VARIABLE_TYPE},
        ).all()

        if not fixed_rows:
            print("  No se encontraron registros huerfanos.")
        else:
            doctor_fixed_map: dict[str, dict] = {}
            for row in fixed_rows:
                doc_id = row.id
                if doc_id not in doctor_fixed_map:
                    doctor_fixed_map[doc_id] = {"name": row.name, "avail_ids": []}
                doctor_fixed_map[doc_id]["avail_ids"].append(
                    (row.avail_id, row.year, row.month)
                )

            print(f"  Se encontraron {len(fixed_rows)} registros huerfanos en {len(doctor_fixed_map)} doctores:")
            for doc_id, info in sorted(doctor_fixed_map.items()):
                periods = ", ".join(f"{y}-{m:02d}" for _, y, m in info["avail_ids"])
                print(f"    - {info['name']} ({doc_id[:8]}...): {periods}")
                for avail_id, _y, _m in info["avail_ids"]:
                    session.execute(
                        text("DELETE FROM doctor_availability WHERE id = :id"),
                        {"id": avail_id},
                    )
                    total_removed += 1
                total_fixed_affected += 1

        # ------------------------------------------------------------------
        # Commit
        # ------------------------------------------------------------------
        session.commit()

    print("\n" + "=" * 70)
    print(f"  RESUMEN: {total_removed} registros eliminados")
    print(f"  Doctores monthly afectados: {total_monthly_affected}")
    print(f"  Doctores fixed afectados:   {total_fixed_affected}")
    if total_removed > 0:
        print("  Los registros huerfanos han sido eliminados exitosamente.")
    else:
        print("  No habia registros huerfanos por limpiar.")
    print("=" * 70)


if __name__ == "__main__":
    main()
