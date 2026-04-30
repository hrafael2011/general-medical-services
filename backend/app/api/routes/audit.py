from typing import Annotated
from datetime import datetime
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.api.dependencies import require_ready_user
from backend.app.infrastructure.db.models.user import UserModel
from backend.app.infrastructure.db.session import get_db_session
from backend.app.infrastructure.repositories.audit import AuditRepository
from backend.app.schemas.audit import AuditEventRead, AuditListResponse

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=AuditListResponse)
def list_audit_events(
    _user: Annotated[UserModel, Depends(require_ready_user)],
    session: Annotated[Session, Depends(get_db_session)],
    actor_id: str | None = Query(default=None),
    action_type: str | None = Query(default=None),
    entity_type: str | None = Query(default=None),
    entity_id: str | None = Query(default=None),
    from_dt: datetime | None = Query(default=None),
    to_dt: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> AuditListResponse:
    repo = AuditRepository(session)
    events = repo.list(
        actor_id=actor_id,
        action_type=action_type,
        entity_type=entity_type,
        entity_id=entity_id,
        from_dt=from_dt,
        to_dt=to_dt,
        limit=limit,
        offset=offset,
    )
    total = repo.count(
        actor_id=actor_id,
        action_type=action_type,
        entity_type=entity_type,
        entity_id=entity_id,
        from_dt=from_dt,
        to_dt=to_dt,
    )
    return AuditListResponse(
        items=[AuditEventRead.model_validate(e) for e in events],
        total=total,
        limit=limit,
        offset=offset,
    )
