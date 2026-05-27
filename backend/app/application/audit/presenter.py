from sqlalchemy.orm import Session

from backend.app.infrastructure.db.models.calendars import CalendarAssignmentModel, CalendarModel
from backend.app.infrastructure.db.models.catalogs import (
    DeactivationReasonModel,
    DepartmentModel,
    RankModel,
    ServiceAreaModel,
)
from backend.app.infrastructure.db.models.doctors import DoctorModel
from backend.app.infrastructure.db.models.missions import MissionAssignmentModel
from backend.app.infrastructure.db.models.user import UserModel
from backend.app.schemas.audit import AuditEventRead


ACTION_DETAIL_LABELS = {
    "doctor_created": "Se creó el médico.",
    "doctor_updated": "Se actualizó la información del médico.",
    "doctor_service_deactivated": "Se desactivó el médico para servicios.",
    "doctor_service_reactivated": "Se reactivó el médico para servicios.",
    "availability_set": "Se cargó disponibilidad.",
    "restriction_added": "Se añadió una restricción.",
    "restriction_lifted": "Se levantó una restricción.",
    "user_created": "Se creó un usuario.",
    "password_reset": "Se restableció la contraseña.",
    "password_changed": "Se cambió la contraseña.",
    "login_failed": "Intento de inicio de sesión fallido.",
    "calendar_created": "Se creó un calendario.",
    "calendar_approved": "Se aprobó un calendario.",
    "calendar_new_version": "Se generó una nueva versión del calendario.",
    "calendar_deleted": "Se eliminó un calendario.",
    "assignment_added": "Se agregó una asignación de servicio.",
    "assignment_removed": "Se eliminó una asignación de servicio.",
    "assignment_replaced": "Se reemplazó una asignación de servicio.",
    "mission_ranking_generated": "Se generó el ranking de candidatos a misiones.",
    "mission_confirmed": "Se confirmó una misión.",
}

FIELD_LABELS = {
    "name": "nombre",
    "sex": "sexo",
    "rank_id": "rango",
    "department_id": "departamento",
    "notes": "notas",
    "active": "activo en sistema",
    "service_active": "activo para servicio",
    "participa_misiones": "misiones",
    "whatsapp_phone": "WhatsApp",
    "service_inactive_reason_id": "motivo de inactividad",
    "service_inactive_detail": "detalle de inactividad",
    "monthly_service_target": "meta mensual",
    "monthly_service_max": "máximo mensual",
    "availability_mode": "modo de disponibilidad",
}

MONTH_LABELS = {
    1: "enero",
    2: "febrero",
    3: "marzo",
    4: "abril",
    5: "mayo",
    6: "junio",
    7: "julio",
    8: "agosto",
    9: "septiembre",
    10: "octubre",
    11: "noviembre",
    12: "diciembre",
}


def _month_year(snapshot: dict | None) -> str | None:
    if not snapshot:
        return None
    month = snapshot.get("month")
    year = snapshot.get("year")
    if isinstance(month, int) and isinstance(year, int):
        return f"{MONTH_LABELS.get(month, str(month)).capitalize()} {year}"
    return None


def _value_label(value) -> str:
    if value is True:
        return "Sí"
    if value is False:
        return "No"
    if value == "male":
        return "Masculino"
    if value == "female":
        return "Femenino"
    if value is None:
        return "Sin especificar"
    return str(value)


