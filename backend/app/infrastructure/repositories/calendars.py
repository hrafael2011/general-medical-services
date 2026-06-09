from datetime import UTC, datetime, date

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from backend.app.infrastructure.db.models.calendars import (
    CalendarAssignmentModel,
    CalendarModel,
    CalendarVersionModel,
    CalendarWeekModel,
    UnresolvedGapModel,
)
from backend.app.infrastructure.db.models.catalogs import ServiceAreaModel
from backend.app.infrastructure.db.models.confirmations import ConfirmationRequestModel
from backend.app.infrastructure.db.models.notifications import NotificationEventModel


def _not_deleted() -> tuple:
    """Return filter expressions to exclude soft-deleted records."""
    return (CalendarModel.deleted_at.is_(None),)


def _version_not_deleted() -> tuple:
    """Return filter expressions to exclude soft-deleted versions."""
    return (CalendarVersionModel.deleted_at.is_(None),)


class CalendarRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    # --- Calendar ---

    def add_calendar(self, calendar: CalendarModel) -> CalendarModel:
        self.session.add(calendar)
        self.session.flush()
        return calendar

    def get_calendar_by_id(self, calendar_id: str) -> CalendarModel | None:
        stmt = select(CalendarModel).where(
            CalendarModel.id == calendar_id,
            *_not_deleted(),
        )
        return self.session.scalar(stmt)

    def get_calendar_by_period(self, year: int, month: int) -> CalendarModel | None:
        stmt = select(CalendarModel).where(
            CalendarModel.year == year,
            CalendarModel.month == month,
            *_not_deleted(),
        )
        return self.session.scalar(stmt)

    def list_calendars(self) -> list[CalendarModel]:
        stmt = (
            select(CalendarModel)
            .where(*_not_deleted())
            .order_by(CalendarModel.year.desc(), CalendarModel.month.desc())
        )
        return list(self.session.scalars(stmt))

    def soft_delete_calendar(self, calendar_id: str) -> None:
        now = datetime.now(UTC)
        self.session.execute(
            update(CalendarModel)
            .where(CalendarModel.id == calendar_id)
            .values(deleted_at=now, updated_at=now)
        )
        # Cascade to all non-deleted versions of this calendar
        self.session.execute(
            update(CalendarVersionModel)
            .where(CalendarVersionModel.calendar_id == calendar_id)
            .where(CalendarVersionModel.deleted_at.is_(None))
            .values(deleted_at=now)
        )
        self.session.flush()

    def restore_calendar(self, calendar_id: str) -> None:
        now = datetime.now(UTC)
        self.session.execute(
            update(CalendarModel)
            .where(CalendarModel.id == calendar_id)
            .values(deleted_at=None, updated_at=now)
        )
        self.session.execute(
            update(CalendarVersionModel)
            .where(CalendarVersionModel.calendar_id == calendar_id)
            .where(CalendarVersionModel.deleted_at.isnot(None))
            .values(deleted_at=None)
        )
        self.session.flush()

    def list_deleted_calendars(self) -> list[CalendarModel]:
        stmt = (
            select(CalendarModel)
            .where(CalendarModel.deleted_at.isnot(None))
            .order_by(CalendarModel.deleted_at.desc())
        )
        return list(self.session.scalars(stmt))

    def get_calendar_by_id_including_deleted(self, calendar_id: str) -> CalendarModel | None:
        stmt = select(CalendarModel).where(CalendarModel.id == calendar_id)
        return self.session.scalar(stmt)

    def hard_delete_calendar(self, calendar_id: str) -> None:
        """Permanently remove a calendar and all its related data."""
        version_subquery = (
            select(CalendarVersionModel.id)
            .where(CalendarVersionModel.calendar_id == calendar_id)
        )
        self.session.execute(
            delete(CalendarAssignmentModel)
            .where(CalendarAssignmentModel.calendar_version_id.in_(version_subquery))
        )
        self.session.execute(
            delete(UnresolvedGapModel)
            .where(UnresolvedGapModel.calendar_version_id.in_(version_subquery))
        )
        self.session.execute(
            delete(CalendarWeekModel)
            .where(CalendarWeekModel.calendar_version_id.in_(version_subquery))
        )
        self.session.execute(
            delete(CalendarVersionModel)
            .where(CalendarVersionModel.calendar_id == calendar_id)
        )
        self.session.execute(
            delete(CalendarModel)
            .where(CalendarModel.id == calendar_id)
        )
        self.session.flush()

    # --- Calendar Version ---

    def add_version(self, version: CalendarVersionModel) -> CalendarVersionModel:
        self.session.add(version)
        self.session.flush()
        return version

    def get_version_by_id(self, version_id: str) -> CalendarVersionModel | None:
        stmt = select(CalendarVersionModel).where(
            CalendarVersionModel.id == version_id,
            *_version_not_deleted(),
        )
        return self.session.scalar(stmt)

    def list_versions(self, calendar_id: str) -> list[CalendarVersionModel]:
        stmt = (
            select(CalendarVersionModel)
            .where(
                CalendarVersionModel.calendar_id == calendar_id,
                *_version_not_deleted(),
            )
            .order_by(CalendarVersionModel.version_number.desc())
        )
        return list(self.session.scalars(stmt))

    def get_latest_version(self, calendar_id: str) -> CalendarVersionModel | None:
        stmt = (
            select(CalendarVersionModel)
            .where(
                CalendarVersionModel.calendar_id == calendar_id,
                *_version_not_deleted(),
            )
            .order_by(CalendarVersionModel.version_number.desc())
            .limit(1)
        )
        return self.session.scalar(stmt)

    def get_approved_version_by_period(
        self,
        year: int,
        month: int,
    ) -> CalendarVersionModel | None:
        stmt = (
            select(CalendarVersionModel)
            .join(CalendarModel, CalendarVersionModel.calendar_id == CalendarModel.id)
            .where(
                CalendarModel.year == year,
                CalendarModel.month == month,
                CalendarModel.status.in_(["approved", "partial"]),
                CalendarVersionModel.status.in_(["approved", "draft"]),
                *_not_deleted(),
                *_version_not_deleted(),
            )
            .order_by(CalendarVersionModel.version_number.desc())
            .limit(1)
        )
        return self.session.scalar(stmt)

    def get_latest_version_by_period(
        self,
        year: int,
        month: int,
    ) -> CalendarVersionModel | None:
        """Return the latest version for the given period regardless of status."""
        stmt = (
            select(CalendarVersionModel)
            .join(CalendarModel, CalendarVersionModel.calendar_id == CalendarModel.id)
            .where(
                CalendarModel.year == year,
                CalendarModel.month == month,
                *_not_deleted(),
                *_version_not_deleted(),
            )
            .order_by(CalendarVersionModel.version_number.desc())
            .limit(1)
        )
        return self.session.scalar(stmt)

    def delete_assignments_for_doctor_in_active_calendars(
        self,
        doctor_id: str,
    ) -> tuple[int, list[str]]:
        """Delete all assignments for a doctor in draft/partial calendars.

        Returns (deleted_count, affected_calendar_ids).
        """
        from sqlalchemy import delete as sql_delete

        active_calendar_ids = (
            select(CalendarModel.id)
            .where(
                CalendarModel.status.in_(["draft", "partial"]),
                CalendarModel.deleted_at.is_(None),
            )
        )

        active_version_ids = (
            select(CalendarVersionModel.id)
            .where(
                CalendarVersionModel.calendar_id.in_(active_calendar_ids),
                CalendarVersionModel.deleted_at.is_(None),
            )
        )

        # Query assignments that will be deleted (needed for affected calendars + notification cleanup)
        assignment_ids_to_delete = self.session.execute(
            select(CalendarAssignmentModel.id)
            .where(
                CalendarAssignmentModel.doctor_id == doctor_id,
                CalendarAssignmentModel.calendar_version_id.in_(active_version_ids),
            )
        ).scalars().all()

        if not assignment_ids_to_delete:
            return 0, []

        # Query affected calendar IDs before deletion
        affected = self.session.execute(
            select(CalendarVersionModel.calendar_id)
            .where(
                CalendarVersionModel.id.in_(
                    select(CalendarAssignmentModel.calendar_version_id)
                    .where(CalendarAssignmentModel.id.in_(assignment_ids_to_delete))
                )
            )
            .distinct()
        ).scalars().all()

        # Collect notification event IDs that reference these assignments
        notification_ids = self.session.execute(
            select(NotificationEventModel.id)
            .where(NotificationEventModel.assignment_id.in_(assignment_ids_to_delete))
        ).scalars().all()

        if notification_ids:
            # Delete confirmation requests referencing these notification events
            self.session.execute(
                sql_delete(ConfirmationRequestModel)
                .where(ConfirmationRequestModel.notification_id.in_(notification_ids))
            )
            # Delete the notification events
            self.session.execute(
                sql_delete(NotificationEventModel)
                .where(NotificationEventModel.id.in_(notification_ids))
            )

        # Delete the assignments
        stmt = (
            sql_delete(CalendarAssignmentModel)
            .where(CalendarAssignmentModel.id.in_(assignment_ids_to_delete))
        )
        result = self.session.execute(stmt)
        return result.rowcount, list(affected)

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

    # --- Calendar Week ---

    def add_week(self, week: CalendarWeekModel) -> CalendarWeekModel:
        self.session.add(week)
        self.session.flush()
        return week

    def list_weeks(self, calendar_id: str) -> list[CalendarWeekModel]:
        stmt = (
            select(CalendarWeekModel)
            .where(CalendarWeekModel.calendar_id == calendar_id)
            .order_by(CalendarWeekModel.week_number)
        )
        return list(self.session.scalars(stmt))

    def get_week_by_id(self, week_id: str) -> CalendarWeekModel | None:
        stmt = select(CalendarWeekModel).where(CalendarWeekModel.id == week_id)
        return self.session.scalar(stmt)

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
            .join(
                CalendarVersionModel,
                CalendarAssignmentModel.calendar_version_id == CalendarVersionModel.id,
            )
            .where(CalendarAssignmentModel.service_date >= start_date)
            .where(CalendarAssignmentModel.service_date <= end_date)
            .where(CalendarVersionModel.deleted_at.is_(None))
        )
        return list(self.session.scalars(stmt))

    def list_service_areas(self) -> list[ServiceAreaModel]:
        stmt = select(ServiceAreaModel).order_by(ServiceAreaModel.code)
        return list(self.session.scalars(stmt))

    # --- Calendar Week ---

    def add_week(self, week: CalendarWeekModel) -> CalendarWeekModel:
        self.session.add(week)
        self.session.flush()
        return week

    def get_week_by_id(self, week_id: str) -> CalendarWeekModel | None:
        return self.session.get(CalendarWeekModel, week_id)

    def list_weeks(self, calendar_id: str) -> list[CalendarWeekModel]:
        stmt = (
            select(CalendarWeekModel)
            .where(CalendarWeekModel.calendar_id == calendar_id)
            .order_by(CalendarWeekModel.week_number)
        )
        return list(self.session.scalars(stmt))

    def list_weeks_by_version(self, version_id: str) -> list[CalendarWeekModel]:
        stmt = (
            select(CalendarWeekModel)
            .where(CalendarWeekModel.calendar_version_id == version_id)
            .order_by(CalendarWeekModel.week_number)
        )
        return list(self.session.scalars(stmt))

    def get_week_for_date(
        self, version_id: str, service_date: date
    ) -> CalendarWeekModel | None:
        stmt = select(CalendarWeekModel).where(
            CalendarWeekModel.calendar_version_id == version_id,
            CalendarWeekModel.start_date <= service_date,
            CalendarWeekModel.end_date >= service_date,
        )
        return self.session.scalar(stmt)

    def update_week_status(
        self, week_id: str, status: str,
        approved_by: str | None = None,
        previous_assignments_hash: str | None = None,
    ) -> None:
        values: dict = {"status": status, "updated_at": datetime.now(UTC)}
        if status == "approved" and approved_by:
            values["approved_by"] = approved_by
            values["approved_at"] = datetime.now(UTC)
        if previous_assignments_hash is not None:
            values["previous_assignments_hash"] = previous_assignments_hash
        self.session.execute(
            update(CalendarWeekModel)
            .where(CalendarWeekModel.id == week_id)
            .values(**values)
        )
        self.session.flush()
        # Expire cached instance so next read fetches fresh data
        week = self.session.get(CalendarWeekModel, week_id)
        if week:
            self.session.expire(week)
