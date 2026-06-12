from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.api.dependencies import require_encargado_or_admin, require_permission, require_ready_user
from backend.app.application.doctors.errors import DoctorServiceError
from backend.app.application.doctors.service import DoctorService
from backend.app.infrastructure.db.models.user import UserModel
from backend.app.infrastructure.db.session import get_db_session
from backend.app.infrastructure.repositories.catalogs import CatalogRepository
from backend.app.infrastructure.repositories.doctors import DoctorRepository
from backend.app.schemas.doctors import (
    CreateDoctorRequest,
    DeactivateDoctorServiceRequest,
    DoctorByAreaResponse,
    DoctorByDayResponse,
    DoctorByDepartmentResponse,
    DoctorListResponse,
    DoctorRead,
    UpdateDoctorRequest,
)

router = APIRouter(prefix="/doctors", tags=["doctors"])


def get_doctor_service(session: Annotated[Session, Depends(get_db_session)]) -> DoctorService:
    from backend.app.application.action_alerts.service import ActionAlertService
    from backend.app.application.audit.service import AuditService
    from backend.app.infrastructure.repositories.action_alerts import ActionAlertRepository
    from backend.app.infrastructure.repositories.audit import AuditRepository
    from backend.app.infrastructure.repositories.missions import MissionRepository
    return DoctorService(
        DoctorRepository(session),
        catalog_repo=CatalogRepository(session),
        audit=AuditService(AuditRepository(session)),
        mission_repo=MissionRepository(session),
        action_alerts=ActionAlertService(ActionAlertRepository(session)),
    )


def _to_read(doctor, repo: DoctorRepository) -> DoctorRead:
    data = DoctorRead.model_validate(doctor)
    data.allowed_area_ids = repo.get_allowed_areas(doctor.id)
    return data


@router.get("", response_model=DoctorListResponse)
def list_doctors(
    _user: Annotated[UserModel, Depends(require_ready_user)],
    session: Annotated[Session, Depends(get_db_session)],
    status: str = "all",
) -> DoctorListResponse:
    repo = DoctorRepository(session)
    doctors = repo.list_all(status=status)
    # Bulk load allowed areas to avoid N+1
    areas_by_doctor = repo.get_allowed_areas_bulk([d.id for d in doctors])
    items = []
    for d in doctors:
        data = DoctorRead.model_validate(d)
        data.allowed_area_ids = areas_by_doctor.get(d.id, [])
        items.append(data)
    return DoctorListResponse(items=items, total=len(items))


@router.get("/by-day", response_model=DoctorByDayResponse)
def list_doctors_by_day(
    _user: Annotated[UserModel, Depends(require_encargado_or_admin)],
    service: Annotated[DoctorService, Depends(get_doctor_service)],
) -> dict:
    return {"days": service.list_by_day()}


@router.get("/by-area", response_model=DoctorByAreaResponse)
def list_doctors_by_area(
    _user: Annotated[UserModel, Depends(require_encargado_or_admin)],
    service: Annotated[DoctorService, Depends(get_doctor_service)],
) -> dict:
    return service.list_by_area()


@router.get("/by-department", response_model=DoctorByDepartmentResponse)
def list_doctors_by_department(
    _user: Annotated[UserModel, Depends(require_encargado_or_admin)],
    service: Annotated[DoctorService, Depends(get_doctor_service)],
) -> dict:
    return service.list_by_department()


@router.get("/{doctor_id}", response_model=DoctorRead)
def get_doctor(
    doctor_id: str,
    _user: Annotated[UserModel, Depends(require_ready_user)],
    session: Annotated[Session, Depends(get_db_session)],
) -> DoctorRead:
    repo = DoctorRepository(session)
    doctor = repo.get_by_id(doctor_id)
    if doctor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Médico no encontrado.")
    return _to_read(doctor, repo)


