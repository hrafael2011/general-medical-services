from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from backend.app.application.audit.service import AuditService
from backend.app.application.calendars.errors import CalendarServiceError
from backend.app.domain.calendars.engine import CalendarEngine, GenerationContext
from backend.app.domain.calendars.scoring import AREA_WEIGHTS
from backend.app.domain.calendars.types import GenerationSummary
from backend.app.infrastructure.db.models.calendars import (
    CalendarAssignmentModel,
    UnresolvedGapModel,
)
from backend.app.infrastructure.repositories.availability import AvailabilityRepository
from backend.app.infrastructure.repositories.calendars import CalendarRepository
from backend.app.infrastructure.repositories.doctors import DoctorRepository

REQUIRED_AREAS = ["emergencia", "pista", "disponible"]


class GenerationService:
    def __init__(
        self,
        calendar_repo: CalendarRepository,
        doctor_repo: DoctorRepository,
        availability_repo: AvailabilityRepository,
        audit: AuditService | None = None,
    ) -> None:
        self.calendar_repo = calendar_repo
        self.doctor_repo = doctor_repo
        self.availability_repo = availability_repo
        self.audit = audit

    def generate(self, *, actor_id: str, calendar_id: str) -> GenerationSummary:
        calendar = self.calendar_repo.get_calendar_by_id(calendar_id)
        if calendar is None:
            raise CalendarServiceError("calendar_not_found", f"Calendar {calendar_id} not found.")

        version = self.calendar_repo.get_latest_version(calendar_id)
        if version is None:
            raise CalendarServiceError("version_not_found", f"No version found for calendar {calendar_id}.")

        if version.status == "approved":
            raise CalendarServiceError(
                "version_is_approved",
                "Cannot generate into an approved version. Create a new version first.",
            )

        # Load all service-active doctors
        doctors = self.doctor_repo.list_service_active()

        # Load allowed areas per doctor
        allowed_areas: dict[str, list[str]] = {
            d.id: self.doctor_repo.get_allowed_areas(d.id) for d in doctors
        }

        # Load availability per doctor
        availability: dict[str, list] = {}
        for d in doctors:
            records = self.availability_repo.list_availability_for_doctor(d.id)
            availability[d.id] = records

        # Load active restrictions per doctor
        restrictions: dict[str, list] = {}
        first_day = date(calendar.year, calendar.month, 1)
        import calendar as cal_module
        last_day_num = cal_module.monthrange(calendar.year, calendar.month)[1]
        last_day = date(calendar.year, calendar.month, last_day_num)
        for d in doctors:
            active_restrictions = self.availability_repo.list_active_restrictions_for_doctor(
                d.id, on_date=first_day
            )
            restrictions[d.id] = active_restrictions

        # Load existing assignments in this version
        existing = self.calendar_repo.list_assignments(version.id)
        existing_dicts = [
            {"doctor_id": a.doctor_id, "service_date": a.service_date, "service_area_id": a.service_area_id}
            for a in existing
        ]

        # Load 60-day historical assignments (before this month)
        history_end = first_day - timedelta(days=1)
        history_start = first_day - timedelta(days=60)
        historical = self.calendar_repo.list_assignments_in_date_range(history_start, history_end)
        historical_dicts = [
            {"doctor_id": a.doctor_id, "service_date": a.service_date, "service_area_id": a.service_area_id}
            for a in historical
        ]

        ctx = GenerationContext(
            year=calendar.year,
            month=calendar.month,
            doctors=doctors,
            allowed_areas=allowed_areas,
            availability=availability,
            restrictions=restrictions,
            existing_assignments=existing_dicts,
            historical_assignments=historical_dicts,
            mission_assignments=[],
            required_areas=REQUIRED_AREAS,
            area_weights=AREA_WEIGHTS,
        )

        engine = CalendarEngine()
        summary_raw = engine.generate(ctx)

        # Clear existing assignments and gaps for this version before persisting new ones
        for a in existing:
            self.calendar_repo.delete_assignment(a.id)
        for g in self.calendar_repo.list_gaps(version.id):
            self.calendar_repo.session.delete(g)
        self.calendar_repo.session.flush()

        now = datetime.now(UTC)

        # Persist results
        for result in summary_raw.slot_results:
            if result.assigned_doctor_id is not None:
                assignment = CalendarAssignmentModel(
                    id=str(uuid4()),
                    calendar_version_id=version.id,
                    service_date=result.slot.date,
                    service_area_id=result.slot.service_area_id,
                    doctor_id=result.assigned_doctor_id,
                    assignment_source="generated",
                    rationale=result.rationale,
                    created_by=actor_id,
                    created_at=now,
                )
                self.calendar_repo.add_assignment(assignment)
            else:
                gap = UnresolvedGapModel(
                    id=str(uuid4()),
                    calendar_version_id=version.id,
                    service_date=result.slot.date,
                    service_area_id=result.slot.service_area_id,
                    reason_code="no_eligible_candidates",
                    description=result.rationale.get("reason"),
                    created_at=now,
                )
                self.calendar_repo.add_gap(gap)

        if self.audit is not None:
            self.audit._create(
                actor_id=actor_id,
                action_type="generated",
                entity_type="calendar_version",
                entity_id=version.id,
                metadata={
                    "calendar_id": calendar_id,
                    "month": calendar.month,
                    "year": calendar.year,
                    "assigned": summary_raw.assigned_count,
                    "gaps": summary_raw.gap_count,
                },
            )

        return summary_raw
