import logging
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from backend.app.application.notifications.service import NotificationService
from backend.app.application.notifications.templates import (
    render_initial_assignment,
    render_mission_participant,
    render_mission_summary_encargado,
)
from backend.app.infrastructure.repositories.doctors import DoctorRepository

logger = logging.getLogger(__name__)


class NotificationTriggers:
    """Queues notifications in response to domain events."""

    def __init__(
        self,
        notification_service: NotificationService,
        doctor_repo: DoctorRepository,
        confirmation_service=None,
    ) -> None:
        self.notification_service = notification_service
        self.doctor_repo = doctor_repo
        self.confirmation_service = confirmation_service

    @staticmethod
    def _with_confirmation_instructions(message: str, token: str, confirmation_type: str) -> str:
        suffix = (
            f"\n\nConfirme su disponibilidad usando el token: {token}"
            if confirmation_type == "service"
            else f"\n\nToken de confirmación: {token}"
        )
        return message + suffix

    @staticmethod
    def _confirmation_due_at() -> datetime:
        return datetime.now(UTC) + timedelta(days=3)

    def on_calendar_approved(
        self,
        *,
        actor_id: str,
        assignments: list,
    ) -> int:
        """Queue initial_assignment notifications for all assignments."""
        count = 0
        for assignment in assignments:
            try:
                doctor = self.doctor_repo.get_by_id(assignment.doctor_id)
                phone = doctor.whatsapp_phone if doctor else None
                message = render_initial_assignment(
                    service_date=str(assignment.service_date),
                    service_area=assignment.service_area_id,
                    service_start=None,
                )
                self.notification_service.queue(
                    notification_type="initial_assignment",
                    idempotency_key=f"assign:{assignment.id}",
                    recipient_doctor_id=assignment.doctor_id,
                    recipient_phone=phone,
                    payload={"message": message},
                    assignment_id=assignment.id,
                    created_by=actor_id,
                )
                count += 1
            except Exception:
                logger.warning(
                    "Failed to queue calendar notification for assignment %s", assignment.id,
                    exc_info=True,
                )
                continue
        return count

    def on_week_approved(
        self,
        *,
        actor_id: str,
        assignments: list,
        week,
    ) -> int:
        """Notify doctors assigned in a specific calendar week.

        Called when a single week is approved (not the whole calendar).
        Follows the same pattern as on_calendar_approved but scoped
        to one week's assignments.
        """
        count = 0
        for assignment in assignments:
            try:
                doctor = self.doctor_repo.get_by_id(assignment.doctor_id)
                phone = doctor.whatsapp_phone if doctor else None
                message = render_initial_assignment(
                    service_date=str(assignment.service_date),
                    service_area=assignment.service_area_id,
                    service_start=None,
                )
                notification = self.notification_service.queue(
                    notification_type="initial_assignment",
                    idempotency_key=f"assign:{assignment.id}",
                    recipient_doctor_id=assignment.doctor_id,
                    recipient_phone=phone,
                    payload={"message": message},
                    assignment_id=assignment.id,
                    created_by=actor_id,
                )
                if self.confirmation_service is not None:
                    confirmation = self.confirmation_service.create_request(
                        confirmation_type="service",
                        idempotency_key=f"service:{assignment.id}:{assignment.doctor_id}",
                        doctor_id=assignment.doctor_id,
                        notification_id=notification.id,
                        assignment_id=assignment.id,
                        due_at=self._confirmation_due_at(),
                        created_by=actor_id,
                    )
                    notification.payload = {
                        **(notification.payload or {}),
                        "message": self._with_confirmation_instructions(
                            message,
                            confirmation.response_token,
                            "service",
                        ),
                        "confirmation_request_id": confirmation.id,
                    }
                count += 1
            except Exception:
                logger.warning(
                    "Failed to queue week notification for assignment %s",
                    assignment.id,
                    exc_info=True,
                )
                continue
        return count

    def on_mission_confirmed(
        self,
        *,
        actor_id: str,
        mission,
        participants: list,
        encargado_phone: str | None,
    ) -> int:
        """Queue mission_participant notifications + encargado summary."""
        count = 0
        mission_date = str(mission.mission_date)

        for participant in participants:
            try:
                doctor = self.doctor_repo.get_by_id(participant.doctor_id)
                phone = doctor.whatsapp_phone if doctor else None
                message = render_mission_participant(
                    mission_date=mission_date,
                    location=mission.location,
                    description=mission.description,
                    mission_start=None,
                )
                self.notification_service.queue(
                    notification_type="mission_participant",
                    idempotency_key=f"mission_participant:{mission.id}:{participant.doctor_id}",
                    recipient_doctor_id=participant.doctor_id,
                    recipient_phone=phone,
                    payload={"message": message},
                    mission_id=mission.id,
                    created_by=actor_id,
                )
                count += 1
            except Exception:
                logger.warning(
                    "Failed to queue mission notification for participant %s", participant.doctor_id,
                    exc_info=True,
                )
                continue

        if encargado_phone:
            try:
                participant_names = [p.doctor_id for p in participants]
                message = render_mission_summary_encargado(
                    mission_date=mission_date,
                    location=mission.location,
                    description=mission.description,
                    participant_names=participant_names,
                )
                self.notification_service.queue(
                    notification_type="mission_summary",
                    idempotency_key=f"mission_summary:{mission.id}",
                    recipient_doctor_id=None,
                    recipient_phone=encargado_phone,
                    payload={"message": message},
                    mission_id=mission.id,
                    created_by=actor_id,
                )
                count += 1
            except Exception:
                logger.warning(
                    "Failed to queue mission summary notification for mission %s", mission.id,
                    exc_info=True,
                )

        return count
