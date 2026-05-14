from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.infrastructure.db.models.missions import (
    MissionAssignmentModel,
    MissionCandidateRankingEntryModel,
    MissionCandidateRankingModel,
    MissionParticipantModel,
)


class MissionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    # --- Mission Assignments ---

    def add_mission(self, mission: MissionAssignmentModel) -> MissionAssignmentModel:
        self.session.add(mission)
        self.session.flush()
        return mission

    def get_mission_by_id(self, mission_id: str) -> MissionAssignmentModel | None:
        mission = self.session.get(MissionAssignmentModel, mission_id)
        if mission is None or mission.deleted_at is not None:
            return None
        return mission

    def list_missions(self) -> list[MissionAssignmentModel]:
        stmt = (
            select(MissionAssignmentModel)
            .where(MissionAssignmentModel.deleted_at.is_(None))
            .order_by(MissionAssignmentModel.mission_date.desc())
        )
        return list(self.session.scalars(stmt))

    def list_missions_for_month(self, year: int, month: int) -> list[MissionAssignmentModel]:
        """All missions in a given month."""
        from calendar import monthrange
        first = date(year, month, 1)
        last = date(year, month, monthrange(year, month)[1])
        stmt = (
            select(MissionAssignmentModel)
            .where(MissionAssignmentModel.mission_date >= first)
            .where(MissionAssignmentModel.mission_date <= last)
            .where(MissionAssignmentModel.deleted_at.is_(None))
        )
        return list(self.session.scalars(stmt))

    # --- Participants ---

    def add_participant(self, participant: MissionParticipantModel) -> MissionParticipantModel:
        self.session.add(participant)
        self.session.flush()
        return participant

    def list_participants(self, mission_id: str) -> list[MissionParticipantModel]:
        stmt = select(MissionParticipantModel).where(
            MissionParticipantModel.mission_assignment_id == mission_id
        )
        return list(self.session.scalars(stmt))

    def list_participants_bulk(self, mission_ids: list[str]) -> dict[str, list[MissionParticipantModel]]:
        """Load participants for multiple missions in a single query."""
        if not mission_ids:
            return {}
        stmt = select(MissionParticipantModel).where(
            MissionParticipantModel.mission_assignment_id.in_(mission_ids)
        )
        result: dict[str, list[MissionParticipantModel]] = {}
        for p in self.session.scalars(stmt):
            result.setdefault(p.mission_assignment_id, []).append(p)
        return result

    def list_participations_for_doctor_in_range(
        self, doctor_id: str, start: date, end: date
    ) -> list[MissionParticipantModel]:
        """All mission participations for a doctor in a date range."""
        stmt = (
            select(MissionParticipantModel)
            .join(MissionAssignmentModel, MissionParticipantModel.mission_assignment_id == MissionAssignmentModel.id)
            .where(MissionParticipantModel.doctor_id == doctor_id)
            .where(MissionAssignmentModel.mission_date >= start)
            .where(MissionAssignmentModel.mission_date <= end)
            .where(MissionAssignmentModel.deleted_at.is_(None))
        )
        return list(self.session.scalars(stmt))

    def list_future_confirmed_participations_for_doctor(
        self,
        doctor_id: str,
        *,
        from_date: date,
    ) -> list[tuple[MissionAssignmentModel, MissionParticipantModel]]:
        stmt = (
            select(MissionAssignmentModel, MissionParticipantModel)
            .join(
                MissionParticipantModel,
                MissionParticipantModel.mission_assignment_id == MissionAssignmentModel.id,
            )
            .where(MissionParticipantModel.doctor_id == doctor_id)
            .where(MissionAssignmentModel.status == "confirmed")
            .where(MissionAssignmentModel.mission_date >= from_date)
            .where(MissionAssignmentModel.deleted_at.is_(None))
            .order_by(MissionAssignmentModel.mission_date)
        )
        return list(self.session.execute(stmt).all())

    def list_confirmed_in_range(self, start: date, end: date) -> list[tuple[MissionAssignmentModel, list[MissionParticipantModel]]]:
        """All confirmed missions with participants in a date range."""
        stmt = (
            select(MissionAssignmentModel)
            .where(MissionAssignmentModel.status == "confirmed")
            .where(MissionAssignmentModel.mission_date >= start)
            .where(MissionAssignmentModel.mission_date <= end)
            .where(MissionAssignmentModel.deleted_at.is_(None))
            .order_by(MissionAssignmentModel.mission_date)
        )
        missions = list(self.session.scalars(stmt))
        participants_by_id = self.list_participants_bulk([m.id for m in missions])
        return [(m, participants_by_id.get(m.id, [])) for m in missions]

    # --- Rankings ---

    def add_ranking(self, ranking: MissionCandidateRankingModel) -> MissionCandidateRankingModel:
        self.session.add(ranking)
        self.session.flush()
        return ranking

    def get_ranking_by_period(self, year: int, month: int, calendar_version_id: str | None = None) -> MissionCandidateRankingModel | None:
        stmt = select(MissionCandidateRankingModel).where(
            MissionCandidateRankingModel.year == year,
            MissionCandidateRankingModel.month == month,
        )
        if calendar_version_id is not None:
            stmt = stmt.where(MissionCandidateRankingModel.calendar_version_id == calendar_version_id)
        stmt = stmt.order_by(MissionCandidateRankingModel.generated_at.desc())
        return self.session.scalars(stmt).first()

    def add_ranking_entry(
        self, entry: MissionCandidateRankingEntryModel
    ) -> MissionCandidateRankingEntryModel:
        self.session.add(entry)
        self.session.flush()
        return entry

    def list_ranking_entries(self, ranking_id: str) -> list[MissionCandidateRankingEntryModel]:
        stmt = (
            select(MissionCandidateRankingEntryModel)
            .where(MissionCandidateRankingEntryModel.mission_candidate_ranking_id == ranking_id)
            .order_by(MissionCandidateRankingEntryModel.ranking_position)
        )
        return list(self.session.scalars(stmt))
