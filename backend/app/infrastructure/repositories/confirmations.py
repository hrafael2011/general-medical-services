from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.infrastructure.db.models.confirmations import ConfirmationRequestModel


class ConfirmationRequestRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, request: ConfirmationRequestModel) -> ConfirmationRequestModel:
        self.session.add(request)
        self.session.flush()
        return request

    def get_by_id(self, request_id: str) -> ConfirmationRequestModel | None:
        return self.session.get(ConfirmationRequestModel, request_id)

    def get_by_idempotency_key(self, key: str) -> ConfirmationRequestModel | None:
        stmt = select(ConfirmationRequestModel).where(
            ConfirmationRequestModel.idempotency_key == key
        )
        return self.session.scalars(stmt).first()

    def get_by_response_token(self, token: str) -> ConfirmationRequestModel | None:
        stmt = select(ConfirmationRequestModel).where(
            ConfirmationRequestModel.response_token == token
        )
        return self.session.scalars(stmt).first()

    def list_all(
        self,
        *,
        status: str | None = None,
        confirmation_type: str | None = None,
        doctor_id: str | None = None,
        limit: int = 100,
    ) -> list[ConfirmationRequestModel]:
        stmt = select(ConfirmationRequestModel).order_by(
            ConfirmationRequestModel.created_at.desc()
        )
        if status:
            stmt = stmt.where(ConfirmationRequestModel.status == status)
        if confirmation_type:
            stmt = stmt.where(ConfirmationRequestModel.confirmation_type == confirmation_type)
        if doctor_id:
            stmt = stmt.where(ConfirmationRequestModel.doctor_id == doctor_id)
        stmt = stmt.limit(limit)
        return list(self.session.scalars(stmt))

    def list_overdue(self, *, now: datetime) -> list[ConfirmationRequestModel]:
        stmt = (
            select(ConfirmationRequestModel)
            .where(ConfirmationRequestModel.status.in_(["pending", "received"]))
            .where(ConfirmationRequestModel.due_at.is_not(None))
            .where(ConfirmationRequestModel.due_at <= now)
            .order_by(ConfirmationRequestModel.due_at)
        )
        return list(self.session.scalars(stmt))

    def mark_response(
        self,
        request: ConfirmationRequestModel,
        *,
        status: str,
        response_channel: str,
        response_payload: dict | None = None,
    ) -> ConfirmationRequestModel:
        now = datetime.now(UTC)
        request.status = status
        request.responded_at = now
        request.response_channel = response_channel
        request.response_payload = response_payload
        request.updated_at = now
        self.session.flush()
        return request

    def mark_expired(self, request: ConfirmationRequestModel) -> ConfirmationRequestModel:
        now = datetime.now(UTC)
        request.status = "expired"
        request.updated_at = now
        self.session.flush()
        return request