@router.post("", response_model=DoctorRead, status_code=201)
def create_doctor(
    payload: CreateDoctorRequest,
    current_user: Annotated[UserModel, Depends(require_permission("manage_doctors"))],
    service: Annotated[DoctorService, Depends(get_doctor_service)],
    session: Annotated[Session, Depends(get_db_session)],
) -> DoctorRead:
    doctor = service.create_doctor(
        actor_id=current_user.id,
        first_name=payload.first_name,
        last_name=payload.last_name,
        name=payload.name,
        sex=payload.sex,
        rank_id=payload.rank_id,
        department_id=payload.department_id,
        notes=payload.notes,
        participa_misiones=payload.participa_misiones,
        service_active=payload.service_active,
        whatsapp_phone=payload.whatsapp_phone,
        monthly_service_target=payload.monthly_service_target,
        monthly_service_max=payload.monthly_service_max,
        monthly_service_limit_mode=payload.monthly_service_limit_mode,
        availability_mode=payload.availability_mode,
        allowed_area_ids=payload.allowed_area_ids,
    )
    session.commit()
    return _to_read(doctor, DoctorRepository(session))


@router.patch("/{doctor_id}", response_model=DoctorRead)
def update_doctor(
    doctor_id: str,
    payload: UpdateDoctorRequest,
    current_user: Annotated[UserModel, Depends(require_permission("manage_doctors"))],
    service: Annotated[DoctorService, Depends(get_doctor_service)],
    session: Annotated[Session, Depends(get_db_session)],
) -> DoctorRead:
    update_fields = payload.model_dump(exclude_unset=True)
    try:
        doctor = service.update_doctor(
            doctor_id,
            actor_id=current_user.id,
            **update_fields,
        )
    except DoctorServiceError as exc:
        status_code = (
            status.HTTP_404_NOT_FOUND
            if exc.code == "doctor_not_found"
            else status.HTTP_422_UNPROCESSABLE_ENTITY
        )
        raise HTTPException(status_code=status_code, detail={"code": exc.code, "message": exc.message}) from exc
    session.commit()
    doctor_read = _to_read(doctor, DoctorRepository(session))
    cleanup = getattr(service, '_last_cleanup_info', {})
    if cleanup.get('removed_assignments', 0) > 0:
        doctor_read.removed_assignments = cleanup['removed_assignments']
        doctor_read.affected_calendar_ids = cleanup.get('affected_calendar_ids', [])
        service._last_cleanup_info = {}
    return doctor_read


@router.post("/{doctor_id}/deactivate-service", response_model=DoctorRead)
def deactivate_service(
    doctor_id: str,
    payload: DeactivateDoctorServiceRequest,
    current_user: Annotated[UserModel, Depends(require_permission("manage_doctors"))],
    service: Annotated[DoctorService, Depends(get_doctor_service)],
    session: Annotated[Session, Depends(get_db_session)],
) -> DoctorRead:
    try:
        doctor = service.deactivate_service(
            doctor_id, actor_id=current_user.id, reason_id=payload.reason_id, detail=payload.detail
        )
    except DoctorServiceError as exc:
        status_code = (
            status.HTTP_404_NOT_FOUND
            if exc.code == "doctor_not_found"
            else status.HTTP_422_UNPROCESSABLE_ENTITY
        )
        raise HTTPException(status_code=status_code, detail={"code": exc.code, "message": exc.message}) from exc
    session.commit()
    return _to_read(doctor, DoctorRepository(session))


@router.post("/{doctor_id}/reactivate-service", response_model=DoctorRead)
def reactivate_service(
    doctor_id: str,
    current_user: Annotated[UserModel, Depends(require_permission("manage_doctors"))],
    service: Annotated[DoctorService, Depends(get_doctor_service)],
    session: Annotated[Session, Depends(get_db_session)],
) -> DoctorRead:
    try:
        doctor = service.reactivate_service(doctor_id, actor_id=current_user.id)
    except DoctorServiceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": exc.code, "message": exc.message}) from exc
    session.commit()
    return _to_read(doctor, DoctorRepository(session))


@router.delete("/{doctor_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_doctor(
    doctor_id: str,
    current_user: Annotated[UserModel, Depends(require_permission("manage_doctors"))],
    service: Annotated[DoctorService, Depends(get_doctor_service)],
    session: Annotated[Session, Depends(get_db_session)],
) -> None:
    try:
        service.soft_delete_doctor(doctor_id, actor_id=current_user.id)
    except DoctorServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    session.commit()
