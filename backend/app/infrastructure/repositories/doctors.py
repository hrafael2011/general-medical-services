from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.infrastructure.db.models.doctors import DoctorAllowedAreaModel, DoctorModel


class DoctorRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, doctor: DoctorModel) -> DoctorModel:
        self.session.add(doctor)
        self.session.flush()
        return doctor

    def get_by_id(self, doctor_id: str) -> DoctorModel | None:
        return self.session.get(DoctorModel, doctor_id)

    def list_all(self, *, active_only: bool = False) -> list[DoctorModel]:
        stmt = select(DoctorModel)
        if active_only:
            stmt = stmt.where(DoctorModel.active == True)  # noqa: E712
        return list(self.session.scalars(stmt.order_by(DoctorModel.name)))

    def list_service_active(self) -> list[DoctorModel]:
        stmt = (
            select(DoctorModel)
            .where(DoctorModel.active == True)  # noqa: E712
            .where(DoctorModel.service_active == True)  # noqa: E712
            .order_by(DoctorModel.name)
        )
        return list(self.session.scalars(stmt))

    def get_allowed_areas(self, doctor_id: str) -> list[str]:
        stmt = select(DoctorAllowedAreaModel.service_area_id).where(
            DoctorAllowedAreaModel.doctor_id == doctor_id
        )
        return list(self.session.scalars(stmt))

    def set_allowed_areas(self, doctor_id: str, area_ids: list[str]) -> None:
        self.session.query(DoctorAllowedAreaModel).filter(
            DoctorAllowedAreaModel.doctor_id == doctor_id
        ).delete()
        for area_id in area_ids:
            self.session.add(DoctorAllowedAreaModel(doctor_id=doctor_id, service_area_id=area_id))
        self.session.flush()
