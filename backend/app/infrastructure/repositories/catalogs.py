from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from backend.app.infrastructure.db.models.catalogs import (
    DeactivationReasonModel,
    DepartmentModel,
    RankModel,
    ServiceAreaModel,
    SystemSettingModel,
)
from backend.app.infrastructure.db.models.doctors import DoctorModel


def _not_deleted_rank() -> tuple:
    return (RankModel.deleted_at.is_(None),)


def _not_deleted_department() -> tuple:
    return (DepartmentModel.deleted_at.is_(None),)


def _not_deleted_deactivation_reason() -> tuple:
    return (DeactivationReasonModel.deleted_at.is_(None),)


class CatalogRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add_service_area(self, service_area: ServiceAreaModel) -> ServiceAreaModel:
        self.session.add(service_area)
        self.session.flush()
        return service_area

    def get_service_area_by_code(self, code: str) -> ServiceAreaModel | None:
        statement = select(ServiceAreaModel).where(ServiceAreaModel.code == code)
        return self.session.scalar(statement)

    def list_service_areas(self) -> list[ServiceAreaModel]:
        statement = select(ServiceAreaModel).order_by(ServiceAreaModel.code)
        return list(self.session.scalars(statement))

    def add_deactivation_reason(
        self,
        reason: DeactivationReasonModel,
    ) -> DeactivationReasonModel:
        self.session.add(reason)
        self.session.flush()
        return reason

    def get_deactivation_reason_by_id(self, reason_id: str) -> DeactivationReasonModel | None:
        statement = select(DeactivationReasonModel).where(
            DeactivationReasonModel.id == reason_id,
            *_not_deleted_deactivation_reason(),
        )
        return self.session.scalar(statement)

    def get_deactivation_reason_by_code(self, code: str) -> DeactivationReasonModel | None:
        statement = select(DeactivationReasonModel).where(
            DeactivationReasonModel.code == code,
            *_not_deleted_deactivation_reason(),
        )
        return self.session.scalar(statement)

    def list_deactivation_reasons(self) -> list[DeactivationReasonModel]:
        statement = (
            select(DeactivationReasonModel)
            .where(*_not_deleted_deactivation_reason())
            .order_by(DeactivationReasonModel.code)
        )
        return list(self.session.scalars(statement))

    def update_deactivation_reason(self, reason_id: str, **fields: object) -> None:
        now = datetime.now(UTC)
        values = {**fields, "updated_at": now}
        self.session.execute(
            update(DeactivationReasonModel)
            .where(DeactivationReasonModel.id == reason_id)
            .values(**values)
        )
        self.session.flush()

    def count_doctors_by_deactivation_reason(self, reason_id: str) -> int:
        stmt = (
            select(func.count())
            .select_from(DoctorModel)
            .where(
                DoctorModel.service_inactive_reason_id == reason_id,
                DoctorModel.deleted_at.is_(None),
            )
        )
        return self.session.scalars(stmt).one()

    def list_deactivation_reasons_for_sex(self, sex: str) -> list[DeactivationReasonModel]:
        statement = (
            select(DeactivationReasonModel)
            .where(
                DeactivationReasonModel.active.is_(True),
                *_not_deleted_deactivation_reason(),
                (
                    (DeactivationReasonModel.applies_to_sex.is_(None))
                    | (DeactivationReasonModel.applies_to_sex == sex)
                ),
            )
            .order_by(DeactivationReasonModel.code)
        )
        return list(self.session.scalars(statement))

    def soft_delete_deactivation_reason(self, reason_id: str) -> None:
        now = datetime.now(UTC)
        self.session.execute(
            update(DeactivationReasonModel)
            .where(DeactivationReasonModel.id == reason_id)
            .values(active=False, deleted_at=now, updated_at=now)
        )
        self.session.flush()

    def list_deleted_deactivation_reasons(self) -> list[DeactivationReasonModel]:
        stmt = (
            select(DeactivationReasonModel)
            .where(DeactivationReasonModel.deleted_at.isnot(None))
            .order_by(DeactivationReasonModel.deleted_at.desc())
        )
        return list(self.session.scalars(stmt))

    def get_deactivation_reason_by_id_including_deleted(
        self,
        reason_id: str,
    ) -> DeactivationReasonModel | None:
        return self.session.get(DeactivationReasonModel, reason_id)

    def restore_deactivation_reason(self, reason_id: str) -> None:
        now = datetime.now(UTC)
        self.session.execute(
            update(DeactivationReasonModel)
            .where(DeactivationReasonModel.id == reason_id)
            .values(active=True, deleted_at=None, updated_at=now)
        )
        self.session.flush()

    def hard_delete_deactivation_reason(self, reason_id: str) -> None:
        reason = self.get_deactivation_reason_by_id_including_deleted(reason_id)
        if reason is not None:
            self.session.delete(reason)
            self.session.flush()

    def add_rank(self, rank: RankModel) -> RankModel:
        self.session.add(rank)
        self.session.flush()
        return rank

    def get_rank_by_id(self, rank_id: str) -> RankModel | None:
        stmt = select(RankModel).where(RankModel.id == rank_id, *_not_deleted_rank())
        return self.session.scalars(stmt).first()

    def get_department_by_id(self, department_id: str) -> DepartmentModel | None:
        stmt = select(DepartmentModel).where(
            DepartmentModel.id == department_id, *_not_deleted_department()
        )
        return self.session.scalars(stmt).first()

    def list_ranks(self) -> list[RankModel]:
        statement = select(RankModel).where(*_not_deleted_rank()).order_by(RankModel.name)
        return list(self.session.scalars(statement))

    def soft_delete_rank(self, rank_id: str) -> None:
        now = datetime.now(UTC)
        self.session.execute(
            update(RankModel)
            .where(RankModel.id == rank_id)
            .values(deleted_at=now, updated_at=now)
        )
        self.session.flush()

    def list_deleted_ranks(self) -> list[RankModel]:
        stmt = (
            select(RankModel)
            .where(RankModel.deleted_at.isnot(None))
            .order_by(RankModel.deleted_at.desc())
        )
        return list(self.session.scalars(stmt))

    def get_rank_by_id_including_deleted(self, rank_id: str) -> RankModel | None:
        return self.session.get(RankModel, rank_id)

    def restore_rank(self, rank_id: str) -> None:
        now = datetime.now(UTC)
        self.session.execute(
            update(RankModel)
            .where(RankModel.id == rank_id)
            .values(deleted_at=None, updated_at=now)
        )
        self.session.flush()

    def hard_delete_rank(self, rank_id: str) -> None:
        rank = self.get_rank_by_id_including_deleted(rank_id)
        if rank is not None:
            self.session.delete(rank)
            self.session.flush()

    def update_rank(self, rank_id: str, **fields: object) -> None:
        now = datetime.now(UTC)
        values = {**fields, "updated_at": now}
        self.session.execute(
            update(RankModel).where(RankModel.id == rank_id).values(**values)
        )
        self.session.flush()

    def add_department(self, department: DepartmentModel) -> DepartmentModel:
        self.session.add(department)
        self.session.flush()
        return department

    def list_departments(self) -> list[DepartmentModel]:
        statement = (
            select(DepartmentModel)
            .where(*_not_deleted_department())
            .order_by(DepartmentModel.name)
        )
        return list(self.session.scalars(statement))

    def count_doctors_by_rank(self, rank_id: str) -> int:
        stmt = (
            select(func.count())
            .select_from(DoctorModel)
            .where(DoctorModel.rank_id == rank_id, DoctorModel.deleted_at.is_(None))
        )
        return self.session.scalars(stmt).one()

    def count_doctors_by_department(self, department_id: str) -> int:
        stmt = (
            select(func.count())
            .select_from(DoctorModel)
            .where(DoctorModel.department_id == department_id, DoctorModel.deleted_at.is_(None))
        )
        return self.session.scalars(stmt).one()

    def soft_delete_department(self, department_id: str) -> None:
        now = datetime.now(UTC)
        self.session.execute(
            update(DepartmentModel)
            .where(DepartmentModel.id == department_id)
            .values(deleted_at=now, updated_at=now)
        )
        self.session.flush()

    def list_deleted_departments(self) -> list[DepartmentModel]:
        stmt = (
            select(DepartmentModel)
            .where(DepartmentModel.deleted_at.isnot(None))
            .order_by(DepartmentModel.deleted_at.desc())
        )
        return list(self.session.scalars(stmt))

    def get_department_by_id_including_deleted(self, department_id: str) -> DepartmentModel | None:
        return self.session.get(DepartmentModel, department_id)

    def restore_department(self, department_id: str) -> None:
        now = datetime.now(UTC)
        self.session.execute(
            update(DepartmentModel)
            .where(DepartmentModel.id == department_id)
            .values(deleted_at=None, updated_at=now)
        )
        self.session.flush()

    def hard_delete_department(self, department_id: str) -> None:
        dept = self.get_department_by_id_including_deleted(department_id)
        if dept is not None:
            self.session.delete(dept)
            self.session.flush()

    def update_department(self, department_id: str, **fields: object) -> None:
        now = datetime.now(UTC)
        values = {**fields, "updated_at": now}
        self.session.execute(
            update(DepartmentModel)
            .where(DepartmentModel.id == department_id)
            .values(**values)
        )
        self.session.flush()

    def upsert_setting(self, setting: SystemSettingModel) -> SystemSettingModel:
        existing = self.session.get(SystemSettingModel, setting.key)
        if existing is None:
            self.session.add(setting)
            self.session.flush()
            return setting
        existing.value = setting.value
        existing.description = setting.description
        existing.updated_at = setting.updated_at
        self.session.flush()
        return existing

    def get_setting(self, key: str) -> SystemSettingModel | None:
        return self.session.get(SystemSettingModel, key)
