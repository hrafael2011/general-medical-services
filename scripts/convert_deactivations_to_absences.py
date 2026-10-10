#!/usr/bin/env python
"""Convierte las desactivaciones actuales en **ausencias Indefinidas**.

Extensión v1.3.0 del spec `2026-10-09-licencias-con-fechas-y-recordatorio`: a partir de ahora
hay **una sola** forma de decir que un médico no está disponible —la **ausencia**— y el estado
"activo para servicio" se deriva de ella. Los médicos que hoy están fuera por el flag
(`service_active = False`) no tienen esa ausencia, así que al quitar el botón viejo se quedarían
sin forma de volver: este script les crea la ausencia que los representa.

Qué hace, por cada médico fuera de servicio **sin ausencia registrada**:

1. Le crea una ausencia **Indefinida** (`ends_at = NULL`) con **su motivo y su detalle actuales**,
   empezando en la fecha en que se le desactivó (`deactivated_at`).

   **Ojo con la fecha de inicio:** en producción `deactivated_at` está vacío en los 29, así que
   la ausencia se registra con la fecha de la conversión. Es una afirmación verdadera sobre el
   **registro** (hoy se registró), pero no sobre cuándo empezó la ausencia real, que el sistema
   nunca guardó. Se puede corregir a mano desde la pantalla si la fecha importa.
2. Lo deja auditado como **Sistema**: no lo hizo una persona, es una conversión de datos.

No reactiva a nadie, no toca misiones, no borra nada y no cambia ningún otro campo. Es
**idempotente**: a quien ya tiene una ausencia sin levantar no se le toca, así que correrlo dos
veces no duplica nada.

Uso:
    python scripts/convert_deactivations_to_absences.py --dry-run
    python scripts/convert_deactivations_to_absences.py
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import select  # noqa: E402

from backend.app.application.audit.service import AuditService  # noqa: E402
from backend.app.infrastructure.db.models.availability import (  # noqa: E402
    DoctorRestrictionModel,
)
from backend.app.infrastructure.db.models.doctors import DoctorModel  # noqa: E402
from backend.app.infrastructure.db.session import SessionLocal  # noqa: E402
from backend.app.infrastructure.repositories.audit import AuditRepository  # noqa: E402


def main() -> None:
    dry_run = "--dry-run" in sys.argv

    with SessionLocal() as session:
        audit = AuditService(AuditRepository(session))

        # Fuera de servicio y sin ninguna ausencia sin levantar que ya lo explique.
        with_absence = select(DoctorRestrictionModel.doctor_id).where(
            DoctorRestrictionModel.lifted_at.is_(None)
        )
        doctors = list(
            session.scalars(
                select(DoctorModel).where(
                    DoctorModel.deleted_at.is_(None),
                    DoctorModel.service_active.is_(False),
                    DoctorModel.id.not_in(with_absence),
                )
            )
        )

        print(f"{'[SIMULACIÓN] ' if dry_run else ''}Médicos fuera de servicio sin ausencia: {len(doctors)}\n")
        for doctor in doctors:
            starts_at = (doctor.deactivated_at or datetime.now(UTC)).date()
            reason = doctor.service_inactive_reason_id
            print(
                f"  · {doctor.name}: ausencia indefinida desde {starts_at} "
                f"(motivo {'sí' if reason else 'NO'})"
            )
            if dry_run:
                continue

            now = datetime.now(UTC)
            record = DoctorRestrictionModel(
                id=str(uuid4()),
                doctor_id=doctor.id,
                reason_id=reason,
                restriction_type="license",
                severity="hard_block",
                description=doctor.service_inactive_detail,
                starts_at=starts_at,
                ends_at=None,  # Indefinida: hasta que alguien la levante
                source="manual",
                review_status="approved",
                created_by=None,
                created_at=now,
                updated_at=now,
                lifted_at=None,
                lifted_by=None,
            )
            session.add(record)
            audit.log_restriction_added(actor_id=None, restriction=record)  # type: ignore[arg-type]

        if dry_run:
            session.rollback()
            print("\n[SIMULACIÓN] No se escribió nada.")
        else:
            session.commit()
            print(f"\nListo: {len(doctors)} médicos convertidos a ausencia indefinida.")


if __name__ == "__main__":
    main()
