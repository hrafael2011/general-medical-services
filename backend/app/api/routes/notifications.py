from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from backend.app.api.dependencies import require_permission
from backend.app.application.notifications.providers import FakeProvider, MetaCloudAPIProvider
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

# Separate router for scheduler health — included independently in router.py
scheduler_router = APIRouter(prefix="/scheduler", tags=["scheduler"])


def get_notification_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> NotificationService:
    from backend.app.application.action_alerts.service import ActionAlertService
    from backend.app.infrastructure.repositories.action_alerts import ActionAlertRepository

    if settings.meta_whatsapp_token and settings.meta_whatsapp_phone_number_id:
        provider = MetaCloudAPIProvider()
    else:
        provider = FakeProvider()
    return NotificationService(
        repo=NotificationRepository(session),
        provider=provider,
        action_alerts=ActionAlertService(ActionAlertRepository(session)),
    )


@router.get("", response_model=NotificationListResponse)
def list_notifications(
    _current_user: Annotated[UserModel, Depends(require_permission("view_notifications"))],
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


@scheduler_router.get("/health")
def get_scheduler_health(request: Request) -> dict:
    """Return APScheduler status and next-run times for all jobs."""
    scheduler = getattr(request.app.state, "scheduler", None)
    if scheduler is None:
        return {"scheduler_running": False, "jobs": []}

    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
        })
    return {
        "scheduler_running": True,
        "jobs": jobs,
    }

