import logging
from datetime import UTC, datetime, timedelta

from backend.app.application.confirmations.service import ConfirmationRequestService
from backend.app.application.notifications.service import NotificationService
from backend.app.application.notifications.templates import (
    render_initial_assignment,
    render_mission_details_updated,
    render_mission_participant,
    render_mission_participant_added,
    render_mission_participant_removed,
    render_mission_summary_encargado,
    render_service_assignment_added,
    render_service_assignment_removed,
    render_service_assignment_updated,
)
from backend.app.infrastructure.repositories.doctors import DoctorRepository

logger = logging.getLogger(__name__)


def _with_whatsapp_confirmation(message: str) -> str:
    return f"{message}\n\nResponda 1 para confirmar su turno."


class NotificationTriggers:
    """Queues notifications in response to domain events."""

    def __init__(
        self,
        notification_service: NotificationService,
        doctor_repo: DoctorRepository,
        confirmation_service: ConfirmationRequestService | None = None,
        confirmation_due_hours: int = 12,
    ) -> None:
        self.notification_service = notification_service
        self.doctor_repo = doctor_repo
        self.confirmation_service = confirmation_service
        self.confirmation_due_hours = confirmation_due_hours

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
                        "message": _with_whatsapp_confirmation(message),
                        "confirmation_request_id": confirmation.id,
                    }
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
        from backend.app.infrastructure.db.models.catalogs import ServiceAreaModel

        count = 0
        for assignment in assignments:
            try:
                doctor = self.doctor_repo.get_by_id(assignment.doctor_id)
                phone = doctor.whatsapp_phone if doctor else None
                # Resolver display_name del área — el repo puede tener .session (prod) o no (test)
                db_session = getattr(self.doctor_repo, 'session', None)
                if db_session:
                    area = db_session.get(ServiceAreaModel, assignment.service_area_id)
                    area_name = area.display_name if area else assignment.service_area_id
                else:
                    area_name = assignment.service_area_id
                service_start = str(assignment.service_start_at) if getattr(assignment, 'service_start_at', None) else None
                message = render_initial_assignment(
                    service_date=str(assignment.service_date),
                    service_area=area_name,
                    service_start=service_start,
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
                        "message": _with_whatsapp_confirmation(message),
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

    def on_calendar_assignment_added_after_approval(
        self,
        *,
        actor_id: str,
        assignment,
        service_area_name: str,
    ) -> int:
        message = render_service_assignment_added(
            service_date=str(assignment.service_date),
            service_area=service_area_name,
            service_start=None,
        )
        return self._queue_service_change(
            actor_id=actor_id,
            assignment=assignment,
            notification_type="service_assignment_added",
            idempotency_key=f"service_change_added:{assignment.id}:{assignment.doctor_id}",
            message=message,
            create_confirmation=True,
        )

    def on_calendar_assignment_removed_after_approval(
        self,
        *,
        actor_id: str,
        assignment,
        service_area_name: str,
    ) -> int:
        message = render_service_assignment_removed(
            service_date=str(assignment.service_date),
            service_area=service_area_name,
            service_start=None,
        )
        return self._queue_service_change(
            actor_id=actor_id,
            assignment=assignment,
            notification_type="service_assignment_removed",
            idempotency_key=f"service_change_removed:{assignment.id}:{assignment.doctor_id}",
            message=message,
            create_confirmation=False,
        )

    def on_calendar_assignment_updated_after_approval(
        self,
        *,
        actor_id: str,
        assignment,
        service_area_name: str,
    ) -> int:
        message = render_service_assignment_updated(
            service_date=str(assignment.service_date),
            service_area=service_area_name,
            service_start=None,
        )
        return self._queue_service_change(
            actor_id=actor_id,
            assignment=assignment,
            notification_type="service_assignment_updated",
            idempotency_key=f"service_change_updated:{assignment.id}:{assignment.doctor_id}",
            message=message,
            create_confirmation=True,
        )

    def _queue_service_change(
        self,
        *,
        actor_id: str,
        assignment,
        notification_type: str,
        idempotency_key: str,
        message: str,
        create_confirmation: bool,
    ) -> int:
        try:
            doctor = self.doctor_repo.get_by_id(assignment.doctor_id)
            phone = doctor.whatsapp_phone if doctor else None
            notification = self.notification_service.queue(
                notification_type=notification_type,
                idempotency_key=idempotency_key,
                recipient_doctor_id=assignment.doctor_id,
                recipient_phone=phone,
                payload={"message": message},
                assignment_id=assignment.id,
                created_by=actor_id,
            )
            if create_confirmation and self.confirmation_service is not None:
                confirmation = self.confirmation_service.create_request(
                    confirmation_type="service",
                    idempotency_key=f"service_change:{assignment.id}:{assignment.doctor_id}",
                    doctor_id=assignment.doctor_id,
                    notification_id=notification.id,
                    assignment_id=assignment.id,
                    due_at=self._confirmation_due_at(),
                    created_by=actor_id,
                )
                notification.payload = {
                    **(notification.payload or {}),
                    "message": _with_whatsapp_confirmation(message),
                    "confirmation_request_id": confirmation.id,
                }
            return 1
        except Exception:
            logger.warning(
                "Failed to queue service change notification for assignment %s",
                getattr(assignment, "id", None),
                exc_info=True,
            )
            return 0

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
                notification = self.notification_service.queue(
                    notification_type="mission_participant",
                    idempotency_key=f"mission_participant:{mission.id}:{participant.doctor_id}",
                    recipient_doctor_id=participant.doctor_id,
                    recipient_phone=phone,
                    payload={"message": message},
                    mission_id=mission.id,
                    created_by=actor_id,
                )
                if self.confirmation_service is not None:
                    confirmation = self.confirmation_service.create_request(
                        confirmation_type="mission",
                        idempotency_key=f"mission:{mission.id}:{participant.doctor_id}",
                        doctor_id=participant.doctor_id,
                        notification_id=notification.id,
                        mission_id=mission.id,
                        due_at=self._confirmation_due_at(),
                        created_by=actor_id,
                    )
                    notification.payload = {
                        **(notification.payload or {}),
                        "message": _with_whatsapp_confirmation(message),
                        "confirmation_request_id": confirmation.id,
                    }
                count += 1
            except Exception:
                logger.warning(
                    "Failed to queue mission notification for participant %s",
                    participant.doctor_id,
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

    def on_mission_participants_changed(
        self,
        *,
        actor_id: str,
        mission,
        added_participants: list,
        removed_participants: list,
    ) -> int:
        count = 0
        mission_date = str(mission.mission_date)

        for participant in removed_participants:
            try:
                doctor = self.doctor_repo.get_by_id(participant.doctor_id)
                phone = doctor.whatsapp_phone if doctor else None
                message = render_mission_participant_removed(
                    mission_date=mission_date,
                    location=mission.location,
                    description=mission.description,
                )
                self.notification_service.queue(
                    notification_type="mission_participant_removed",
                    idempotency_key=f"mission_removed:{mission.id}:{participant.id}:{participant.doctor_id}",
                    recipient_doctor_id=participant.doctor_id,
                    recipient_phone=phone,
                    payload={"message": message},
                    mission_id=mission.id,
                    created_by=actor_id,
                )
                count += 1
            except Exception:
                logger.warning(
                    "Failed to queue mission removal notification for participant %s",
                    getattr(participant, "doctor_id", None),
                    exc_info=True,
                )

        for participant in added_participants:
            try:
                doctor = self.doctor_repo.get_by_id(participant.doctor_id)
                phone = doctor.whatsapp_phone if doctor else None
                message = render_mission_participant_added(
                    mission_date=mission_date,
                    location=mission.location,
                    description=mission.description,
                    mission_start=None,
                )
                notification = self.notification_service.queue(
                    notification_type="mission_participant_added",
                    idempotency_key=f"mission_added:{mission.id}:{participant.id}:{participant.doctor_id}",
                    recipient_doctor_id=participant.doctor_id,
                    recipient_phone=phone,
                    payload={"message": message},
                    mission_id=mission.id,
                    created_by=actor_id,
                )
                if self.confirmation_service is not None:
                    confirmation = self.confirmation_service.create_request(
                        confirmation_type="mission",
                        idempotency_key=f"mission_change:{mission.id}:{participant.id}",
                        doctor_id=participant.doctor_id,
                        notification_id=notification.id,
                        mission_id=mission.id,
                        due_at=self._confirmation_due_at(),
                        created_by=actor_id,
                    )
                    notification.payload = {
                        **(notification.payload or {}),
                        "message": _with_whatsapp_confirmation(message),
                        "confirmation_request_id": confirmation.id,
                    }
                count += 1
            except Exception:
                logger.warning(
                    "Failed to queue mission add notification for participant %s",
                    getattr(participant, "doctor_id", None),
                    exc_info=True,
                )

        return count

    def on_mission_details_changed(
        self,
        *,
        actor_id: str,
        mission,
        participants: list,
    ) -> int:
        count = 0
        message = render_mission_details_updated(
            mission_date=str(mission.mission_date),
            location=mission.location,
            description=mission.description,
            mission_start=None,
        )
        change_marker = int(mission.updated_at.timestamp()) if mission.updated_at else "pending"
        for participant in participants:
            try:
                doctor = self.doctor_repo.get_by_id(participant.doctor_id)
                phone = doctor.whatsapp_phone if doctor else None
                self.notification_service.queue(
                    notification_type="mission_details_updated",
                    idempotency_key=f"mission_details:{mission.id}:{change_marker}:{participant.doctor_id}",
                    recipient_doctor_id=participant.doctor_id,
                    recipient_phone=phone,
                    payload={"message": message},
                    mission_id=mission.id,
                    created_by=actor_id,
                )
                count += 1
            except Exception:
                logger.warning(
                    "Failed to queue mission update notification for participant %s",
                    getattr(participant, "doctor_id", None),
                    exc_info=True,
                )
        return count

    def _confirmation_due_at(self):
        return datetime.now(UTC) + timedelta(hours=self.confirmation_due_hours)
