from datetime import UTC, date, datetime

from backend.app.application.calendars.errors import CalendarServiceError
from backend.app.application.calendars.generation_service import GenerationService
from backend.app.application.calendars.service import CalendarService
from backend.app.application.catalogs.service import CatalogService

SYSTEM_AUTO_GENERATION_ACTOR = "system:calendar-auto-generation"


class AutoCalendarGenerationService:
    def __init__(
        self,
        *,
        calendar_service: CalendarService,
        generation_service: GenerationService,
        catalog_service: CatalogService,
    ) -> None:
        self.calendar_service = calendar_service
        self.generation_service = generation_service
        self.catalog_service = catalog_service

    def run_due(
        self,
        *,
        today: date | None = None,
        actor_id: str = SYSTEM_AUTO_GENERATION_ACTOR,
    ) -> dict:
        current_day = today or datetime.now(UTC).date()
        settings = self.catalog_service.get_calendar_generation_settings()

        if not settings["auto_generation_enabled"]:
            return {
                "status": "skipped",
                "reason": "disabled",
                "calendar_id": None,
                "month": None,
                "year": None,
                "assigned_count": 0,
                "gap_count": 0,
            }

        generation_day = int(settings["generation_day"])
        if current_day.day != generation_day:
            return {
                "status": "skipped",
                "reason": "not_due",
                "calendar_id": None,
                "month": None,
                "year": None,
                "assigned_count": 0,
                "gap_count": 0,
            }

        year, month = _next_month(current_day.year, current_day.month)
        existing = self.calendar_service.repo.get_calendar_by_period(year, month)
        if existing is not None:
            return {
                "status": "skipped",
                "reason": "calendar_already_exists",
                "calendar_id": existing.id,
                "month": month,
                "year": year,
                "assigned_count": 0,
                "gap_count": 0,
            }

        try:
            calendar = self.calendar_service.create_calendar(
                actor_id=actor_id,
                month=month,
                year=year,
                notes="Generated automatically by monthly calendar job.",
                generation_mode="scheduled_auto",
            )
        except CalendarServiceError as exc:
            if exc.code == "calendar_already_exists":
                existing = self.calendar_service.repo.get_calendar_by_period(year, month)
                return {
                    "status": "skipped",
                    "reason": "calendar_already_exists",
                    "calendar_id": existing.id if existing else None,
                    "month": month,
                    "year": year,
                    "assigned_count": 0,
                    "gap_count": 0,
                }
            raise

        summary = self.generation_service.generate(
            actor_id=actor_id,
            calendar_id=calendar.id,
            generation_mode="scheduled_auto",
        )

        return {
            "status": "generated",
            "reason": None,
            "calendar_id": calendar.id,
            "month": month,
            "year": year,
            "assigned_count": summary.assigned_count,
            "gap_count": summary.gap_count,
        }


def _next_month(year: int, month: int) -> tuple[int, int]:
    if month == 12:
        return year + 1, 1
    return year, month + 1
