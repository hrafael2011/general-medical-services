#!/usr/bin/env python
"""Cierra el hueco de datos del eje 2: médicos fuera de servicio sin motivo.

Contexto (spec `2026-10-09-licencias-con-fechas-y-recordatorio`): había **dos puertas** para
desactivar a un médico. El botón dedicado pedía motivo y lo guardaba; editar el médico y
desmarcar "presta servicio" no lo pedía. Por esa segunda puerta quedaron médicos **fuera de
servicio sin motivo registrado y todavía dentro de misiones**.

La auditoría de mayo de 2026 lo confirma: los afectados tienen un `doctor_updated` con
`service_active: False`, `participa_misiones: True` y `allowed_area_ids: []`, y **el motivo no
quedó registrado en ninguna parte**. No se puede recuperar: hay que elegirlo. Decisión del
usuario (2026-10-10): motivo **OTROS** con una nota que deja claro que fue una desactivación
histórica sin motivo, y sacarlos de misiones, como exige la regla unificada.

Hace dos cosas, ambas idempotentes:

1. Fuera de servicio **sin motivo** → se le pone OTROS + la nota, y se le quita de misiones.
2. Fuera de servicio con motivo **pero todavía en misiones** → se le quita de misiones.

Queda registrado en la auditoría con actor `Sistema` (la interfaz lo muestra así), porque no
lo hizo una persona: es una corrección de datos.

Uso:
    python scripts/fix_absence_inconsistencies.py --dry-run
    python scripts/fix_absence_inconsistencies.py
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import func, select  # noqa: E402

from backend.app.application.audit.service import AuditService  # noqa: E402
from backend.app.infrastructure.db.models.catalogs import (  # noqa: E402
    DeactivationReasonModel,
)
from backend.app.infrastructure.db.models.doctors import DoctorModel  # noqa: E402
from backend.app.infrastructure.repositories.audit import AuditRepository  # noqa: E402
from backend.app.infrastructure.db.session import SessionLocal  # noqa: E402

# El motivo que se usa para no inventar una causa: dice explícitamente que no se sabe.
FALLBACK_REASON_NAME = "OTROS"

HISTORICAL_DETAIL = (
    "Desactivación histórica sin motivo registrado; se completó al unificar las dos puertas "
    "de desactivación (2026-10-10)."
)


def _find_fallback_reason(session) -> DeactivationReasonModel:
    reason = session.execute(
        select(DeactivationReasonModel).where(
            func.upper(DeactivationReasonModel.display_name) == FALLBACK_REASON_NAME,
            DeactivationReasonModel.deleted_at.is_(None),
        )
    ).scalars().first()
    if reason is None:
        # Nada de adivinar: si el catálogo no tiene el motivo acordado, el script se detiene.
        raise SystemExit(
            f"No se encontró el motivo «{FALLBACK_REASON_NAME}» en el catálogo. "
            "No se cambia nada."
        )
    return reason


def main() -> None:
    dry_run = "--dry-run" in sys.argv

    with SessionLocal() as session:
        reason = _find_fallback_reason(session)
        audit = AuditService(AuditRepository(session))

        missing_reason = session.execute(
            select(DoctorModel).where(
                DoctorModel.service_active.is_(False),
                DoctorModel.deleted_at.is_(None),
                DoctorModel.service_inactive_reason_id.is_(None),
            )
        ).scalars().all()

        out_of_missions = session.execute(
            select(DoctorModel).where(
                DoctorModel.service_active.is_(False),
                DoctorModel.deleted_at.is_(None),
                DoctorModel.service_inactive_reason_id.is_not(None),
                DoctorModel.participa_misiones.is_(True),
            )
        ).scalars().all()

        print(f"Motivo que se usará: {reason.display_name} ({reason.id})")
        print(f"{'[SIMULACIÓN] ' if dry_run else ''}Sin motivo: {len(missing_reason)} · "
              f"con motivo pero en misiones: {len(out_of_missions)}\n")

        for doctor in missing_reason:
            print(f"  · {doctor.name}: sin motivo → {FALLBACK_REASON_NAME}, fuera de misiones")
            if dry_run:
                continue
            doctor.service_inactive_reason_id = reason.id
            doctor.service_inactive_detail = HISTORICAL_DETAIL
            doctor.participa_misiones = False
            doctor.updated_at = datetime.now(UTC)
            audit.log_doctor_updated(
                actor_id=None,  # type: ignore[arg-type]  # lo muestra como "Sistema"
                doctor=doctor,
                changed_fields={
                    "service_inactive_reason_id": reason.id,
                    "service_inactive_detail": HISTORICAL_DETAIL,
                    "participa_misiones": False,
                },
            )

        for doctor in out_of_missions:
            print(f"  · {doctor.name}: tiene motivo pero seguía en misiones → fuera de misiones")
            if dry_run:
                continue
            doctor.participa_misiones = False
            doctor.updated_at = datetime.now(UTC)
            audit.log_doctor_updated(
                actor_id=None,  # type: ignore[arg-type]
                doctor=doctor,
                changed_fields={"participa_misiones": False},
            )

        if dry_run:
            session.rollback()
            print("\n[SIMULACIÓN] No se escribió nada.")
        else:
            session.commit()
            print(f"\nListo: {len(missing_reason) + len(out_of_missions)} médicos corregidos.")


if __name__ == "__main__":
    main()