class AuditPresenter:
    def __init__(self, session: Session) -> None:
        self.session = session
        self._users: dict[str, UserModel | None] = {}
        self._doctors: dict[str, DoctorModel | None] = {}
        self._ranks: dict[str, RankModel | None] = {}
        self._departments: dict[str, DepartmentModel | None] = {}
        self._reasons: dict[str, DeactivationReasonModel | None] = {}
        self._areas: dict[str, ServiceAreaModel | None] = {}
        self._calendars: dict[str, CalendarModel | None] = {}
        self._assignments: dict[str, CalendarAssignmentModel | None] = {}
        self._missions: dict[str, MissionAssignmentModel | None] = {}

    def present(self, event) -> AuditEventRead:
        item = AuditEventRead.model_validate(event)
        snapshot = event.after_snapshot or event.before_snapshot or event.metadata_ or {}
        item.actor_display = self._actor_display(event.actor_id)
        item.entity_display = self._entity_display(event.entity_type, event.entity_id, snapshot)
        item.detail_summary = self._detail_summary(event.action_type, snapshot)
        return item

    def _cached_get(self, cache: dict, model, entity_id: str | None):
        if not entity_id:
            return None
        if entity_id not in cache:
            cache[entity_id] = self.session.get(model, entity_id)
        return cache[entity_id]

    def _actor_display(self, actor_id: str | None) -> str:
        if actor_id is None:
            return "Sistema"
        user = self._cached_get(self._users, UserModel, actor_id)
        if user is None:
            return "Usuario del sistema"
        return f"{user.name} ({user.email})"

    def _doctor_name(self, doctor_id: str | None) -> str | None:
        doctor = self._cached_get(self._doctors, DoctorModel, doctor_id)
        return doctor.name if doctor else None

    def _catalog_label(self, field: str, value: str | None) -> str:
        if not value:
            return "Sin especificar"
        if field == "rank_id":
            rank = self._cached_get(self._ranks, RankModel, value)
            return rank.name if rank else value
        if field == "department_id":
            department = self._cached_get(self._departments, DepartmentModel, value)
            return department.name if department else value
        if field == "service_inactive_reason_id":
            reason = self._cached_get(self._reasons, DeactivationReasonModel, value)
            return reason.display_name if reason else value
        if field == "service_area_id":
            area = self._cached_get(self._areas, ServiceAreaModel, value)
            return area.display_name if area else value
        return _value_label(value)

    def _field_value(self, field: str, value) -> str:
        if field in {"rank_id", "department_id", "service_inactive_reason_id", "service_area_id"}:
            return self._catalog_label(field, value)
        return _value_label(value)

    def _entity_display(self, entity_type: str, entity_id: str | None, snapshot: dict) -> str:
        if entity_type == "doctor":
            name = self._doctor_name(entity_id) or snapshot.get("name")
            return f"Médico: {name}" if name else "Médico"
        if entity_type == "user":
            user = self._cached_get(self._users, UserModel, entity_id)
            name = user.name if user else snapshot.get("name")
            email = user.email if user else snapshot.get("email")
            if name and email:
                return f"Usuario: {name} ({email})"
            return f"Usuario: {name or email}" if name or email else "Usuario"
        if entity_type == "calendar":
            calendar = self._cached_get(self._calendars, CalendarModel, entity_id)
            if calendar:
                month = MONTH_LABELS.get(calendar.month, calendar.month)
                return f"Calendario: {str(month).capitalize()} {calendar.year}"
            period = _month_year(snapshot)
            return f"Calendario: {period}" if period else "Calendario"
        if entity_type == "assignment":
            assignment = self._cached_get(self._assignments, CalendarAssignmentModel, entity_id)
            doctor_id = snapshot.get("doctor_id") or (assignment.doctor_id if assignment else None)
            doctor_name = self._doctor_name(doctor_id)
            service_date = snapshot.get("service_date") or (
                str(assignment.service_date) if assignment else None
            )
            if doctor_name and service_date:
                return f"Servicio: {doctor_name} - {service_date}"
            return "Asignación de servicio"
        if entity_type == "availability":
            doctor_name = self._doctor_name(snapshot.get("doctor_id"))
            return f"Disponibilidad: {doctor_name}" if doctor_name else "Disponibilidad"
        if entity_type == "restriction":
            doctor_name = self._doctor_name(snapshot.get("doctor_id"))
            return f"Restricción: {doctor_name}" if doctor_name else "Restricción"
        if entity_type == "mission":
            mission = self._cached_get(self._missions, MissionAssignmentModel, entity_id)
            mission_date = snapshot.get("mission_date") or (
                str(mission.mission_date) if mission else None
            )
            location = mission.location if mission else None
            if mission_date and location:
                return f"Misión: {mission_date} - {location}"
            return f"Misión: {mission_date}" if mission_date else "Misión"
        if entity_type == "mission_ranking":
            period = _month_year(snapshot)
            return f"Ranking de misiones: {period}" if period else "Ranking de misiones"
        return entity_type.replace("_", " ").capitalize()

    def _detail_summary(self, action_type: str, snapshot: dict) -> str:
        if action_type == "doctor_created":
            name = snapshot.get("name")
            sex = self._field_value("sex", snapshot.get("sex"))
            status = self._field_value("service_active", snapshot.get("service_active"))
            return f"Se creó el médico {name}. Sexo: {sex}. Activo para servicio: {status}."
        if action_type == "doctor_updated":
            fields = [
                f"{FIELD_LABELS.get(field, field)}: {self._field_value(field, value)}"
                for field, value in snapshot.items()
                if field not in {"id", "created_by", "updated_at"}
            ]
            return "Se actualizaron: " + "; ".join(fields[:4]) + ("." if fields else "")
        if action_type == "doctor_service_deactivated":
            reason = self._field_value(
                "service_inactive_reason_id", snapshot.get("service_inactive_reason_id")
            )
            detail = snapshot.get("service_inactive_detail")
            return f"Servicio desactivado. Motivo: {reason}." + (
                f" Detalle: {detail}." if detail else ""
            )
        if action_type == "doctor_service_reactivated":
            return "Servicio reactivado. El médico vuelve a estar disponible para servicios y misiones."
        if action_type == "availability_set":
            period = _month_year(snapshot)
            return f"Disponibilidad cargada para {period}." if period else "Disponibilidad cargada."
        if action_type == "restriction_added":
            starts_at = snapshot.get("starts_at")
            ends_at = snapshot.get("ends_at") or "sin fecha final"
            severity = snapshot.get("severity")
            return (
                f"Restricción añadida desde {starts_at} hasta {ends_at}. "
                f"Severidad: {_value_label(severity)}."
            )
        if action_type == "restriction_lifted":
            return f"Restricción levantada el {snapshot.get('lifted_at', 'momento registrado')}."
        if action_type == "user_created":
            return (
                f"Usuario creado: {snapshot.get('name')} ({snapshot.get('email')}). "
                f"Rol: {snapshot.get('role')}."
            )
        if action_type in {"password_reset", "password_changed"}:
            return ACTION_DETAIL_LABELS[action_type]
        if action_type == "login_failed":
            locked = " La cuenta fue bloqueada temporalmente." if snapshot.get("locked") else ""
            return "Intento de inicio de sesión fallido." + locked
        if action_type in {
            "calendar_created",
            "calendar_approved",
            "calendar_new_version",
            "calendar_deleted",
        }:
            period = _month_year(snapshot)
            base = ACTION_DETAIL_LABELS[action_type]
            version = snapshot.get("version_number")
            reason = snapshot.get("reason")
            return (
                f"{base} {period or ''}".strip()
                + (f" Versión: {version}." if version else ".")
                + (f" Motivo: {reason}." if reason else "")
            )
        if action_type in {"assignment_added", "assignment_replaced"}:
            area = self._field_value("service_area_id", snapshot.get("service_area_id"))
            return (
                f"{ACTION_DETAIL_LABELS[action_type]} "
                f"Fecha: {snapshot.get('service_date')}. Área: {area}."
            )
        if action_type == "assignment_removed":
            return ACTION_DETAIL_LABELS[action_type]
        if action_type == "mission_ranking_generated":
            period = _month_year(snapshot)
            return f"Ranking generado para {period}." if period else ACTION_DETAIL_LABELS[action_type]
        if action_type == "mission_confirmed":
            return (
                f"Misión confirmada para el {snapshot.get('mission_date')}. "
                f"Estado: {_value_label(snapshot.get('status'))}."
            )
        return ACTION_DETAIL_LABELS.get(action_type, "Evento registrado en auditoría.")
