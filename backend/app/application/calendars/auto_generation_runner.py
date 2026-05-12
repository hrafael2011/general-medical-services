import asyncio
import logging
import time

from sqlalchemy.exc import OperationalError

from backend.app.application.audit.service import AuditService
from backend.app.application.calendars.auto_generation_service import AutoCalendarGenerationService
from backend.app.application.calendars.generation_service import GenerationService
from backend.app.application.calendars.service import CalendarService
from backend.app.application.catalogs.service import CatalogService
from backend.app.core.config import settings
from backend.app.infrastructure.db.session import SessionLocal
from backend.app.infrastructure.repositories.audit import AuditRepository
from backend.app.infrastructure.repositories.availability import AvailabilityRepository
from backend.app.infrastructure.repositories.calendars import CalendarRepository
from backend.app.infrastructure.repositories.catalogs import CatalogRepository
from backend.app.infrastructure.repositories.doctors import DoctorRepository
from backend.app.infrastructure.repositories.missions import MissionRepository

logger = logging.getLogger(__name__)


async def calendar_auto_generation_loop() -> None:
    interval = max(60, settings.calendar_auto_generation_check_interval_seconds)
    while True:
        try:
            await asyncio.to_thread(run_calendar_auto_generation_once)
        except Exception:
            logger.exception("Calendar auto-generation check failed.")
        await asyncio.sleep(interval)


def run_calendar_auto_generation_once() -> dict:
    last_error: OperationalError | None = None
    for attempt in range(3):
        try:
            return _run_calendar_auto_generation_once()
        except OperationalError as exc:
            last_error = exc
            logger.warning(
                "Calendar auto-generation DB connection failed on attempt %s.",
                attempt + 1,
                exc_info=True,
            )
            time.sleep(0.5)
    raise last_error


def _run_calendar_auto_generation_once() -> dict:
    with SessionLocal() as session:
        audit = AuditService(AuditRepository(session))
        calendar_repo = CalendarRepository(session)
        catalog_repo = CatalogRepository(session)
        generation = GenerationService(
            calendar_repo,
            DoctorRepository(session),
            AvailabilityRepository(session),
            MissionRepository(session),
            catalog_repo,
            audit=audit,
        )
        service = AutoCalendarGenerationService(
            calendar_service=CalendarService(calendar_repo, audit=audit),
            generation_service=generation,
            catalog_service=CatalogService(catalog_repo),
        )
        result = service.run_due()
        session.commit()
        logger.info("Calendar auto-generation check finished: %s", result)
        return result
