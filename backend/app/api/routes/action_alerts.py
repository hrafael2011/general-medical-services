from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.api.dependencies import require_permission
from backend.app.application.action_alerts.service import ActionAlertError, ActionAlertService
from backend.app.infrastructure.db.models.user import UserModel
from backend.app.infrastructure.db.session import get_db_session
from backend.app.infrastructure.repositories.action_alerts import ActionAlertRepository
from backend.app.schemas.action_alerts import (
    ActionAlertListResponse,
    ActionAlertRead,
    ActionAlertSummaryResponse,
)

router = APIRouter(prefix="/action-alerts", tags=["action-alerts"])


@router.get("", response_model=ActionAlertListResponse)
def list_action_alerts(
    _current_user: Annotated[UserModel, Depends(require_permission("manage_alerts"))],
    session: Annotated[Session, Depends(get_db_session)],
    status_filter: str | None = Query(default="open", alias="status"),
    section: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> ActionAlertListResponse:
    repo = ActionAlertRepository(session)
    items = repo.list_all(
        status=status_filter,
        section=section,
        severity=severity,
        limit=limit,
    )
    return ActionAlertListResponse(
        items=[ActionAlertRead.model_validate(item) for item in items],
        total=len(items),
    )


@router.get("/summary", response_model=ActionAlertSummaryResponse)
def summarize_action_alerts(
    _current_user: Annotated[UserModel, Depends(require_permission("manage_alerts"))],
    session: Annotated[Session, Depends(get_db_session)],
) -> ActionAlertSummaryResponse:
    by_section = ActionAlertRepository(session).count_open_by_section()
    return ActionAlertSummaryResponse(
        total_open=sum(by_section.values()),
        by_section=by_section,
    )


@router.post("/{alert_id}/resolve", response_model=ActionAlertRead)
def resolve_action_alert(
    alert_id: str,
    current_user: Annotated[UserModel, Depends(require_permission("manage_alerts"))],
    session: Annotated[Session, Depends(get_db_session)],
) -> ActionAlertRead:
    service = ActionAlertService(ActionAlertRepository(session))
    try:
        alert = service.resolve(alert_id, actor_id=current_user.id)
    except ActionAlertError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    session.commit()
    return ActionAlertRead.model_validate(alert)


@router.post("/{alert_id}/dismiss", response_model=ActionAlertRead)
def dismiss_action_alert(
    alert_id: str,
    current_user: Annotated[UserModel, Depends(require_permission("manage_alerts"))],
    session: Annotated[Session, Depends(get_db_session)],
) -> ActionAlertRead:
    service = ActionAlertService(ActionAlertRepository(session))
    try:
        alert = service.dismiss(alert_id, actor_id=current_user.id)
    except ActionAlertError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    session.commit()
    return ActionAlertRead.model_validate(alert)
