from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from backend.app.application.audit.service import AuditService
from backend.app.application.calendars.errors import CalendarServiceError
from backend.app.domain.availability_rules import belongs_to_operational_month
from backend.app.domain.calendars.engine import CalendarEngine, GenerationContext
from backend.app.domain.calendars.scoring import AREA_WEIGHTS
from backend.app.domain.calendars.types import GenerationSummary, SlotRequest
from backend.app.application.calendars.service import CALENDAR_GENERATION_MODES
from backend.app.infrastructure.db.models.calendars import (
    CalendarAssignmentModel,
    UnresolvedGapModel,
)
from backend.app.infrastructure.db.models.catalogs import ServiceAreaModel
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

    def missing_required_codes(self) -> list[str]:
        return [code for code in REQUIRED_AREA_CODES if code not in self._code_to_uuid]


class GenerationService:
    def __init__(
        self,
        calendar_repo: CalendarRepository,
        doctor_repo: DoctorRepository,
        availability_repo: AvailabilityRepository,
        mission_repo: MissionRepository,
        catalog_repo: CatalogRepository,
        audit: AuditService | None = None,
        mission_ranking_service=None,
    ) -> None:
        self.calendar_repo = calendar_repo
        self.doctor_repo = doctor_repo
        self.availability_repo = availability_repo
        self.mission_repo = mission_repo
        self.catalog_repo = catalog_repo
        self.audit = audit
        self.mission_ranking_service = mission_ranking_service

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

        approved_weeks = [
            week
            for week in self.calendar_repo.list_weeks_by_version(version.id)
            if week.status == "approved"
        ]
        if approved_weeks:
            raise CalendarServiceError(
                "week_locked",
                "No se puede generar con reglas porque hay semanas aprobadas. Desbloquea las semanas primero.",
            )

        # Build code↔uuid mapper so the domain engine works with logical codes
        mapper = _AreaMapper(self.calendar_repo.session)
        missing_area_codes = mapper.missing_required_codes()
        if missing_area_codes:
            raise CalendarServiceError(
                "generation_configuration_incomplete",
                "No se puede generar con reglas porque faltan áreas de servicio "
                f"requeridas en el catálogo: {', '.join(missing_area_codes)}.",
            )

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

        # Build a set of slots that already have assignments (manual or prior generated)
        already_assigned: set[tuple[date, str]] = set()
        for a in existing:
            already_assigned.add((a.service_date, mapper.code(a.service_area_id)))

        # Clear existing gaps for this version — they will be re-evaluated
        for g in self.calendar_repo.list_gaps(version.id):
            self.calendar_repo.session.delete(g)
        self.calendar_repo.session.flush()

        now = datetime.now(UTC)
        calendar.generation_mode = generation_mode
        calendar.updated_at = now

        # Persist NEW results only — skip slots that already have assignments
        for result in summary_raw.slot_results:
            area_uuid = mapper.uuid(result.slot.service_area_id)
            slot_key = (result.slot.date, result.slot.service_area_id)
            if slot_key in already_assigned:
                continue  # keep existing assignment untouched

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
                # Resolve service_start_at from ServiceAreaModel.start_hour
                area = self.calendar_repo.session.get(ServiceAreaModel, area_uuid)
                if area and area.start_hour is not None:
                    assignment.service_start_at = datetime(
                        result.slot.date.year, result.slot.date.month, result.slot.date.day,
                        area.start_hour, 0, 0, tzinfo=UTC,
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

        # Generate ranking immediately after batch assignment (no debounce needed)
        if self.mission_ranking_service is not None:
            try:
                self.mission_ranking_service.generate_ranking(
                    actor_id=actor_id,
                    year=calendar.year,
                    month=calendar.month,
                    calendar_version_id=version.id,
                )
            except Exception:
                import logging
                _logger = logging.getLogger(__name__)
                _logger.exception(
                    "Failed to generate ranking after batch generation for %d/%02d (non-fatal)",
                    calendar.year, calendar.month,
                )

        return summary_raw

    def fill_gaps(
        self,
        *,
        actor_id: str,
        calendar_id: str,
    ) -> dict:
        """Fill only unresolved gaps without touching existing assignments.

        Returns a dict with ``filled`` (int) and ``remaining`` (int).
        """
        calendar = self.calendar_repo.get_calendar_by_id(calendar_id)
        if calendar is None:
            raise CalendarServiceError("calendar_not_found", f"Calendar {calendar_id} not found.")

        version = self.calendar_repo.get_latest_version(calendar_id)
        if version is None:
            raise CalendarServiceError("version_not_found", f"No version found for calendar {calendar_id}.")

        if version.status == "approved":
            raise CalendarServiceError(
                "version_is_approved",
                "Cannot fill gaps in an approved version.",
            )

        gaps = self.calendar_repo.list_gaps(version.id)
        if not gaps:
            return {"filled": 0, "remaining": 0, "message": "No hay huecos por llenar."}

        # Build code↔uuid mapper
        mapper = _AreaMapper(self.calendar_repo.session)

        # Load all service-active doctors
        doctors = self.doctor_repo.list_service_active()

        # Load allowed areas per doctor (UUIDs → codes)
        allowed_areas: dict[str, list[str]] = {}
        for d in doctors:
            area_uuids = self.doctor_repo.get_allowed_areas(d.id)
            allowed_areas[d.id] = [mapper.code(uid) for uid in area_uuids]

        # Load availability per doctor
        availability: dict[str, list] = {}
        for d in doctors:
            availability[d.id] = self.availability_repo.list_availability_for_doctor(d.id)

        # Load active restrictions
        first_day = date(calendar.year, calendar.month, 1)
        restrictions: dict[str, list] = {}
        for d in doctors:
            restrictions[d.id] = self.availability_repo.list_active_restrictions_for_doctor(
                d.id, on_date=first_day
            )

        # Load existing assignments
        existing = self.calendar_repo.list_assignments(version.id)
        existing_dicts = [
            {"doctor_id": a.doctor_id, "service_date": a.service_date, "service_area_id": mapper.code(a.service_area_id)}
            for a in existing
        ]

        # Load historical context
        history_end = first_day - timedelta(days=1)
        history_start = first_day - timedelta(days=60)
        historical = self.calendar_repo.list_assignments_in_date_range(history_start, history_end)
        historical_dicts = [
            {"doctor_id": a.doctor_id, "service_date": a.service_date, "service_area_id": mapper.code(a.service_area_id)}
            for a in historical
        ]

        confirmed_missions = self.mission_repo.list_confirmed_in_range(history_start, history_end)
        mission_assignments_raw: list[dict] = []
        for _mission, participants in confirmed_missions:
            for p in participants:
                mission_assignments_raw.append({
                    "doctor_id": p.doctor_id,
                    "mission_date": _mission.mission_date,
                })

        area_weights_dict: dict[str, float] = {
            sa.id: float(sa.load_weight)
            for sa in self.catalog_repo.list_service_areas()
        }

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
        now = datetime.now(UTC)
        filled = 0

        for gap in gaps:
            area_code = mapper.code(gap.service_area_id)
            slot = SlotRequest(
                date=gap.service_date,
                service_area_id=area_code,
                area_weight=area_weights_dict.get(gap.service_area_id, 1.0),
            )

            # Get eligible doctors for this slot, considering current assignments
            current_snapshot = [
                a for a in existing_dicts
                if a["service_date"] != gap.service_date or a["service_area_id"] != area_code
            ]
            eligible = engine.get_eligible_doctors(slot, ctx, current_snapshot)
            if not eligible:
                continue

            # Pick best candidate: fewest monthly assignments so far
            monthly_counts = {}
            for a in existing_dicts:
                if belongs_to_operational_month(a["service_date"], calendar.year, calendar.month):
                    monthly_counts[a["doctor_id"]] = monthly_counts.get(a["doctor_id"], 0) + 1

            best = min(eligible, key=lambda d: monthly_counts.get(d.id, 0))

            # Create assignment
            area_uuid = mapper.uuid(area_code)
            assignment = CalendarAssignmentModel(
                id=str(uuid4()),
                calendar_version_id=version.id,
                service_date=gap.service_date,
                service_area_id=area_uuid,
                doctor_id=best.id,
                assignment_source="generated",
                rationale={"fill_gaps": True, "reason": "Auto-filled from gap"},
                created_by=actor_id,
                created_at=now,
            )
            area = self.calendar_repo.session.get(ServiceAreaModel, area_uuid)
            if area and area.start_hour is not None:
                assignment.service_start_at = datetime(
                    gap.service_date.year, gap.service_date.month, gap.service_date.day,
                    area.start_hour, 0, 0, tzinfo=UTC,
                )
            self.calendar_repo.add_assignment(assignment)

            # Update the running snapshot
            existing_dicts.append({
                "doctor_id": best.id,
                "service_date": gap.service_date,
                "service_area_id": area_code,
            })

            # Remove the gap
            self.calendar_repo.session.delete(gap)
            filled += 1

        self.calendar_repo.session.flush()

        if self.audit is not None:
            self.audit._create(
                actor_id=actor_id,
                action_type="calendar_gaps_filled",
                entity_type="calendar_version",
                entity_id=version.id,
                metadata={
                    "calendar_id": calendar_id,
                    "filled": filled,
                    "remaining": len(gaps) - filled,
                },
            )

        # Generate ranking after filling gaps
        if self.mission_ranking_service is not None:
            try:
                self.mission_ranking_service.generate_ranking(
                    actor_id=actor_id,
                    year=calendar.year,
                    month=calendar.month,
                    calendar_version_id=version.id,
                )
            except Exception:
                import logging
                _logger = logging.getLogger(__name__)
                _logger.exception(
                    "Failed to generate ranking after fill_gaps for %d/%02d (non-fatal)",
                    calendar.year, calendar.month,
                )

        return {
            "filled": filled,
            "remaining": len(gaps) - filled,
            "message": f"Se llenaron {filled} huecos. {len(gaps) - filled} pendientes.",
        }
