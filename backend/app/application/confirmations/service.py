import secrets
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.exc import IntegrityError

from backend.app.application.action_alerts.service import ActionAlertService
from backend.app.infrastructure.db.models.confirmations import ConfirmationRequestModel
from backend.app.infrastructure.db.models.notifications import NotificationEventModel
from backend.app.infrastructure.repositories.confirmations import ConfirmationRequestRepository


class ConfirmationRequestError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class ConfirmationRequestService:
    def __init__(
        self,
        repo: ConfirmationRequestRepository,
        action_alerts: ActionAlertService | None = None,
    ) -> None:
        self.repo = repo
        self.action_alerts = action_alerts

    def create_request(
        self,
        *,
        confirmation_type: str,
        idempotency_key: str,
        doctor_id: str,
        notification_id: str | None = None,
        assignment_id: str | None = None,
        mission_id: str | None = None,
        due_at: datetime | None = None,
        created_by: str | None = None,
    ) -> ConfirmationRequestModel:
        existing = self.repo.get_by_idempotency_key(idempotency_key)
        if existing is not None:
            return existing

        now = datetime.now(UTC)
        request = ConfirmationRequestModel(
            id=str(uuid4()),
            confirmation_type=confirmation_type,
            status="pending",
            idempotency_key=idempotency_key,
            response_token=self._new_response_token(),
            doctor_id=doctor_id,
            notification_id=notification_id,
            assignment_id=assignment_id,
            mission_id=mission_id,
            due_at=due_at,
            responded_at=None,
            response_channel=None,
            response_payload=None,
            created_by=created_by,
            created_at=now,
            updated_at=now,
        )
        try:
            return self.repo.add(request)
        except IntegrityError:
            self.repo.session.rollback()
            existing = self.repo.get_by_idempotency_key(idempotency_key)
            if existing is not None:
                return existing
            raise

    def mark_received_by_token(
        self,
        response_token: str,
        *,
        response_channel: str,
        response_payload: dict | None = None,
        expected_doctor_id: str | None = None,
    ) -> ConfirmationRequestModel:
        return self._mark_response_by_token(
            response_token,
            status="received",
            response_channel=response_channel,
            response_payload=response_payload,
            expected_doctor_id=expected_doctor_id,
        )

    def mark_confirmed_by_token(
        self,
        response_token: str,
        *,
        response_channel: str,
        response_payload: dict | None = None,
        expected_doctor_id: str | None = None,
    ) -> ConfirmationRequestModel:
        return self._mark_response_by_token(
            response_token,
            status="confirmed",
            response_channel=response_channel,
            response_payload=response_payload,
            expected_doctor_id=expected_doctor_id,
        )

    def mark_declined_by_token(
        self,
        response_token: str,
        *,
        response_channel: str,
        response_payload: dict | None = None,
        expected_doctor_id: str | None = None,
    ) -> ConfirmationRequestModel:
        return self._mark_response_by_token(
            response_token,
            status="declined",
            response_channel=response_channel,
            response_payload=response_payload,
            expected_doctor_id=expected_doctor_id,
        )

    def mark_received(
        self,
        request_id: str,
        *,
        response_channel: str,
        response_payload: dict | None = None,
    ) -> ConfirmationRequestModel:
        return self._mark_response(
            request_id,
            status="received",
            response_channel=response_channel,
            response_payload=response_payload,
        )

    def mark_confirmed(
        self,
        request_id: str,
        *,
        response_channel: str,
        response_payload: dict | None = None,
    ) -> ConfirmationRequestModel:
        return self._mark_response(
            request_id,
            status="confirmed",
            response_channel=response_channel,
            response_payload=response_payload,
        )

    def mark_declined(
        self,
        request_id: str,
        *,
        response_channel: str,
        response_payload: dict | None = None,
    ) -> ConfirmationRequestModel:
        return self._mark_response(
            request_id,
            status="declined",
            response_channel=response_channel,
            response_payload=response_payload,
        )

    def process_overdue(self, *, actor_id: str | None = None) -> dict:
        now = datetime.now(UTC)
        overdue = self.repo.list_overdue(now=now)
        alerts_created = 0

        for request in overdue:
            self.repo.mark_expired(request)
            if self.action_alerts is None:
                continue

            alert_type = (
                "service_confirmation_overdue"
                if request.confirmation_type == "service"
                else "mission_confirmation_overdue"
            )
            section = "calendar" if request.confirmation_type == "service" else "missions"
            title = (
                "Confirmación de servicio vencida"
                if request.confirmation_type == "service"
                else "Confirmación de misión vencida"
            )
            message = (
                "Un médico no confirmó el servicio dentro del tiempo esperado."
                if request.confirmation_type == "service"
                else "Un médico no confirmó la misión dentro del tiempo esperado."
            )
            before = self.action_alerts.repo.get_open_for_entity(
                alert_type=alert_type,
                entity_type="confirmation_request",
                entity_id=request.id,
            )
            self.action_alerts.create_if_missing(
                alert_type=alert_type,
                section=section,
                severity="warning",
                title=title,
                message=message,
                entity_type="confirmation_request",
                entity_id=request.id,
                action_url="/calendars" if section == "calendar" else "/missions",
                alert_metadata={
                    "confirmation_request_id": request.id,
                    "confirmation_type": request.confirmation_type,
                    "doctor_id": request.doctor_id,
                    "assignment_id": request.assignment_id,
                    "mission_id": request.mission_id,
                    "due_at": request.due_at.isoformat() if request.due_at else None,
                },
                created_by=actor_id,
            )
            after = self.action_alerts.repo.get_open_for_entity(
                alert_type=alert_type,
                entity_type="confirmation_request",
                entity_id=request.id,
            )
            if before is None and after is not None:
                alerts_created += 1

        return {"expired": len(overdue), "alerts_created": alerts_created}

    def _mark_response(
        self,
        request_id: str,
        *,
        status: str,
        response_channel: str,
        response_payload: dict | None,
    ) -> ConfirmationRequestModel:
        request = self.repo.get_by_id(request_id)
        if request is None:
            raise ConfirmationRequestError(
                "confirmation_not_found",
                "La solicitud de confirmación no existe.",
            )
        if request.status in {"confirmed", "declined"}:
            return request
        updated = self.repo.mark_response(
            request,
            status=status,
            response_channel=response_channel,
            response_payload=response_payload,
        )
        self._handle_final_response_alerts(
            updated,
            status=status,
            response_payload=response_payload,
        )
        return updated

    def _mark_response_by_token(
        self,
        response_token: str,
        *,
        status: str,
        response_channel: str,
        response_payload: dict | None,
        expected_doctor_id: str | None = None,
    ) -> ConfirmationRequestModel:
        request = self.repo.get_by_response_token(response_token.strip())
        if request is None:
            raise ConfirmationRequestError(
                "confirmation_not_found",
                "La solicitud de confirmación no existe.",
            )
        if expected_doctor_id is not None and request.doctor_id != expected_doctor_id:
            raise ConfirmationRequestError(
                "confirmation_not_authorized",
                "No tiene autorización para responder esta confirmación.",
            )
        if request.status in {"confirmed", "declined"}:
            return request
        updated = self.repo.mark_response(
            request,
            status=status,
            response_channel=response_channel,
            response_payload=response_payload,
        )
        self._handle_final_response_alerts(
            updated,
            status=status,
            response_payload=response_payload,
        )

        # Create notification event for admin visibility when confirmed
        if status == "confirmed":
            now = datetime.now(UTC)
            event = NotificationEventModel(
                id=str(uuid4()),
                notification_type=f"{request.confirmation_type}_confirmed",
                idempotency_key=f"confirmed:{request.id}",
                recipient_doctor_id=request.doctor_id,
                recipient_phone=None,
                payload={
                    "message": (
                        f"Dr. confirmó su {'servicio' if request.confirmation_type == 'service' else 'misión'}."
                    ),
                    "confirmation_request_id": request.id,
                },
                status="skipped",
                sent_at=now,
                created_by=request.doctor_id,
                created_at=now,
                updated_at=now,
            )
            self.repo.session.add(event)

        return updated

    def _handle_final_response_alerts(
        self,
        request: ConfirmationRequestModel,
        *,
        status: str,
        response_payload: dict | None,
    ) -> None:
        self._resolve_overdue_alert_if_final(
            request,
            status=status,
            response_payload=response_payload,
        )
        if status == "declined":
            self._create_declined_alert(request, response_payload=response_payload)

    def _resolve_overdue_alert_if_final(
        self,
        request: ConfirmationRequestModel,
        *,
        status: str,
        response_payload: dict | None,
    ) -> None:
        if self.action_alerts is None or status not in {"confirmed", "declined"}:
            return

        alert_type = (
            "service_confirmation_overdue"
            if request.confirmation_type == "service"
            else "mission_confirmation_overdue"
        )
        alert = self.action_alerts.repo.get_open_for_entity(
            alert_type=alert_type,
            entity_type="confirmation_request",
            entity_id=request.id,
        )
        if alert is None:
            return

        actor_id = None
        if response_payload and isinstance(response_payload.get("user_id"), str):
            actor_id = response_payload["user_id"]
        self.action_alerts.repo.mark_resolved(alert, actor_id=actor_id)

    def _create_declined_alert(
        self,
        request: ConfirmationRequestModel,
        *,
        response_payload: dict | None,
    ) -> None:
        if self.action_alerts is None:
            return

        section = "calendar" if request.confirmation_type == "service" else "missions"
        alert_type = (
            "service_confirmation_declined"
            if request.confirmation_type == "service"
            else "mission_confirmation_declined"
        )
        title = (
            "Servicio rechazado por médico"
            if request.confirmation_type == "service"
            else "Misión rechazada por médico"
        )
        message = (
            "Un médico rechazó una asignación de servicio. Debe revisarse el calendario."
            if request.confirmation_type == "service"
            else "Un médico rechazó una misión. Debe revisarse la asignación."
        )
        actor_id = None
        if response_payload and isinstance(response_payload.get("user_id"), str):
            actor_id = response_payload["user_id"]
        self.action_alerts.create_if_missing(
            alert_type=alert_type,
            section=section,
            severity="critical",
            title=title,
            message=message,
            entity_type="confirmation_request",
            entity_id=request.id,
            action_url="/calendars" if section == "calendar" else "/missions",
            alert_metadata={
                "confirmation_request_id": request.id,
                "confirmation_type": request.confirmation_type,
                "doctor_id": request.doctor_id,
                "assignment_id": request.assignment_id,
                "mission_id": request.mission_id,
            },
            created_by=actor_id,
        )

    def _new_response_token(self) -> str:
        for _ in range(5):
            token = secrets.token_urlsafe(18)
            if self.repo.get_by_response_token(token) is None:
                return token
        return secrets.token_urlsafe(24)
