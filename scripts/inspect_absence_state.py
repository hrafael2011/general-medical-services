#!/usr/bin/env python
"""Inspección de solo lectura del estado de las ausencias (eje 2) en la base conectada.

Se usa para confirmar en producción, antes de tocar nada, cuáles son los registros
inconsistentes y qué dice el catálogo de motivos real. No escribe nada.

Uso:
    python scripts/inspect_absence_state.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import func, select  # noqa: E402

from backend.app.infrastructure.db.models.availability import (  # noqa: E402
    DoctorRestrictionModel,
)
from backend.app.infrastructure.db.models.catalogs import (  # noqa: E402
    DeactivationReasonModel,
)
from backend.app.infrastructure.db.models.doctors import DoctorModel  # noqa: E402
from backend.app.infrastructure.db.session import SessionLocal  # noqa: E402


def main() -> None:
    with SessionLocal() as session:
        print("=== CATÁLOGO DE MOTIVOS (producción) ===")
        reasons = session.execute(
            select(DeactivationReasonModel).order_by(DeactivationReasonModel.display_name)
        ).scalars().all()
        for r in reasons:
            print(
                f"  id={r.id}  code={getattr(r, 'code', None)!r}  "
                f"name={r.display_name!r}  severity={getattr(r, 'severity', None)!r}  "
                f"applies_to_sex={getattr(r, 'applies_to_sex', None)!r}  "
                f"active={getattr(r, 'active', None)!r}"
            )
        print(f"  total: {len(reasons)}")

        print("\n=== FUERA DE SERVICIO SIN MOTIVO (hueco de datos) ===")
        no_reason = session.execute(
            select(DoctorModel).where(
                DoctorModel.service_active.is_(False),
                DoctorModel.service_inactive_reason_id.is_(None),
                DoctorModel.deleted_at.is_(None),
            )
        ).scalars().all()
        for d in no_reason:
            print(
                f"  id={d.id}  name={d.name!r}  sex={d.sex}  "
                f"participa_misiones={d.participa_misiones}  "
                f"detail={d.service_inactive_detail!r}  updated_at={d.updated_at}"
            )
        print(f"  total: {len(no_reason)}")

        print("\n=== FUERA DE SERVICIO PERO TODAVÍA EN MISIONES ===")
        still_missions = session.execute(
            select(DoctorModel).where(
                DoctorModel.service_active.is_(False),
                DoctorModel.participa_misiones.is_(True),
                DoctorModel.deleted_at.is_(None),
            )
        ).scalars().all()
        for d in still_missions:
            print(
                f"  id={d.id}  name={d.name!r}  sex={d.sex}  "
                f"reason_id={d.service_inactive_reason_id}  "
                f"detail={d.service_inactive_detail!r}  updated_at={d.updated_at}"
            )
        print(f"  total: {len(still_missions)}")

        print("\n=== RESTRICCIONES (mecanismo con fechas) ===")
        total = session.execute(select(func.count()).select_from(DoctorRestrictionModel)).scalar_one()
        print(f"  filas en doctor_restrictions: {total}")
        for r in session.execute(select(DoctorRestrictionModel)).scalars().all():
            print(
                f"  id={r.id}  doctor_id={r.doctor_id}  type={r.restriction_type}  "
                f"severity={r.severity}  starts_at={r.starts_at}  ends_at={r.ends_at}  "
                f"lifted_at={r.lifted_at}"
            )

        print("\n=== RESUMEN DEL EJE 2 ===")
        print(f"  médicos vivos ....................... {session.execute(select(func.count()).select_from(DoctorModel).where(DoctorModel.deleted_at.is_(None))).scalar_one()}")
        print(f"  fuera de servicio ................... {session.execute(select(func.count()).select_from(DoctorModel).where(DoctorModel.service_active.is_(False), DoctorModel.deleted_at.is_(None))).scalar_one()}")
        print(f"  fuera de misiones ................... {session.execute(select(func.count()).select_from(DoctorModel).where(DoctorModel.participa_misiones.is_(False), DoctorModel.deleted_at.is_(None))).scalar_one()}")


if __name__ == "__main__":
    main()
