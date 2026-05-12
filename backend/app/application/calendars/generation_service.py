from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from backend.app.application.audit.service import AuditService
from backend.app.application.calendars.errors import CalendarServiceError
from backend.app.domain.calendars.engine import CalendarEngine, GenerationContext
from backend.app.domain.calendars.scoring import AREA_WEIGHTS
from backend.app.domain.calendars.types import GenerationSummary
from backend.app.application.calendars.service import CALENDAR_GENERATION_MODES
from backend.app.infrastructure.db.models.calendars import (
    CalendarAssignmentModel,
    UnresolvedGapModel,
)
from backend.app.infrastructure.repositories.availability import AvailabilityRepository
from backend.app.infrastructure.repositories.calendars import CalendarRepository
from backend.app.infrastructure.repositories.catalogs import CatalogRepository
from backend.app.infrastructure.repositories.doctors import DoctorRepository
from backend.app.infrastructure.repositories.missions import MissionRepository

REQUIRED_AREA_CODES = ["emergencia", "pista", "disponible"]

class _AreaMapper:
    """Maps between service area codes (domain) and UUIDs (persistence)."""

    def __init__(self, session) -> None:
        repo = CatalogRepository(session)
        areas = repo.list_service_areas()
        self._code_to_uuid: dict[str, str] = {a.code: a.id for a in areas}
        self._uuid_to_code: dict[str, str] = {a.id: a.code for a in areas}

    def uuid(self, code: str) -> str:
        return self._code_to_uuid[code]

    def code(self, uuid: str) -> str:
        return self._uuid_to_code.get(uuid, uuid)

    @property
    def required_uuids(self) -> list[str]:
        return [self._code_to_uuid[c] for c in REQUIRED_AREA_CODES]

    @property
    def weighted_uuids(self) -> dict[str, float]:
        return {self._code_to_uuid[c]: w for c, w in AREA_WEIGHTS.items()}


class GenerationService:
    def __init__(
        self,
        calendar_repo: CalendarRepository,
        doctor_repo: DoctorRepository,
        availability_repo: AvailabilityRepository,
        mission_repo: MissionRepository,
        catalog_repo: CatalogRepository,
        audit: AuditService | None = None,
    ) -> None:
        self.calendar_repo = calendar_repo
        self.doctor_repo = doctor_repo
        self.availability_repo = availability_repo
        self.mission_repo = mission_repo
        self.catalog_repo = catalog_repo
        self.audit = audit

    def generate(
        self,
        *,
        actor_id: str,
        calendar_id: str,
        generation_mode: str = "assisted_auto",
    ) -> GenerationSummary:
        if generation_mode not in CALENDAR_GENERATION_MODES:
            raise CalendarServiceError(
                "invalid_generation_mode",
                f"Unsupported calendar generation mode: {generation_mode}.",
            )

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

        # Build code↔uuid mapper so the domain engine works with logical codes
        mapper = _AreaMapper(self.calendar_repo.session)

        # Load all service-active doctors
        doctors = self.doctor_repo.list_service_active()

        # Load allowed areas per doctor — convert UUIDs → codes for the domain engine
        allowed_areas: dict[str, list[str]] = {}
        for d in doctors:
            area_uuids = self.doctor_repo.get_allowed_areas(d.id)
            allowed_areas[d.id] = [mapper.code(uid) for uid in area_uuids]

        # Load availability per doctor
        availability: dict[str, list] = {}
        for d in doctors:
            records = self.availability_repo.list_availability_for_doctor(d.id)
            availability[d.id] = records

        # Load active restrictions per doctor
        restrictions: dict[str, list] = {}
        first_day = date(calendar.year, calendar.month, 1)
        for d in doctors:
            active_restrictions = self.availability_repo.list_active_restrictions_for_doctor(
                d.id, on_date=first_day
            )
            restrictions[d.id] = active_restrictions

        # Load existing assignments — convert service_area_id UUIDs → codes
        existing = self.calendar_repo.list_assignments(version.id)
        existing_dicts = [
            {"doctor_id": a.doctor_id, "service_date": a.service_date, "service_area_id": mapper.code(a.service_area_id)}
            for a in existing
        ]

        # Load 60-day historical assignments — convert service_area_id UUIDs → codes
        history_end = first_day - timedelta(days=1)
        history_start = first_day - timedelta(days=60)
        historical = self.calendar_repo.list_assignments_in_date_range(history_start, history_end)
        historical_dicts = [
            {"doctor_id": a.doctor_id, "service_date": a.service_date, "service_area_id": mapper.code(a.service_area_id)}
            for a in historical
        ]

        # Load 60-day confirmed missions for spacing rules
        confirmed_missions = self.mission_repo.list_confirmed_in_range(history_start, history_end)
        mission_assignments_raw: list[dict] = []
        for _mission, participants in confirmed_missions:
            for p in participants:
                mission_assignments_raw.append({
                    "doctor_id": p.doctor_id,
                    "mission_date": _mission.mission_date,
                })

        ctx = GenerationContext(
            year=calendar.year,
            month=calendar.month,
            doctors=doctors,
            allowed_areas=allowed_areas,
            availability=availability,
            restrictions=restrictions,
            existing_assignments=existing_dicts,
            historical_assignments=historical_dicts,
            mission_assignments=mission_assignments_raw,
            required_areas=REQUIRED_AREA_CODES,
            area_weights=AREA_WEIGHTS,
            monthly_service_targets={d.id: d.monthly_service_target for d in doctors},
            monthly_service_maxes={d.id: d.monthly_service_max for d in doctors},
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
        calendar.generation_mode = generation_mode
        calendar.updated_at = now

        # Persist results — convert service_area_id from codes back to UUIDs
        for result in summary_raw.slot_results:
            area_uuid = mapper.uuid(result.slot.service_area_id)
            if result.assigned_doctor_id is not None:
                assignment = CalendarAssignmentModel(
                    id=str(uuid4()),
                    calendar_version_id=version.id,
                    service_date=result.slot.date,
                    service_area_id=area_uuid,
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
                    service_area_id=area_uuid,
                    reason_code="no_eligible_candidates",
                    description=result.rationale.get("reason"),
                    created_at=now,
                )
                self.calendar_repo.add_gap(gap)

        if self.audit is not None:
            self.audit._create(
                actor_id=actor_id,
                action_type="calendar_generated",
                entity_type="calendar_version",
                entity_id=version.id,
                metadata={
                    "calendar_id": calendar_id,
                    "month": calendar.month,
                    "year": calendar.year,
                    "assigned": summary_raw.assigned_count,
                    "gaps": summary_raw.gap_count,
                    "generation_mode": generation_mode,
                },
            )

        return summary_raw
