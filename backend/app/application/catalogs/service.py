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

CALENDAR_AUTO_GENERATION_ENABLED_KEY = "calendar_auto_generation_enabled"
CALENDAR_GENERATION_DAY_KEY = "calendar_generation_day"


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

        self._upsert_calendar_generation_defaults(now)

        from backend.app.application.reports.pdf_templates import DEFAULT_SIGNATURES as _sigs
        for key, value, description in [
            ("pdf.sig_left_name",   _sigs.left_name,   "Nombre de la firmante izquierda en PDFs institucionales."),
            ("pdf.sig_left_title1", _sigs.left_title1, "Título 1 de la firmante izquierda."),
            ("pdf.sig_left_title2", _sigs.left_title2, "Título 2 de la firmante izquierda."),
            ("pdf.sig_left_title3", _sigs.left_title3, "Título 3 de la firmante izquierda."),
            ("pdf.sig_right_name",   _sigs.right_name,   "Nombre del firmante derecho en PDFs institucionales."),
            ("pdf.sig_right_title1", _sigs.right_title1, "Título 1 del firmante derecho."),
            ("pdf.sig_right_title2", _sigs.right_title2, "Título 2 del firmante derecho."),
            ("pdf.sig_right_title3", _sigs.right_title3, "Título 3 del firmante derecho."),
        ]:
            self.catalogs.upsert_setting(
                SystemSettingModel(key=key, value=value, description=description, updated_at=now)
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

    def _upsert_calendar_generation_defaults(self, now: datetime) -> None:
        if self.catalogs.get_setting(CALENDAR_GENERATION_DAY_KEY) is None:
            self.catalogs.upsert_setting(
                SystemSettingModel(
                    key=CALENDAR_GENERATION_DAY_KEY,
                    value="27",
                    description="Default day of month to generate next calendar draft.",
                    updated_at=now,
                )
            )
        if self.catalogs.get_setting(CALENDAR_AUTO_GENERATION_ENABLED_KEY) is None:
            self.catalogs.upsert_setting(
                SystemSettingModel(
                    key=CALENDAR_AUTO_GENERATION_ENABLED_KEY,
                    value="false",
                    description="Whether monthly calendar draft generation runs automatically.",
                    updated_at=now,
                )
            )

    def get_calendar_generation_settings(self) -> dict[str, int | bool]:
        now = datetime.now(UTC)
        self._upsert_calendar_generation_defaults(now)

        enabled = self.catalogs.get_setting(CALENDAR_AUTO_GENERATION_ENABLED_KEY)
        day = self.catalogs.get_setting(CALENDAR_GENERATION_DAY_KEY)

        return {
            "auto_generation_enabled": (enabled.value.lower() == "true") if enabled else False,
            "generation_day": int(day.value) if day else 27,
        }

    def update_calendar_generation_settings(
        self,
        *,
        auto_generation_enabled: bool | None = None,
        generation_day: int | None = None,
    ) -> dict[str, int | bool]:
        now = datetime.now(UTC)
        self._upsert_calendar_generation_defaults(now)

        if auto_generation_enabled is not None:
            self.catalogs.upsert_setting(
                SystemSettingModel(
                    key=CALENDAR_AUTO_GENERATION_ENABLED_KEY,
                    value="true" if auto_generation_enabled else "false",
                    description="Whether monthly calendar draft generation runs automatically.",
                    updated_at=now,
                )
            )
        if generation_day is not None:
            self.catalogs.upsert_setting(
                SystemSettingModel(
                    key=CALENDAR_GENERATION_DAY_KEY,
                    value=str(generation_day),
                    description="Default day of month to generate next calendar draft.",
                    updated_at=now,
                )
            )

        return self.get_calendar_generation_settings()
