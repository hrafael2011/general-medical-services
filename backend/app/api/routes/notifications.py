from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.api.dependencies import require_ready_user
from backend.app.application.notifications.providers import FakeProvider, TwilioProvider
from backend.app.application.notifications.service import NotificationService
from backend.app.core.config import settings
from backend.app.infrastructure.db.models.user import UserModel
from backend.app.infrastructure.db.session import get_db_session
from backend.app.infrastructure.repositories.notifications import NotificationRepository
from backend.app.schemas.notifications import (
    NotificationEventRead,
    NotificationListResponse,
    ProcessNotificationsResponse,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


def get_notification_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> NotificationService:
    provider = TwilioProvider() if settings.twilio_account_sid else FakeProvider()
    return NotificationService(
        repo=NotificationRepository(session),
        provider=provider,
    )


@router.get("", response_model=NotificationListResponse)
def list_notifications(
    _user: Annotated[UserModel, Depends(require_ready_user)],
    session: Annotated[Session, Depends(get_db_session)],
    status: str | None = Query(default=None),
    notification_type: str | None = Query(default=None),
    limit: int = Query(default=100, le=500),
) -> NotificationListResponse:
    repo = NotificationRepository(session)
    items = repo.list_all(status=status, notification_type=notification_type, limit=limit)
    return NotificationListResponse(
        items=[NotificationEventRead.model_validate(n) for n in items],
        total=len(items),
    )


@router.post("/process", response_model=ProcessNotificationsResponse)
def process_notifications(
    _user: Annotated[UserModel, Depends(require_ready_user)],
    service: Annotated[NotificationService, Depends(get_notification_service)],
    session: Annotated[Session, Depends(get_db_session)],
) -> ProcessNotificationsResponse:
    result = service.process_pending()
    session.commit()
    return ProcessNotificationsResponse(**result)
