from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.api.dependencies import require_permission
from backend.app.application.action_alerts.service import ActionAlertService
from backend.app.application.confirmations.service import (
    ConfirmationRequestError,
    ConfirmationRequestService,
)
from backend.app.infrastructure.db.models.user import UserModel
from backend.app.infrastructure.db.session import get_db_session
from backend.app.infrastructure.repositories.action_alerts import ActionAlertRepository
from backend.app.infrastructure.repositories.confirmations import ConfirmationRequestRepository
from backend.app.infrastructure.repositories.doctors import DoctorRepository
from backend.app.schemas.confirmations import (
    ConfirmationRequestListResponse,
    ConfirmationRequestRead,
    ProcessOverdueConfirmationsResponse,
    PublicConfirmationActionRequest,
    PublicConfirmationRead,
    PublicConfirmationResponse,
)

router = APIRouter(prefix="/confirmation-requests", tags=["confirmation-requests"])


@router.get("/public/{response_token}", response_model=PublicConfirmationRead)
def get_public_confirmation(
    response_token: str,
    session: Annotated[Session, Depends(get_db_session)],
) -> PublicConfirmationRead:
    request = ConfirmationRequestRepository(session).get_by_response_token(response_token.strip())
    if request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Confirmación no encontrada.")
    doctor = DoctorRepository(session).get_by_id(request.doctor_id)
    return PublicConfirmationRead(
        confirmation_type=request.confirmation_type,
        status=request.status,
        doctor_name=doctor.name if doctor else None,
        due_at=request.due_at,
        responded_at=request.responded_at,
    )


@router.post("/public/{response_token}/{action}", response_model=PublicConfirmationResponse)
def respond_public_confirmation(
    response_token: str,
    action: str,
    payload: PublicConfirmationActionRequest,
    session: Annotated[Session, Depends(get_db_session)],
) -> PublicConfirmationResponse:
    service = ConfirmationRequestService(
        ConfirmationRequestRepository(session),
        action_alerts=ActionAlertService(ActionAlertRepository(session)),
    )
    response_payload = {"action": action, "note": payload.note}
    try:
        if action == "received":
            request = service.mark_received_by_token(
                response_token,
                response_channel="public_link",
                response_payload=response_payload,
            )
        elif action == "confirm":
            request = service.mark_confirmed_by_token(
                response_token,
                response_channel="public_link",
                response_payload=response_payload,
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Acción de confirmación no encontrada.",
            )
    except ConfirmationRequestError as exc:
        if exc.code == "confirmation_not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Confirmación no encontrada.",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes autorización para responder esta confirmación.",
        ) from exc

    session.commit()
    doctor = DoctorRepository(session).get_by_id(request.doctor_id)
    return PublicConfirmationResponse(
        confirmation_type=request.confirmation_type,
        status=request.status,
        doctor_name=doctor.name if doctor else None,
        responded_at=request.responded_at,
    )


@router.get("", response_model=ConfirmationRequestListResponse)
def list_confirmation_requests(
    _current_user: Annotated[UserModel, Depends(require_permission("manage_confirmations"))],
    session: Annotated[Session, Depends(get_db_session)],
    status: str | None = Query(default=None),
    confirmation_type: str | None = Query(default=None),
    doctor_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> ConfirmationRequestListResponse:
    repo = ConfirmationRequestRepository(session)
    items = repo.list_all(
        status=status,
        confirmation_type=confirmation_type,
        doctor_id=doctor_id,
        limit=limit,
    )
    return ConfirmationRequestListResponse(
        items=[ConfirmationRequestRead.model_validate(item) for item in items],
        total=len(items),
    )


@router.post("/process-overdue", response_model=ProcessOverdueConfirmationsResponse)
def process_overdue_confirmations(
    current_user: Annotated[UserModel, Depends(require_permission("manage_confirmations"))],
    session: Annotated[Session, Depends(get_db_session)],
) -> ProcessOverdueConfirmationsResponse:
    service = ConfirmationRequestService(
        ConfirmationRequestRepository(session),
        action_alerts=ActionAlertService(ActionAlertRepository(session)),
    )
    result = service.process_overdue(actor_id=current_user.id)
    session.commit()
    return ProcessOverdueConfirmationsResponse(**result)
