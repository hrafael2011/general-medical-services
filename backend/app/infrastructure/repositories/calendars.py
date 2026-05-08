from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.infrastructure.db.models.calendars import (
    CalendarAssignmentModel,
    CalendarModel,
    CalendarVersionModel,
    UnresolvedGapModel,
)


class CalendarRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    # --- Calendar ---

    def add_calendar(self, calendar: CalendarModel) -> CalendarModel:
        self.session.add(calendar)
        self.session.flush()
        return calendar

    def get_calendar_by_id(self, calendar_id: str) -> CalendarModel | None:
        return self.session.get(CalendarModel, calendar_id)

    def get_calendar_by_period(self, year: int, month: int) -> CalendarModel | None:
        stmt = select(CalendarModel).where(
            CalendarModel.year == year,
            CalendarModel.month == month,
        )
        return self.session.scalar(stmt)

    def list_calendars(self) -> list[CalendarModel]:
        stmt = select(CalendarModel).order_by(CalendarModel.year.desc(), CalendarModel.month.desc())
        return list(self.session.scalars(stmt))

    # --- Calendar Version ---

    def add_version(self, version: CalendarVersionModel) -> CalendarVersionModel:
        self.session.add(version)
        self.session.flush()
        return version

    def get_version_by_id(self, version_id: str) -> CalendarVersionModel | None:
        return self.session.get(CalendarVersionModel, version_id)

    def list_versions(self, calendar_id: str) -> list[CalendarVersionModel]:
        stmt = (
            select(CalendarVersionModel)
            .where(CalendarVersionModel.calendar_id == calendar_id)
            .order_by(CalendarVersionModel.version_number.desc())
        )
        return list(self.session.scalars(stmt))

    def get_latest_version(self, calendar_id: str) -> CalendarVersionModel | None:
        stmt = (
            select(CalendarVersionModel)
            .where(CalendarVersionModel.calendar_id == calendar_id)
            .order_by(CalendarVersionModel.version_number.desc())
            .limit(1)
        )
        return self.session.scalar(stmt)

    # --- Calendar Assignment ---

    def add_assignment(self, assignment: CalendarAssignmentModel) -> CalendarAssignmentModel:
        self.session.add(assignment)
        self.session.flush()
        return assignment

    def get_assignment_by_id(self, assignment_id: str) -> CalendarAssignmentModel | None:
        return self.session.get(CalendarAssignmentModel, assignment_id)

    def list_assignments(self, version_id: str) -> list[CalendarAssignmentModel]:
        stmt = (
            select(CalendarAssignmentModel)
            .where(CalendarAssignmentModel.calendar_version_id == version_id)
            .order_by(CalendarAssignmentModel.service_date, CalendarAssignmentModel.service_area_id)
        )
        return list(self.session.scalars(stmt))

    def list_assignments_for_date(
        self, version_id: str, service_date: date
    ) -> list[CalendarAssignmentModel]:
        stmt = select(CalendarAssignmentModel).where(
            CalendarAssignmentModel.calendar_version_id == version_id,
            CalendarAssignmentModel.service_date == service_date,
        )
        return list(self.session.scalars(stmt))

    def get_assignment_for_slot(
        self, version_id: str, service_date: date, service_area_id: str
    ) -> CalendarAssignmentModel | None:
        stmt = select(CalendarAssignmentModel).where(
            CalendarAssignmentModel.calendar_version_id == version_id,
            CalendarAssignmentModel.service_date == service_date,
            CalendarAssignmentModel.service_area_id == service_area_id,
        )
        return self.session.scalar(stmt)

    def delete_assignment(self, assignment_id: str) -> None:
        assignment = self.session.get(CalendarAssignmentModel, assignment_id)
        if assignment:
            self.session.delete(assignment)
            self.session.flush()

    # --- Unresolved Gaps ---

    def add_gap(self, gap: UnresolvedGapModel) -> UnresolvedGapModel:
        self.session.add(gap)
        self.session.flush()
        return gap

    def list_gaps(self, version_id: str) -> list[UnresolvedGapModel]:
        stmt = (
            select(UnresolvedGapModel)
            .where(UnresolvedGapModel.calendar_version_id == version_id)
            .order_by(UnresolvedGapModel.service_date)
        )
        return list(self.session.scalars(stmt))

    def list_assignments_in_date_range(
        self, start_date: "date", end_date: "date"
    ) -> list[CalendarAssignmentModel]:
        """Return all assignments across all versions within a date range (for load history)."""
        stmt = (
            select(CalendarAssignmentModel)
            .where(CalendarAssignmentModel.service_date >= start_date)
            .where(CalendarAssignmentModel.service_date <= end_date)
        )
        return list(self.session.scalars(stmt))
