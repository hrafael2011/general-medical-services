from datetime import UTC, datetime
from uuid import uuid4

from backend.app.domain.catalogs import INITIAL_DEACTIVATION_REASONS, INITIAL_SERVICE_AREAS
from backend.app.infrastructure.db.models.catalogs import (
    DeactivationReasonModel,
    DepartmentModel,
    RankModel,
    ServiceAreaModel,
    SystemSettingModel,
)
from backend.app.infrastructure.repositories.catalogs import CatalogRepository


def normalize_name(value: str) -> str:
    return " ".join(value.strip().lower().split())


class CatalogService:
    def __init__(self, catalogs: CatalogRepository) -> None:
        self.catalogs = catalogs

    def seed_initial_catalogs(self) -> None:
        now = datetime.now(UTC)
        for item in INITIAL_SERVICE_AREAS:
            if self.catalogs.get_service_area_by_code(item["code"]) is None:
                self.catalogs.add_service_area(
                    ServiceAreaModel(
                        id=str(uuid4()),
                        code=item["code"],
                        display_name=item["display_name"],
                        active=True,
                        required_for_daily_coverage=bool(item["required_for_daily_coverage"]),
                        load_weight=int(item["load_weight"]),
                        created_at=now,
                        updated_at=now,
                    )
                )

        for item in INITIAL_DEACTIVATION_REASONS:
            if self.catalogs.get_deactivation_reason_by_code(item["code"]) is None:
                self.catalogs.add_deactivation_reason(
                    DeactivationReasonModel(
                        id=str(uuid4()),
                        code=item["code"],
                        display_name=item["display_name"],
                        active=True,
                        requires_detail=bool(item["requires_detail"]),
                        applies_to_sex=item["applies_to_sex"],
                        severity=item["severity"],
                        created_at=now,
                        updated_at=now,
                    )
                )

        self.catalogs.upsert_setting(
            SystemSettingModel(
                key="calendar_generation_day",
                value="27",
                description="Default day of month to generate next calendar draft.",
                updated_at=now,
            )
        )

    def create_rank(self, name: str, abbreviation: str) -> RankModel:
        now = datetime.now(UTC)
        rank = RankModel(
            id=str(uuid4()),
            name=name.strip(),
            normalized_name=normalize_name(name),
            abbreviation=abbreviation.strip(),
            active=True,
            created_at=now,
            updated_at=now,
        )
        return self.catalogs.add_rank(rank)

    def create_department(self, name: str) -> DepartmentModel:
        now = datetime.now(UTC)
        department = DepartmentModel(
            id=str(uuid4()),
            name=name.strip(),
            normalized_name=normalize_name(name),
            active=True,
            created_at=now,
            updated_at=now,
        )
        return self.catalogs.add_department(department)

