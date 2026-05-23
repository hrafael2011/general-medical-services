from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.api.dependencies import require_encargado_or_admin
from backend.app.application.notifications.providers import FakeProvider, MetaCloudAPIProvider, TwilioProvider
from backend.app.application.notifications.service import NotificationService
from backend.app.core.config import settings
from backend.app.infrastructure.db.models.user import UserModel
from backend.app.infrastructure.db.session import get_db_session
from backend.app.infrastructure.repositories.notifications import NotificationRepository
from backend.app.schemas.notifications import (
    NotificationEventRead,
    NotificationListResponse,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


def get_notification_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> NotificationService:
    from backend.app.application.action_alerts.service import ActionAlertService
    from backend.app.infrastructure.repositories.action_alerts import ActionAlertRepository

    if settings.meta_whatsapp_token and settings.meta_whatsapp_phone_number_id:
        provider = MetaCloudAPIProvider(
            token=settings.meta_whatsapp_token,
            phone_number_id=settings.meta_whatsapp_phone_number_id,
        )
    elif settings.twilio_account_sid:
        provider = TwilioProvider()
    else:
        provider = FakeProvider()
    return NotificationService(
        repo=NotificationRepository(session),
        provider=provider,
        action_alerts=ActionAlertService(ActionAlertRepository(session)),
    )


@router.get("", response_model=NotificationListResponse)
def list_notifications(
    _user: Annotated[UserModel, Depends(require_encargado_or_admin)],
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
