import uuid
from contextvars import ContextVar
from datetime import UTC, datetime

from backend.app.application.audit.errors import AuditError  # noqa: F401
from backend.app.infrastructure.db.models.audit import AuditEventModel
from backend.app.infrastructure.repositories.audit import AuditRepository

# Context variable populated by middleware for correlating audit events
_request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)


def get_current_request_id() -> str | None:
    """Return the current request_id (set by middleware), if any."""
    return _request_id_ctx.get()


def set_current_request_id(value: str | None) -> None:
    """Set the request_id for the current request context."""
    if value is not None:
        _request_id_ctx.set(value)


class AuditService:
    def __init__(self, audit_repo: AuditRepository) -> None:
        self.repo = audit_repo

    def _create(
        self,
        *,
        actor_id: str | None,
        action_type: str,
        entity_type: str,
        entity_id: str | None,
        before: dict | None = None,
        after: dict | None = None,
        metadata: dict | None = None,
    ) -> AuditEventModel:
        event = AuditEventModel(
            id=str(uuid.uuid4()),
            actor_id=actor_id,
            action_type=action_type,
            entity_type=entity_type,
            entity_id=entity_id,
            occurred_at=datetime.now(UTC),
            request_id=_request_id_ctx.get(),
            before_snapshot=before,
            after_snapshot=after,
            metadata_=metadata,
        )
        try:
            self.repo.add(event)
        except Exception:
            pass  # audit must not break business operations
        return event

    # --- Doctor events ---

    def log_doctor_created(self, *, actor_id: str, doctor) -> AuditEventModel:
        return self._create(
            actor_id=actor_id,
            action_type="doctor_created",
            entity_type="doctor",
            entity_id=doctor.id,
            after={"name": doctor.name, "sex": doctor.sex, "service_active": doctor.service_active},
        )

    def log_doctor_updated(self, *, actor_id: str, doctor, changed_fields: dict) -> AuditEventModel:
        return self._create(
            actor_id=actor_id,
            action_type="doctor_updated",
            entity_type="doctor",
            entity_id=doctor.id,
            after=changed_fields,
        )

    def log_doctor_service_deactivated(self, *, actor_id: str, doctor) -> AuditEventModel:
        return self._create(
            actor_id=actor_id,
            action_type="doctor_service_deactivated",
            entity_type="doctor",
            entity_id=doctor.id,
            after={
                "service_active": False,
                "service_inactive_reason_id": doctor.service_inactive_reason_id,
                "service_inactive_detail": doctor.service_inactive_detail,
            },
        )

    def log_doctor_service_reactivated(self, *, actor_id: str, doctor) -> AuditEventModel:
        return self._create(
            actor_id=actor_id,
            action_type="doctor_service_reactivated",
            entity_type="doctor",
            entity_id=doctor.id,
            after={"service_active": True},
        )

    def log_doctor_deleted(self, *, actor_id: str, doctor) -> AuditEventModel:
        return self._create(
            actor_id=actor_id,
            action_type="doctor_deleted",
            entity_type="doctor",
            entity_id=doctor.id,
            before={"name": doctor.name, "sex": doctor.sex, "service_active": doctor.service_active},
        )

    # --- Availability events ---

    def log_availability_set(self, *, actor_id: str, availability) -> AuditEventModel:
        return self._create(
            actor_id=actor_id,
            action_type="availability_set",
            entity_type="availability",
            entity_id=availability.id,
            after={
                "doctor_id": availability.doctor_id,
                "availability_type": availability.availability_type,
                "year": availability.year,
                "month": availability.month,
            },
        )

    def log_restriction_added(self, *, actor_id: str, restriction) -> AuditEventModel:
        return self._create(
            actor_id=actor_id,
            action_type="restriction_added",
            entity_type="restriction",
            entity_id=restriction.id,
            after={
                "doctor_id": restriction.doctor_id,
                "restriction_type": restriction.restriction_type,
                "severity": restriction.severity,
                "starts_at": str(restriction.starts_at),
                "ends_at": str(restriction.ends_at) if restriction.ends_at else None,
            },
        )

    def log_restriction_lifted(self, *, actor_id: str, restriction) -> AuditEventModel:
        return self._create(
            actor_id=actor_id,
            action_type="restriction_lifted",
            entity_type="restriction",
            entity_id=restriction.id,
            after={"doctor_id": restriction.doctor_id, "lifted_at": str(restriction.lifted_at)},
        )

    # --- Account events ---

    def log_user_created(self, *, actor_id: str | None, user) -> AuditEventModel:
        return self._create(
            actor_id=actor_id,
            action_type="user_created",
            entity_type="user",
            entity_id=user.id,
            after={"name": user.name, "email": user.email, "role": user.role},
        )

    def log_password_reset(self, *, actor_id: str, user) -> AuditEventModel:
        return self._create(
            actor_id=actor_id,
            action_type="password_reset",
            entity_type="user",
            entity_id=user.id,
            after={"must_change_password": True},
        )

    def log_password_changed(self, *, actor_id: str, user) -> AuditEventModel:
        return self._create(
            actor_id=actor_id,
            action_type="password_changed",
            entity_type="user",
            entity_id=user.id,
            after={"must_change_password": False},
        )

    def log_login_failed(self, *, email: str, locked: bool = False) -> AuditEventModel:
        return self._create(
            actor_id=None,
            action_type="login_failed",
            entity_type="user",
            entity_id=None,
            metadata={"email_hint": email[:3] + "***", "locked": locked},
        )

    def log_user_updated(self, *, actor_id: str, user, changed_fields: dict) -> AuditEventModel:
        return self._create(
            actor_id=actor_id,
            action_type="user_updated",
            entity_type="user",
            entity_id=user.id,
            after=changed_fields,
        )

    def log_user_deleted(self, *, actor_id: str, user) -> AuditEventModel:
        return self._create(
            actor_id=actor_id,
            action_type="user_deleted",
            entity_type="user",
            entity_id=user.id,
            before={"name": user.name, "email": user.email, "role": user.role},
        )

    # --- Calendar events ---

    def log_calendar_created(self, *, actor_id: str, calendar) -> AuditEventModel:
        return self._create(
            actor_id=actor_id,
            action_type="calendar_created",
            entity_type="calendar",
            entity_id=calendar.id,
            after={"year": calendar.year, "month": calendar.month, "status": calendar.status},
        )

    def log_calendar_approved(self, *, actor_id: str, calendar, version) -> AuditEventModel:
        return self._create(
            actor_id=actor_id,
            action_type="calendar_approved",
            entity_type="calendar",
            entity_id=calendar.id,
            after={
                "status": calendar.status,
                "version_number": version.version_number,
                "version_id": version.id,
            },
        )

    def log_calendar_new_version(self, *, actor_id: str, calendar, version) -> AuditEventModel:
        return self._create(
            actor_id=actor_id,
            action_type="calendar_new_version",
            entity_type="calendar",
            entity_id=calendar.id,
            after={
                "status": calendar.status,
                "version_number": version.version_number,
                "version_id": version.id,
                "reason": version.reason,
            },
        )

    def log_calendar_unlocked(self, *, actor_id: str, calendar, version) -> AuditEventModel:
        return self._create(
            actor_id=actor_id,
            action_type="calendar_unlocked",
            entity_type="calendar",
            entity_id=calendar.id,
            before={"status": "approved"},
            after={
                "status": calendar.status,
                "version_number": version.version_number,
                "version_id": version.id,
            },
        )

    def log_calendar_deleted(self, *, actor_id: str, calendar) -> AuditEventModel:
        return self._create(
            actor_id=actor_id,
            action_type="calendar_deleted",
            entity_type="calendar",
            entity_id=calendar.id,
            before={"year": calendar.year, "month": calendar.month, "status": calendar.status},
        )

    # --- Assignment events ---

    def log_assignment_added(self, *, actor_id: str, assignment) -> AuditEventModel:
        return self._create(
            actor_id=actor_id,
            action_type="assignment_added",
            entity_type="assignment",
            entity_id=assignment.id,
            after={
                "calendar_version_id": assignment.calendar_version_id,
                "doctor_id": assignment.doctor_id,
                "service_date": str(assignment.service_date),
                "service_area_id": assignment.service_area_id,
                "override_justification": assignment.override_justification,
            },
        )

    def log_assignment_removed(self, *, actor_id: str, assignment_id: str) -> AuditEventModel:
        return self._create(
            actor_id=actor_id,
            action_type="assignment_removed",
            entity_type="assignment",
            entity_id=assignment_id,
        )

    def log_assignment_replaced(self, *, actor_id: str, assignment) -> AuditEventModel:
        return self._create(
            actor_id=actor_id,
            action_type="assignment_replaced",
            entity_type="assignment",
            entity_id=assignment.id,
            after={
                "calendar_version_id": assignment.calendar_version_id,
                "doctor_id": assignment.doctor_id,
                "service_date": str(assignment.service_date),
                "service_area_id": assignment.service_area_id,
                "override_justification": assignment.override_justification,
            },
        )

    # --- Mission events ---

    def log_mission_ranking_generated(self, actor_id: str, ranking) -> AuditEventModel:
        return self._create(
            actor_id=actor_id,
            action_type="mission_ranking_generated",
            entity_type="mission_ranking",
            entity_id=ranking.id,
            after={
                "year": ranking.year,
                "month": ranking.month,
                "calendar_version_id": ranking.calendar_version_id,
                "generated_at": str(ranking.generated_at),
            },
        )

    def log_mission_confirmed(self, actor_id: str, mission) -> AuditEventModel:
        return self._create(
            actor_id=actor_id,
            action_type="mission_confirmed",
            entity_type="mission",
            entity_id=mission.id,
            after={
                "mission_date": str(mission.mission_date),
                "status": mission.status,
                "confirmed_by": mission.confirmed_by,
                "confirmed_at": str(mission.confirmed_at) if mission.confirmed_at else None,
            },
        )
