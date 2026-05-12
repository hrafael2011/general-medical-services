from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from backend.app.application.audit.service import AuditService
from backend.app.application.missions.errors import MissionServiceError
from backend.app.application.notifications.triggers import NotificationTriggers
from backend.app.domain.calendars.scoring import STRONG_AREAS
from backend.app.infrastructure.db.models.missions import (
    MissionAssignmentModel,
    MissionCandidateRankingEntryModel,
    MissionParticipantModel,
)
from backend.app.infrastructure.repositories.availability import AvailabilityRepository
from backend.app.infrastructure.repositories.calendars import CalendarRepository
from backend.app.infrastructure.repositories.missions import MissionRepository


class MissionCandidateService:
    def __init__(
        self,
        mission_repo: MissionRepository,
        calendar_repo: CalendarRepository,
        availability_repo: AvailabilityRepository,
        audit: AuditService | None = None,
        triggers: NotificationTriggers | None = None,
    ) -> None:
        self.mission_repo = mission_repo
        self.calendar_repo = calendar_repo
        self.availability_repo = availability_repo
        self.audit = audit
        self.triggers = triggers

    def _service_area_code_map(self) -> dict[str, str]:
        """Map persisted service area UUIDs to domain codes, preserving codes as-is."""
        return {area.id: area.code for area in self.calendar_repo.list_service_areas()}

    def _service_area_code(self, service_area_id: str, area_codes_by_id: dict[str, str]) -> str:
        return area_codes_by_id.get(service_area_id, service_area_id)

    def _is_strong_area(self, service_area_id: str, area_codes_by_id: dict[str, str]) -> bool:
        return self._service_area_code(service_area_id, area_codes_by_id) in STRONG_AREAS

    def _get_approved_period_ranking(self, year: int, month: int):
        approved_version = self.calendar_repo.get_approved_version_by_period(year, month)
        if approved_version is None:
            raise MissionServiceError(
                "approved_calendar_required",
                "No approved calendar exists for this period.",
            )
        ranking = self.mission_repo.get_ranking_by_period(
            year,
            month,
            calendar_version_id=approved_version.id,
        )
        if ranking is None:
            raise MissionServiceError(
                "ranking_not_found",
                "No ranking exists for the approved calendar.",
            )
        return ranking

    def recommend_candidates(
        self,
        *,
        year: int,
        month: int,
        mission_date: date,
        participant_count: int,
        include_alternates: bool = False,
    ) -> dict:
        """Return {"primary": list[entries], "alternates": list[entries]} for a mission date.

        Primary candidates: eligible entries with no hard blocks and no same-day assignment,
        up to participant_count.
        Alternates (when include_alternates=True): next entries with only soft warnings,
        up to participant_count more.
        """
        # 1. Load ranking for the approved calendar version in the period.
        ranking = self._get_approved_period_ranking(year, month)

        # 2. Load all entries (sorted by position ascending)
        entries: list[MissionCandidateRankingEntryModel] = self.mission_repo.list_ranking_entries(
            ranking.id
        )

        # Pre-load all assignments in the 14-day look-back window and on the mission date
        lookback_start = mission_date - timedelta(days=14)
        lookback_end = mission_date - timedelta(days=1)
        recent_assignments = self.calendar_repo.list_assignments_in_date_range(
            lookback_start, lookback_end
        )
        same_day_assignments = self.calendar_repo.list_assignments_in_date_range(
            mission_date, mission_date
        )
        area_codes_by_id = self._service_area_code_map()

        primary: list[MissionCandidateRankingEntryModel] = []
        alternates: list[MissionCandidateRankingEntryModel] = []

        for entry in entries:
            doctor_id = entry.doctor_id

            # 3a. Check hard-block restrictions on mission_date
            restrictions = self.availability_repo.list_active_restrictions_for_doctor(
                doctor_id, on_date=mission_date
            )
            has_hard_block = any(r.severity == "hard_block" for r in restrictions)
            if has_hard_block:
                # Skip entirely — hard block disqualifies from both primary and alternates
                continue

            warnings: list[str] = list(entry.warnings or [])

            # 3b. Check spacing: strong-area assignment within 7 days
            doctor_recent = [
                a for a in recent_assignments if a.doctor_id == doctor_id
            ]
            strong_recent = [
                a for a in doctor_recent
                if self._is_strong_area(a.service_area_id, area_codes_by_id)
                and (mission_date - a.service_date).days <= 7
            ]
            if strong_recent:
                if "ocupado: turno reciente" not in warnings:
                    warnings.append("ocupado: turno reciente")

            # 3c. Check if doctor already has a same-day assignment
            doctor_same_day = [
                a for a in same_day_assignments if a.doctor_id == doctor_id
            ]
            has_same_day = len(doctor_same_day) > 0
            if has_same_day:
                if "ocupado: tiene turno ese día" not in warnings:
                    warnings.append("ocupado: tiene turno ese día")

            # 4. Primary: eligible=True, no same-day conflict, and not over the count yet
            if entry.eligible and not has_same_day:
                if len(primary) < participant_count:
                    primary.append(entry)
                    continue

            # 5. Alternates: soft warnings only (no hard blocks — already filtered above)
            if include_alternates and not has_same_day:
                if len(alternates) < participant_count:
                    alternates.append(entry)

        if not include_alternates:
            alternates = []

        return {"primary": primary, "alternates": alternates}

    def rank_candidates_for_date(
        self,
        *,
        year: int,
        month: int,
        mission_date: date,
    ) -> list[dict]:
        """Return the full monthly ranking adjusted for one mission date.

        The monthly ranking remains the base ordering. This method adds
        date-specific operational state so the UI can show why a highly ranked
        doctor can or cannot be selected for that mission date.
        """
        ranking = self._get_approved_period_ranking(year, month)

        entries: list[MissionCandidateRankingEntryModel] = self.mission_repo.list_ranking_entries(
            ranking.id
        )

        lookback_start = mission_date - timedelta(days=14)
        lookback_end = mission_date - timedelta(days=1)
        recent_assignments = self.calendar_repo.list_assignments_in_date_range(
            lookback_start, lookback_end
        )
        same_day_assignments = self.calendar_repo.list_assignments_in_date_range(
            mission_date, mission_date
        )
        area_codes_by_id = self._service_area_code_map()

        ranked: list[dict] = []
        for entry in entries:
            doctor_id = entry.doctor_id
            reasons: list[str] = []
            warnings: list[str] = list(entry.warnings or [])
            selectable = bool(entry.eligible)

            restrictions = self.availability_repo.list_active_restrictions_for_doctor(
                doctor_id, on_date=mission_date
            )
            has_hard_block = any(r.severity == "hard_block" for r in restrictions)
            if has_hard_block:
                selectable = False
                reasons.append("Tiene una restricción dura para la fecha.")

            has_same_day = any(a.doctor_id == doctor_id for a in same_day_assignments)
            if has_same_day:
                selectable = False
                reasons.append("Tiene servicio asignado ese día.")

            doctor_recent = [
                a for a in recent_assignments if a.doctor_id == doctor_id
            ]
            strong_recent = [
                a for a in doctor_recent
                if self._is_strong_area(a.service_area_id, area_codes_by_id)
                and (mission_date - a.service_date).days <= 7
            ]
            if strong_recent and "Servicio fuerte reciente." not in warnings:
                warnings.append("Servicio fuerte reciente.")

            if not entry.eligible and not reasons:
                selectable = False
                reasons.append("No elegible según el ranking mensual.")

            if not selectable:
                status = "unavailable"
            elif warnings:
                status = "alternate"
            else:
                status = "recommended"

            if selectable:
                ranked.append({
                    "entry": entry,
                    "selectable": selectable,
                    "recommendation_status": status,
                    "reasons": reasons,
                    "warnings": warnings,
                })

        ranked.sort(
            key=lambda item: (
                item["entry"].total_load_score,
                item["entry"].ranking_position,
            )
        )
        for index, item in enumerate(ranked, start=1):
            item["adjusted_position"] = index

        return ranked

    def create_mission(
        self,
        *,
        actor_id: str,
        mission_date: date,
        participant_count: int,
        location: str | None,
        description: str | None,
    ) -> MissionAssignmentModel:
        """Create a new mission assignment with status='draft'."""
        now = datetime.now(UTC)
        mission = MissionAssignmentModel(
            id=str(uuid4()),
            mission_date=mission_date,
            mission_start_at=None,
            mission_end_at=None,
            participant_count=participant_count,
            location=location,
            description=description,
            source="manual",
            status="draft",
            created_by=actor_id,
            confirmed_by=None,
            confirmed_at=None,
            created_at=now,
            updated_at=now,
        )
        return self.mission_repo.add_mission(mission)

    def update_mission(
        self,
        *,
        actor_id: str,
        mission_id: str,
        updates: dict,
    ) -> MissionAssignmentModel:
        mission = self.mission_repo.get_mission_by_id(mission_id)
        if mission is None:
            raise MissionServiceError(
                "mission_not_found",
                f"Mission with id {mission_id} not found.",
            )

        before = {
            "mission_date": str(mission.mission_date),
            "participant_count": mission.participant_count,
            "location": mission.location,
            "description": mission.description,
            "mission_start_at": str(mission.mission_start_at) if mission.mission_start_at else None,
            "mission_end_at": str(mission.mission_end_at) if mission.mission_end_at else None,
        }

        allowed_fields = {
            "mission_date",
            "participant_count",
            "location",
            "description",
            "mission_start_at",
            "mission_end_at",
        }
        for field, value in updates.items():
            if field in allowed_fields:
                setattr(mission, field, value)

        mission.updated_at = datetime.now(UTC)
        self.mission_repo.session.flush()

        if self.audit is not None:
            self.audit._create(
                actor_id=actor_id,
                action_type="mission_updated",
                entity_type="mission",
                entity_id=mission_id,
                before=before,
                after={
                    "mission_date": str(mission.mission_date),
                    "participant_count": mission.participant_count,
                    "location": mission.location,
                    "description": mission.description,
                    "mission_start_at": str(mission.mission_start_at) if mission.mission_start_at else None,
                    "mission_end_at": str(mission.mission_end_at) if mission.mission_end_at else None,
                },
            )

        return mission

    def delete_mission(
        self,
        *,
        actor_id: str,
        mission_id: str,
    ) -> MissionAssignmentModel:
        mission = self.mission_repo.get_mission_by_id(mission_id)
        if mission is None:
            raise MissionServiceError(
                "mission_not_found",
                f"Mission with id {mission_id} not found.",
            )

        now = datetime.now(UTC)
        mission.deleted_at = now
        mission.updated_at = now
        self.mission_repo.session.flush()

        if self.audit is not None:
            self.audit._create(
                actor_id=actor_id,
                action_type="mission_deleted",
                entity_type="mission",
                entity_id=mission_id,
                before={"status": mission.status},
                after={"deleted_at": str(mission.deleted_at)},
            )

        return mission

    def confirm_mission(
        self,
        *,
        actor_id: str,
        mission_id: str,
        doctor_ids: list[str],
    ) -> MissionAssignmentModel:
        """Confirm a mission by assigning participants and setting status to 'confirmed'."""
        # 1. Load mission
        mission = self.mission_repo.get_mission_by_id(mission_id)
        if mission is None:
            raise MissionServiceError(
                "mission_not_found",
                f"Mission with id {mission_id} not found.",
            )

        # 2. Guard: already confirmed
        if mission.status == "confirmed":
            raise MissionServiceError(
                "already_confirmed",
                f"Mission {mission_id} is already confirmed.",
            )

        # 3. Validate selected doctors against date-specific availability.
        eligible_items = self.rank_candidates_for_date(
            year=mission.mission_date.year,
            month=mission.mission_date.month,
            mission_date=mission.mission_date,
        )
        ranking_entries_by_doctor = {
            item["entry"].doctor_id: item["entry"]
            for item in eligible_items
        }
        unavailable_doctor_ids = [
            doctor_id for doctor_id in doctor_ids
            if doctor_id not in ranking_entries_by_doctor
        ]
        if unavailable_doctor_ids:
            raise MissionServiceError(
                "candidate_not_available",
                "One or more selected doctors are not available for this mission date.",
            )

        # 4. Delete existing participants
        existing_participants = self.mission_repo.list_participants(mission_id)
        for participant in existing_participants:
            self.mission_repo.session.delete(participant)
        self.mission_repo.session.flush()

        # 5. Create new participants with rationale
        now = datetime.now(UTC)
        for doctor_id in doctor_ids:
            entry = ranking_entries_by_doctor.get(doctor_id)
            participant = MissionParticipantModel(
                id=str(uuid4()),
                mission_assignment_id=mission_id,
                doctor_id=doctor_id,
                selection_source="ranking" if entry else "manual",
                ranking_position=entry.ranking_position if entry else None,
                score=entry.total_load_score if entry else None,
                reasons=dict(entry.reasons) if entry and entry.reasons else None,
                warnings=list(entry.warnings) if entry and entry.warnings else None,
                created_at=now,
            )
            self.mission_repo.add_participant(participant)

        # 6. Update mission status
        mission.status = "confirmed"
        mission.confirmed_by = actor_id
        mission.confirmed_at = now
        mission.updated_at = now
        self.mission_repo.session.flush()

        # 7. Audit log
        if self.audit is not None:
            self.audit._create(
                actor_id=actor_id,
                action_type="mission_confirmed",
                entity_type="mission",
                entity_id=mission_id,
                after={
                    "status": mission.status,
                    "confirmed_by": actor_id,
                    "doctor_ids": doctor_ids,
                },
            )

        # 8. Queue notifications
        if self.triggers is not None:
            participants = self.mission_repo.list_participants(mission_id)
            self.triggers.on_mission_confirmed(
                actor_id=actor_id,
                mission=mission,
                participants=participants,
                encargado_phone=None,
            )

        # 9. Return updated mission
        return mission
