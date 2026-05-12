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

    def get_by_normalized_name(self, name: str) -> DoctorModel | None:
        stmt = select(DoctorModel).where(DoctorModel.normalized_name == name)
        return self.session.scalars(stmt).first()

    def list_all(self, *, active_only: bool = False) -> list[DoctorModel]:
        stmt = select(DoctorModel)
        if active_only:
            stmt = stmt.where(DoctorModel.active.is_(True))
        return list(self.session.scalars(stmt.order_by(DoctorModel.name)))

    def list_service_active(self) -> list[DoctorModel]:
        stmt = (
            select(DoctorModel)
            .where(DoctorModel.active.is_(True))
            .where(DoctorModel.service_active.is_(True))
            .order_by(DoctorModel.name)
        )
        return list(self.session.scalars(stmt))

    def list_with_filters(
        self,
        *,
        rank_id: str | None = None,
        sex: str | None = None,
        department_id: str | None = None,
        active_only: bool = True,
    ) -> list[DoctorModel]:
        stmt = select(DoctorModel)
        if active_only:
            stmt = stmt.where(DoctorModel.active.is_(True))
        if rank_id:
            stmt = stmt.where(DoctorModel.rank_id == rank_id)
        if sex:
            stmt = stmt.where(DoctorModel.sex == sex)
        if department_id:
            stmt = stmt.where(DoctorModel.department_id == department_id)
        return list(self.session.scalars(stmt.order_by(DoctorModel.name)))

    def get_allowed_areas(self, doctor_id: str) -> list[str]:
        stmt = select(DoctorAllowedAreaModel.service_area_id).where(
            DoctorAllowedAreaModel.doctor_id == doctor_id
        )
        return list(self.session.scalars(stmt))

    def get_allowed_areas_bulk(self, doctor_ids: list[str]) -> dict[str, list[str]]:
        """Load allowed areas for multiple doctors in a single query."""
        if not doctor_ids:
            return {}
        stmt = select(DoctorAllowedAreaModel).where(
            DoctorAllowedAreaModel.doctor_id.in_(doctor_ids)
        )
        result: dict[str, list[str]] = {}
        for row in self.session.scalars(stmt):
            result.setdefault(row.doctor_id, []).append(row.service_area_id)
        return result

    def set_allowed_areas(self, doctor_id: str, area_ids: list[str]) -> None:
        self.session.query(DoctorAllowedAreaModel).filter(
            DoctorAllowedAreaModel.doctor_id == doctor_id
        ).delete()
        for area_id in area_ids:
            self.session.add(DoctorAllowedAreaModel(doctor_id=doctor_id, service_area_id=area_id))
        self.session.flush()
