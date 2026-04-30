from datetime import UTC, datetime
from uuid import uuid4

from backend.app.application.audit.service import AuditService
from backend.app.application.calendars.errors import CalendarServiceError
from backend.app.infrastructure.db.models.calendars import CalendarModel, CalendarVersionModel
from backend.app.infrastructure.repositories.calendars import CalendarRepository


class CalendarService:
    def __init__(
        self,
        repo: CalendarRepository,
        audit: AuditService | None = None,
    ) -> None:
        self.repo = repo
        self.audit = audit

    def create_calendar(
        self,
        *,
        actor_id: str,
        month: int,
        year: int,
        notes: str | None,
    ) -> CalendarModel:
        """Creates calendar + initial version v1 in 'draft' status."""
        existing = self.repo.get_calendar_by_period(year, month)
        if existing is not None:
            raise CalendarServiceError(
                "calendar_already_exists",
                f"A calendar for {year}-{month:02d} already exists.",
            )

        now = datetime.now(UTC)
        calendar = CalendarModel(
            id=str(uuid4()),
            year=year,
            month=month,
            status="draft",
            created_by=actor_id,
            approved_by=None,
            created_at=now,
            updated_at=now,
            approved_at=None,
        )
        calendar = self.repo.add_calendar(calendar)

        version = CalendarVersionModel(
            id=str(uuid4()),
            calendar_id=calendar.id,
            version_number=1,
            status="draft",
            created_by=actor_id,
            reason=notes,
            created_at=now,
        )
        self.repo.add_version(version)

        if self.audit is not None:
            self.audit.log_calendar_created(actor_id=actor_id, calendar=calendar)

        return calendar

    def get_calendar(self, calendar_id: str) -> CalendarModel:
        calendar = self.repo.get_calendar_by_id(calendar_id)
        if calendar is None:
            raise CalendarServiceError(
                "calendar_not_found",
                f"Calendar with id {calendar_id} not found.",
            )
        return calendar

    def list_calendars(self) -> list[CalendarModel]:
        return self.repo.list_calendars()

    def approve_version(
        self,
        *,
        actor_id: str,
        calendar_id: str,
        version_number: int,
        notes: str | None,
    ) -> CalendarVersionModel:
        """
        Sets version status to 'approved', sets calendar status to 'approved'.
        Raises CalendarServiceError if version not found or already approved.
        """
        calendar = self.repo.get_calendar_by_id(calendar_id)
        if calendar is None:
            raise CalendarServiceError(
                "calendar_not_found",
                f"Calendar with id {calendar_id} not found.",
            )

        versions = self.repo.list_versions(calendar_id)
        version = next(
            (v for v in versions if v.version_number == version_number), None
        )
        if version is None:
            raise CalendarServiceError(
                "version_not_found",
                f"Version {version_number} not found for calendar {calendar_id}.",
            )

        if version.status == "approved":
            raise CalendarServiceError(
                "calendar_already_approved",
                f"Version {version_number} is already approved.",
            )

        now = datetime.now(UTC)

        version.status = "approved"
        # CalendarVersionModel does not have approved_at / approved_by columns,
        # so those fields live on the CalendarModel.
        self.repo.session.flush()

        calendar.status = "approved"
        calendar.approved_by = actor_id
        calendar.approved_at = now
        calendar.updated_at = now
        self.repo.session.flush()

        if self.audit is not None:
            self.audit.log_calendar_approved(
                actor_id=actor_id, calendar=calendar, version=version
            )

        return version

    def new_version_after_approval(
        self,
        *,
        actor_id: str,
        calendar_id: str,
        reason: str | None,
    ) -> CalendarVersionModel:
        """
        Called when an approved calendar needs modification.
        Creates version N+1 in 'draft' status.
        Sets calendar status back to 'draft'.
        The assignments from the previous approved version are NOT copied here
        (that's AssignmentService's job).
        """
        calendar = self.repo.get_calendar_by_id(calendar_id)
        if calendar is None:
            raise CalendarServiceError(
                "calendar_not_found",
                f"Calendar with id {calendar_id} not found.",
            )

        if calendar.status != "approved":
            raise CalendarServiceError(
                "invalid_status_transition",
                "new_version_after_approval can only be called on an approved calendar.",
            )

        versions = self.repo.list_versions(calendar_id)
        if not versions:
            raise CalendarServiceError(
                "version_not_found",
                f"No versions found for calendar {calendar_id}.",
            )

        next_version_number = max(v.version_number for v in versions) + 1
        now = datetime.now(UTC)

        new_version = CalendarVersionModel(
            id=str(uuid4()),
            calendar_id=calendar_id,
            version_number=next_version_number,
            status="draft",
            created_by=actor_id,
            reason=reason,
            created_at=now,
        )
        self.repo.add_version(new_version)

        calendar.status = "draft"
        calendar.updated_at = now
        self.repo.session.flush()

        if self.audit is not None:
            self.audit.log_calendar_new_version(
                actor_id=actor_id, calendar=calendar, version=new_version
            )

        return new_version
