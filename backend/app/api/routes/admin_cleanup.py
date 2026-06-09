"""One-shot admin route for hard-deleting soft-deleted calendars. Available in any environment."""
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.api.dependencies import require_permission
from backend.app.infrastructure.db.models.user import UserModel
from backend.app.infrastructure.db.session import get_db_session
from backend.app.infrastructure.repositories.calendars import CalendarRepository

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/cleanup-soft-deleted-calendars")
def cleanup_soft_deleted_calendars(
    _current_user: Annotated[UserModel, Depends(require_permission("manage_calendars"))],
    session: Annotated[Session, Depends(get_db_session)] = None,
):
    """Hard-delete all soft-deleted calendars and their related data."""
    repo = CalendarRepository(session)
    deleted = repo.list_deleted_calendars()

    if not deleted:
        return {"deleted": 0, "entries": []}

    entries = []
    for c in deleted:
        entries.append({"id": c.id, "year": c.year, "month": c.month})
        repo.hard_delete_calendar(c.id)

    session.commit()
    return {"deleted": len(entries), "entries": entries}
