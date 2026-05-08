from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.infrastructure.db.models.availability import (
    DoctorAvailabilityModel,
    DoctorRestrictionModel,
)


class AvailabilityRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    # --- availability ---

    def add_availability(self, record: DoctorAvailabilityModel) -> DoctorAvailabilityModel:
        self.session.add(record)
        self.session.flush()
        return record

    def get_availability_by_id(self, record_id: str) -> DoctorAvailabilityModel | None:
        return self.session.get(DoctorAvailabilityModel, record_id)

    def list_availability_for_doctor(self, doctor_id: str) -> list[DoctorAvailabilityModel]:
        stmt = select(DoctorAvailabilityModel).where(
            DoctorAvailabilityModel.doctor_id == doctor_id
        ).order_by(DoctorAvailabilityModel.created_at)
        return list(self.session.scalars(stmt))

    def list_monthly_variable_for_period(
        self, doctor_id: str, year: int, month: int
    ) -> list[DoctorAvailabilityModel]:
        stmt = select(DoctorAvailabilityModel).where(
            DoctorAvailabilityModel.doctor_id == doctor_id,
            DoctorAvailabilityModel.availability_type == "monthly_variable",
            DoctorAvailabilityModel.year == year,
            DoctorAvailabilityModel.month == month,
        )
        return list(self.session.scalars(stmt))

    def list_weekly_fixed_for_doctor(self, doctor_id: str) -> list[DoctorAvailabilityModel]:
        stmt = select(DoctorAvailabilityModel).where(
            DoctorAvailabilityModel.doctor_id == doctor_id,
            DoctorAvailabilityModel.availability_type == "weekly_fixed",
        )
        return list(self.session.scalars(stmt))

    def delete_availability(self, record_id: str) -> None:
        record = self.session.get(DoctorAvailabilityModel, record_id)
        if record:
            self.session.delete(record)
            self.session.flush()

    # --- restrictions ---

    def add_restriction(self, record: DoctorRestrictionModel) -> DoctorRestrictionModel:
        self.session.add(record)
        self.session.flush()
        return record

    def get_restriction_by_id(self, record_id: str) -> DoctorRestrictionModel | None:
        return self.session.get(DoctorRestrictionModel, record_id)

    def list_active_restrictions_for_doctor(
        self, doctor_id: str, on_date: date
    ) -> list[DoctorRestrictionModel]:
        stmt = select(DoctorRestrictionModel).where(
            DoctorRestrictionModel.doctor_id == doctor_id,
            DoctorRestrictionModel.lifted_at.is_(None),
            DoctorRestrictionModel.starts_at <= on_date,
        ).order_by(DoctorRestrictionModel.starts_at)
        results = list(self.session.scalars(stmt))
        # filter ends_at in Python to avoid DB null comparison complexity
        return [r for r in results if r.ends_at is None or r.ends_at >= on_date]

    def list_restrictions_for_doctor(self, doctor_id: str) -> list[DoctorRestrictionModel]:
        stmt = select(DoctorRestrictionModel).where(
            DoctorRestrictionModel.doctor_id == doctor_id
        ).order_by(DoctorRestrictionModel.starts_at.desc())
        return list(self.session.scalars(stmt))
