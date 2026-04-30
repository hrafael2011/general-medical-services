from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.infrastructure.db.models.catalogs import (
    DeactivationReasonModel,
    DepartmentModel,
    RankModel,
    ServiceAreaModel,
    SystemSettingModel,
)


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
        return self.session.get(DeactivationReasonModel, reason_id)

    def get_deactivation_reason_by_code(self, code: str) -> DeactivationReasonModel | None:
        statement = select(DeactivationReasonModel).where(DeactivationReasonModel.code == code)
        return self.session.scalar(statement)

    def list_deactivation_reasons(self) -> list[DeactivationReasonModel]:
        statement = select(DeactivationReasonModel).order_by(DeactivationReasonModel.code)
        return list(self.session.scalars(statement))

    def list_deactivation_reasons_for_sex(self, sex: str) -> list[DeactivationReasonModel]:
        statement = (
            select(DeactivationReasonModel)
            .where(
                DeactivationReasonModel.active.is_(True),
                (
                    (DeactivationReasonModel.applies_to_sex.is_(None))
                    | (DeactivationReasonModel.applies_to_sex == sex)
                ),
            )
            .order_by(DeactivationReasonModel.code)
        )
        return list(self.session.scalars(statement))

    def add_rank(self, rank: RankModel) -> RankModel:
        self.session.add(rank)
        self.session.flush()
        return rank

    def list_ranks(self) -> list[RankModel]:
        statement = select(RankModel).order_by(RankModel.name)
        return list(self.session.scalars(statement))

    def add_department(self, department: DepartmentModel) -> DepartmentModel:
        self.session.add(department)
        self.session.flush()
        return department

    def list_departments(self) -> list[DepartmentModel]:
        statement = select(DepartmentModel).order_by(DepartmentModel.name)
        return list(self.session.scalars(statement))

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

