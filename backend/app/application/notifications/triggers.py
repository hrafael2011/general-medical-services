import logging
from datetime import UTC, datetime, timedelta

from backend.app.application.confirmations.service import ConfirmationRequestService
from backend.app.application.notifications.service import NotificationService
from backend.app.application.notifications.templates import (
    _with_telegram_confirmation,
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


def _resolve_recipient_phone(doctor) -> str | None:
    """Return the best contact target for a doctor.

    Returns telegram_chat_id when available (Telegram is the primary
    notification channel).  Returns None when the doctor has no
    telegram_chat_id — whatsapp_phone numbers are not valid Telegram
    chat IDs and would produce 400 Bad Request.
    """
    if doctor is None:
        return None
    return getattr(doctor, "telegram_chat_id", None) or None


def _build_confirmation_message(message: str, doctor, confirmation) -> str | dict:
    """Build confirmation message payload — Telegram buttons or WhatsApp text.

    Returns a dict with inline keyboard button when the doctor has
    telegram_chat_id, otherwise a plain string with WhatsApp confirmation
    instructions.
    """
    chat_id = getattr(doctor, "telegram_chat_id", None)
    if chat_id:
        return _with_telegram_confirmation(message, confirmation)
    return _with_whatsapp_confirmation(message)


class NotificationTriggers:
    """Queues notifications in response to domain events."""

    def __init__(
        self,
        notification_service: NotificationService,
        doctor_repo: DoctorRepository,
        confirmation_service: ConfirmationRequestService | None = None,
        due_hours_before_service: int = 4,
        approval_grace_minutes: int = 0,
    ) -> None:
        self.notification_service = notification_service
        self.doctor_repo = doctor_repo
        self.confirmation_service = confirmation_service
        self.due_hours_before_service = due_hours_before_service
        self.approval_grace_minutes = approval_grace_minutes

    def _reactivate(self, assignments: list) -> None:
        """Re-aprobar reabre lo que un desbloqueo había cancelado.

        Sin esto, corregir un error y volver a aprobar deja a los médicos sin
        enterarse de la versión buena: la fila cancelada sigue cancelada.
        """
        assignment_ids = [assignment.id for assignment in assignments]
        self.notification_service.reactivate_for_assignments(assignment_ids)
        if self.confirmation_service is not None:
            self.confirmation_service.reactivate_for_assignments(assignment_ids)

    def _scheduled_for(self) -> datetime | None:
        """Hora de salida del aviso: el margen que da tiempo a arrepentirse."""
        if self.approval_grace_minutes <= 0:
            return None
        return datetime.now(UTC) + timedelta(minutes=self.approval_grace_minutes)

    def _resolve_area(self, assignment) -> tuple[str, datetime | None]:
        """Return the area display name and the service start time.

        The full-calendar approval used to send the area **UUID** and no time, so the
        doctor read something like "turno en d89219b3-…". The session is optional
        because week-trigger tests use a fake repo without one; in that case the area
        id is the best available label.
        """
        from backend.app.infrastructure.db.models.catalogs import ServiceAreaModel

        session = getattr(self.doctor_repo, "session", None)
        area = session.get(ServiceAreaModel, assignment.service_area_id) if session else None
        area_name = area.display_name if area is not None else str(assignment.service_area_id)

        start = getattr(assignment, "service_start_at", None)
        if start is None and getattr(assignment, "service_date", None) is not None:
            hour = area.start_hour if area is not None else 7
            start = datetime(
                assignment.service_date.year,
                assignment.service_date.month,
                assignment.service_date.day,
                hour,
                0,
                0,
                tzinfo=UTC,
            )
        return area_name, start

    def on_calendar_approved(
        self,
        *,
        actor_id: str,
        assignments: list,
    ) -> int:
        """Queue initial_assignment notifications for all assignments."""
        self._reactivate(assignments)
        count = 0
        for assignment in assignments:
            # El id se lee ANTES del try. Dentro del `except` la instancia puede
            # estar inutilizable (sesión expirada o revertida por otro); si esa
            # lectura lanza, la excepción reemplaza a la original y tumba la
            # aprobación entera por un fallo al formatear un log.
            assignment_id = assignment.id
            try:
                doctor = self.doctor_repo.get_by_id(assignment.doctor_id)
                phone = _resolve_recipient_phone(doctor)
                area_name, service_start = self._resolve_area(assignment)
                message = render_initial_assignment(
                    service_date=str(assignment.service_date),
                    service_area=area_name,
                    service_start=(
                        service_start.strftime("%I:%M %p") if service_start else None
                    ),
                )
                notification = self.notification_service.queue(
                    notification_type="initial_assignment",
                    idempotency_key=f"assign:{assignment_id}",
                    recipient_doctor_id=assignment.doctor_id,
                    recipient_phone=phone,
                    payload={"message": message},
                    assignment_id=assignment_id,
                    scheduled_for=self._scheduled_for(),
                    created_by=actor_id,
                )
                if self.confirmation_service is not None:
                    confirmation = self.confirmation_service.create_request(
                        confirmation_type="service",
                        idempotency_key=f"service:{assignment.id}:{assignment.doctor_id}",
                        doctor_id=assignment.doctor_id,
                        notification_id=notification.id,
                        assignment_id=assignment.id,
                        due_at=self._confirmation_due_at(service_start),
                        created_by=actor_id,
                    )
                    notification.payload = {
                        **(notification.payload or {}),
                        "message": _build_confirmation_message(message, doctor, confirmation),
                        "confirmation_request_id": confirmation.id,
                    }
                count += 1
            except Exception:
                logger.warning(
                    "Failed to queue calendar notification for assignment %s", assignment_id,
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
        self._reactivate(assignments)
        count = 0
        for assignment in assignments:
            # El id se lee ANTES del try: dentro del `except` la instancia puede
            # estar inutilizable y la lectura del log tumbaría la aprobación.
            assignment_id = assignment.id
            try:
                doctor = self.doctor_repo.get_by_id(assignment.doctor_id)
                phone = _resolve_recipient_phone(doctor)
                area_name, start_dt = self._resolve_area(assignment)
                message = render_initial_assignment(
                    service_date=str(assignment.service_date),
                    service_area=area_name,
                    service_start=start_dt.strftime("%I:%M %p") if start_dt else None,
                )
                notification = self.notification_service.queue(
                    notification_type="initial_assignment",
                    idempotency_key=f"assign:{assignment_id}",
                    recipient_doctor_id=assignment.doctor_id,
                    recipient_phone=phone,
                    payload={"message": message},
                    assignment_id=assignment_id,
                    scheduled_for=self._scheduled_for(),
                    created_by=actor_id,
                )
                if self.confirmation_service is not None:
                    confirmation = self.confirmation_service.create_request(
                        confirmation_type="service",
                        idempotency_key=f"service:{assignment_id}:{assignment.doctor_id}",
                        doctor_id=assignment.doctor_id,
                        notification_id=notification.id,
                        assignment_id=assignment.id,
                        due_at=self._confirmation_due_at(start_dt),
                        created_by=actor_id,
                    )
                    notification.payload = {
                        **(notification.payload or {}),
                        "message": _build_confirmation_message(message, doctor, confirmation),
                        "confirmation_request_id": confirmation.id,
                    }
                count += 1
            except Exception:
                logger.warning(
                    "Failed to queue week notification for assignment %s",
                    assignment_id,
                    exc_info=True,
                )
                continue
        return count

    def on_week_unapproved(self, *, actor_id: str, assignments: list) -> dict[str, int]:
        """Deshace lo que encoló `on_week_approved`.

        Solo alcanza a lo que no ha salido: un aviso ya enviado no se puede
        recoger, y uno en vuelo podría duplicarse.
        """
        assignment_ids = [assignment.id for assignment in assignments]
        notification_ids = self.notification_service.cancel_for_assignments(assignment_ids)
        confirmation_ids: list[str] = []
        if self.confirmation_service is not None:
            confirmation_ids = self.confirmation_service.cancel_for_assignments(assignment_ids)
        logger.info(
            "Unapproval by %s cancelled %d notifications and %d confirmations",
            actor_id,
            len(notification_ids),
            len(confirmation_ids),
        )
        return {
            "notifications": len(notification_ids),
            "confirmations": len(confirmation_ids),
        }

    def on_calendar_assignment_added_after_approval(
        self,
        *,
        actor_id: str,
        assignment,
        service_area_name: str,
    ) -> int:
        resolved_name, start_dt = self._resolve_area(assignment)
        message = render_service_assignment_added(
            service_date=str(assignment.service_date),
            service_area=service_area_name or resolved_name,
            service_start=start_dt.strftime("%I:%M %p") if start_dt else None,
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
        # Sin esto, la confirmación sigue viva y escala por un turno que ya no
        # existe. El aviso de "removido" se encola igual más abajo.
        if self.confirmation_service is not None:
            self.confirmation_service.cancel_for_assignments([assignment.id])
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
        resolved_name, start_dt = self._resolve_area(assignment)
        message = render_service_assignment_updated(
            service_date=str(assignment.service_date),
            service_area=service_area_name or resolved_name,
            service_start=start_dt.strftime("%I:%M %p") if start_dt else None,
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
            phone = _resolve_recipient_phone(doctor)
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
                    due_at=self._confirmation_due_at(
                        self._resolve_area(assignment)[1]
                    ),
                    created_by=actor_id,
                )
                notification.payload = {
                    **(notification.payload or {}),
                    "message": _build_confirmation_message(message, doctor, confirmation),
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
            # Igual que en las asignaciones: el id se lee ANTES del try para que
            # el log del `except` no pueda lanzar por tocar una instancia muerta.
            participant_id = participant.doctor_id
            try:
                doctor = self.doctor_repo.get_by_id(participant_id)
                phone = _resolve_recipient_phone(doctor)
                message = render_mission_participant(
                    mission_date=mission_date,
                    location=mission.location,
                    description=mission.description,
                    mission_start=None,
                )
                notification = self.notification_service.queue(
                    notification_type="mission_participant",
                    idempotency_key=f"mission_participant:{mission.id}:{participant_id}",
                    recipient_doctor_id=participant_id,
                    recipient_phone=phone,
                    payload={"message": message},
                    mission_id=mission.id,
                    created_by=actor_id,
                )
                if self.confirmation_service is not None:
                    confirmation = self.confirmation_service.create_request(
                        confirmation_type="mission",
                        idempotency_key=f"mission:{mission.id}:{participant_id}",
                        doctor_id=participant_id,
                        notification_id=notification.id,
                        mission_id=mission.id,
                        due_at=self._confirmation_due_at(
                            getattr(mission, "mission_start_at", None)
                        ),
                        created_by=actor_id,
                    )
                    notification.payload = {
                        **(notification.payload or {}),
                        "message": _build_confirmation_message(message, doctor, confirmation),
                        "confirmation_request_id": confirmation.id,
                    }
                count += 1
            except Exception:
                logger.warning(
                    "Failed to queue mission notification for participant %s",
                    participant_id,
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
                phone = _resolve_recipient_phone(doctor)
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
                phone = _resolve_recipient_phone(doctor)
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
                        due_at=self._confirmation_due_at(
                            getattr(mission, "mission_start_at", None)
                        ),
                        created_by=actor_id,
                    )
                    notification.payload = {
                        **(notification.payload or {}),
                        "message": _build_confirmation_message(message, doctor, confirmation),
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
                phone = _resolve_recipient_phone(doctor)
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

    def _confirmation_due_at(self, service_start: datetime | None) -> datetime:
        from backend.app.application.confirmations.deadlines import due_at_for_service

        return due_at_for_service(
            service_start,
            hours_before=self.due_hours_before_service,
        )
