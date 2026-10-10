"""El estado "activo para servicio" se **deriva** de las ausencias.

Extensión v1.3.0 del spec `2026-10-09-licencias-con-fechas-y-recordatorio`.

Antes había dos formas de decir que un médico no está disponible: el flag
`doctors.service_active` (que se ponía a mano) y una ausencia con fechas. Dejaban estados
distintos y produjeron registros inconsistentes en producción. Ahora hay **una sola** forma
—la ausencia— y el flag pasa a ser un **valor calculado**: un médico está activo para
servicio si **no tiene una ausencia vigente hoy**.

Por qué se mantiene el flag en vez de reescribir las consultas: lo leen **83 sitios del
backend y 29 del frontend**, incluido el SQL del asistente (22 consultas). Manteniéndolo
como valor calculado, todos esos sitios siguen funcionando **sin tocarlos** y dejan de
mentir. La alternativa era reescribir cada consulta para el mismo resultado.

Se recalcula en dos momentos:

1. **Al escribir**: registrar, editar o levantar una ausencia.
2. **Al pasar la fecha**: el job del recordatorio, que ya corre cada 30 minutos (así el
   estado cambia solo el día que la ausencia empieza o termina, sin que nadie toque nada).
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.application.audit.service import AuditService
from backend.app.infrastructure.db.models.availability import DoctorRestrictionModel
from backend.app.infrastructure.db.models.doctors import DoctorModel
from backend.app.infrastructure.repositories.audit import AuditRepository

# Solo las ausencias que **bloquean** cambian el estado; una advertencia no saca a nadie.
BLOCKING_SEVERITY = "hard_block"


def today_utc() -> date:
    """El "hoy" del sistema. Se usa el mismo criterio que el recordatorio de reintegro."""
    return datetime.now(UTC).date()


def current_absence(
    session: Session, doctor_id: str, *, on_date: date | None = None
) -> DoctorRestrictionModel | None:
    """La ausencia **vigente** de un médico ese día, si tiene alguna.

    Vigente = no levantada, que ya empezó y que no ha terminado. Si hay varias, se devuelve
    la que empezó más tarde, que es la que explica mejor por qué no está.
    """
    on_date = on_date or today_utc()
    stmt = (
        select(DoctorRestrictionModel)
        .where(
            DoctorRestrictionModel.doctor_id == doctor_id,
            DoctorRestrictionModel.lifted_at.is_(None),
            DoctorRestrictionModel.severity == BLOCKING_SEVERITY,
            DoctorRestrictionModel.starts_at <= on_date,
        )
        .order_by(DoctorRestrictionModel.starts_at.desc())
    )
    for restriction in session.scalars(stmt):
        if restriction.ends_at is None or restriction.ends_at >= on_date:
            return restriction
    return None


def sync_service_state(
    session: Session,
    *,
    doctor_ids: list[str] | None = None,
    actor_id: str | None = None,
) -> list[str]:
    """Recalcula `service_active` (y el motivo y el detalle) desde las ausencias vigentes.

    Devuelve los ids de los médicos cuyo estado **cambió**. Escribe un evento de auditoría
    por cada cambio, con actor `Sistema` si no lo provocó una persona: quien mire el
    historial tiene que poder entender por qué el médico salió o volvió.

    Es idempotente: correrlo dos veces seguidas no cambia nada la segunda vez.
    """
    # **Antes de consultar**, se vuelca lo que esté pendiente: quien llama acaba de registrar,
    # editar o levantar una ausencia, y la consulta tiene que ver ese cambio. La sesión de la
    # aplicación trabaja con `autoflush` apagado, así que sin este flush el recálculo leería el
    # estado anterior y el flag se quedaría un paso por detrás. (Se destapó verificando en
    # producción con un servicio sin auditoría: el flush del evento de auditoría lo tapaba.)
    session.flush()

    stmt = select(DoctorModel).where(DoctorModel.deleted_at.is_(None))
    if doctor_ids is not None:
        if not doctor_ids:
            return []
        stmt = stmt.where(DoctorModel.id.in_(doctor_ids))

    doctors = list(session.scalars(stmt))
    if not doctors:
        return []

    today = today_utc()
    changed: list[str] = []
    for doctor in doctors:
        absence = current_absence(session, doctor.id, on_date=today)
        should_be_active = absence is None
        if doctor.service_active == should_be_active:
            continue

        doctor.service_active = should_be_active
        if should_be_active:
            # Vuelve: se limpia el motivo, que ya no explica nada.
            doctor.service_inactive_reason_id = None
            doctor.service_inactive_detail = None
        else:
            # El motivo y el detalle se copian de la ausencia vigente para que la vista por
            # departamento siga explicando por qué no está (antes solo los llenaba el botón).
            doctor.service_inactive_reason_id = absence.reason_id if absence else None
            doctor.service_inactive_detail = absence.description if absence else None
        doctor.updated_at = datetime.now(UTC)
        changed.append(doctor.id)

    if not changed:
        return []

    session.flush()
    audit = AuditService(AuditRepository(session))
    for doctor in doctors:
        if doctor.id not in changed:
            continue
        if doctor.service_active:
            audit.log_doctor_service_reactivated(actor_id=actor_id, doctor=doctor)
        else:
            audit.log_doctor_service_deactivated(actor_id=actor_id, doctor=doctor)

    return changed
