from datetime import UTC, datetime, date, timedelta
from uuid import uuid4

from backend.app.application.audit.service import AuditService
from backend.app.application.missions.errors import MissionServiceError
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
    ) -> None:
        self.mission_repo = mission_repo
        self.calendar_repo = calendar_repo
        self.availability_repo = availability_repo
        self.audit = audit

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
        # 1. Load ranking for the period
        ranking = self.mission_repo.get_ranking_by_period(year, month)
        if ranking is None:
            raise MissionServiceError(
                "ranking_not_found",
                "No ranking for this period. Generate the calendar first.",
            )

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
                if a.service_area_id in STRONG_AREAS
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

        # 3. Delete existing participants
        existing_participants = self.mission_repo.list_participants(mission_id)
        for participant in existing_participants:
            self.mission_repo.session.delete(participant)
        self.mission_repo.session.flush()

        # 4. Create new participants
        now = datetime.now(UTC)
        for doctor_id in doctor_ids:
            participant = MissionParticipantModel(
                id=str(uuid4()),
                mission_assignment_id=mission_id,
                doctor_id=doctor_id,
                selection_source="manual",
                ranking_position=None,
                score=None,
                reasons=None,
                warnings=None,
                created_at=now,
            )
            self.mission_repo.add_participant(participant)

        # 5. Update mission status
        mission.status = "confirmed"
        mission.confirmed_by = actor_id
        mission.confirmed_at = now
        mission.updated_at = now
        self.mission_repo.session.flush()

        # 6. Audit log
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

        # 7. Return updated mission
        return mission
