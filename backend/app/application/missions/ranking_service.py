from calendar import monthrange
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from backend.app.application.audit.service import AuditService
from backend.app.domain.calendars.scoring import AREA_WEIGHTS, MISSION_WEIGHT
from backend.app.infrastructure.db.models.missions import (
    MissionCandidateRankingEntryModel,
    MissionCandidateRankingModel,
)
from backend.app.infrastructure.repositories.calendars import CalendarRepository
from backend.app.infrastructure.repositories.doctors import DoctorRepository
from backend.app.infrastructure.repositories.missions import MissionRepository


class MissionRankingService:
    def __init__(
        self,
        mission_repo: MissionRepository,
        doctor_repo: DoctorRepository,
        calendar_repo: CalendarRepository,
        audit: AuditService | None = None,
    ) -> None:
        self.mission_repo = mission_repo
        self.doctor_repo = doctor_repo
        self.calendar_repo = calendar_repo
        self.audit = audit

    def generate_ranking(
        self,
        *,
        actor_id: str,
        year: int,
        month: int,
        calendar_version_id: str | None = None,
    ) -> MissionCandidateRankingModel:
        """Generate (or regenerate) the mission candidate ranking for a given month/year.

        If a ranking already exists for this period, all its entries are deleted and
        the ranking record is reused with an updated ``generated_at`` timestamp.
        Otherwise a new ranking record is created.
        """
        now = datetime.now(UTC)

        # --- Step 1: reuse or create the ranking record ---
        ranking = self.mission_repo.get_ranking_by_period(year, month)
        if ranking is not None:
            # Delete all existing entries for this ranking
            existing_entries = self.mission_repo.list_ranking_entries(ranking.id)
            for entry in existing_entries:
                self.mission_repo.session.delete(entry)
            self.mission_repo.session.flush()
            # Update metadata on the existing record
            ranking.generated_at = now
            ranking.calendar_version_id = calendar_version_id
            ranking.created_by = actor_id
            self.mission_repo.session.flush()
        else:
            ranking = MissionCandidateRankingModel(
                id=str(uuid4()),
                month=month,
                year=year,
                calendar_version_id=calendar_version_id,
                generated_at=now,
                created_by=actor_id,
            )
            self.mission_repo.add_ranking(ranking)

        # --- Step 2: load service-active doctors ---
        all_doctors = self.doctor_repo.list_service_active()

        # --- Step 3: filter to mission participants ---
        doctors = [d for d in all_doctors if d.participa_misiones]

        # --- Date ranges ---
        first_day = date(year, month, 1)
        last_day = date(year, month, monthrange(year, month)[1])
        recent_end = first_day - timedelta(days=1)   # day before the month starts
        recent_start = first_day - timedelta(days=60)

        # Pre-fetch all calendar assignments for the relevant date ranges once,
        # then filter per-doctor in memory to avoid N+1 queries.
        monthly_assignments = self.calendar_repo.list_assignments_in_date_range(
            start_date=first_day, end_date=last_day
        )
        recent_assignments = self.calendar_repo.list_assignments_in_date_range(
            start_date=recent_start, end_date=recent_end
        )

        # --- Step 4: compute load score per doctor ---
        scored: list[tuple[float, float, float, float, bool, str]] = []
        # Each tuple: (total_load_score, monthly_svc, recent_svc, monthly_mission, has_mission_this_month, doctor_id)

        for doctor in doctors:
            doc_id = doctor.id

            # monthly_service_load
            doctor_monthly = [
                a for a in monthly_assignments if a.doctor_id == doc_id
            ]
            monthly_service_load: float = sum(
                AREA_WEIGHTS.get(a.service_area_id, 1.0) for a in doctor_monthly
            )

            # recent_service_load (last 60 days before the month)
            doctor_recent = [
                a for a in recent_assignments if a.doctor_id == doc_id
            ]
            recent_service_load: float = sum(
                AREA_WEIGHTS.get(a.service_area_id, 1.0) for a in doctor_recent
            )

            # monthly_mission_load
            mission_participations = self.mission_repo.list_participations_for_doctor_in_range(
                doc_id, first_day, last_day
            )
            monthly_mission_load: float = len(mission_participations) * MISSION_WEIGHT
            has_mission_this_month: bool = len(mission_participations) > 0

            # total_load_score
            total_load_score: float = (
                monthly_service_load
                + recent_service_load * 0.5
                + monthly_mission_load
            )
            if has_mission_this_month:
                total_load_score += 2.0

            scored.append((
                total_load_score,
                monthly_service_load,
                recent_service_load,
                monthly_mission_load,
                has_mission_this_month,
                doc_id,
            ))

        # --- Step 5: sort ascending by total_load_score ---
        scored.sort(key=lambda t: t[0])

        # --- Step 6 & 7: create ranking entries ---
        for position, (total, monthly_svc, recent_svc, monthly_mission, _, doc_id) in enumerate(
            scored, start=1
        ):
            entry = MissionCandidateRankingEntryModel(
                id=str(uuid4()),
                mission_candidate_ranking_id=ranking.id,
                doctor_id=doc_id,
                ranking_position=position,
                total_load_score=total,
                monthly_service_load=monthly_svc,
                recent_service_load=recent_svc,
                monthly_mission_load=monthly_mission,
                eligible=True,
                reasons=None,
                warnings=None,
            )
            self.mission_repo.add_ranking_entry(entry)

        # --- Audit ---
        if self.audit is not None:
            self.audit.log_mission_ranking_generated(actor_id, ranking)

        return ranking

    def get_ranking(self, *, year: int, month: int) -> MissionCandidateRankingModel | None:
        """Return the existing ranking for the given period, or None."""
        return self.mission_repo.get_ranking_by_period(year, month)
