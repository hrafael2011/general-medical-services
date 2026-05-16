import hashlib
from datetime import UTC, datetime
from uuid import uuid4

from backend.app.application.audit.service import AuditService
from backend.app.application.calendars.errors import CalendarServiceError
from backend.app.application.notifications.triggers import NotificationTriggers
from backend.app.infrastructure.db.models.calendars import (
    CalendarAssignmentModel,
    CalendarModel,
    CalendarVersionModel,
    CalendarWeekModel,
)
from backend.app.infrastructure.repositories.calendars import CalendarRepository

CALENDAR_GENERATION_MODES = {"manual", "assisted_auto", "scheduled_auto"}


class CalendarService:
    def __init__(
        self,
        repo: CalendarRepository,
        audit: AuditService | None = None,
        triggers: NotificationTriggers | None = None,
        mission_ranking_service=None,
    ) -> None:
        self.repo = repo
        self.audit = audit
        self.triggers = triggers
        self.mission_ranking_service = mission_ranking_service

    def create_calendar(
        self,
        *,
        actor_id: str,
        month: int,
        year: int,
        notes: str | None,
        generation_mode: str = "manual",
    ) -> CalendarModel:
        """Creates calendar + initial version v1 in 'draft' status."""
        if generation_mode not in CALENDAR_GENERATION_MODES:
            raise CalendarServiceError(
                "invalid_generation_mode",
                f"Unsupported calendar generation mode: {generation_mode}.",
            )

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
            generation_mode=generation_mode,
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

    def soft_delete_calendar(self, *, actor_id: str, calendar_id: str) -> None:
        """Soft-delete a calendar so it no longer appears in list/get queries."""
        calendar = self.repo.get_calendar_by_id(calendar_id)
        if calendar is None:
            raise CalendarServiceError(
                "calendar_not_found",
                f"Calendar with id {calendar_id} not found.",
            )
        self.repo.soft_delete_calendar(calendar_id)

        if self.audit is not None:
            self.audit.log_calendar_deleted(actor_id=actor_id, calendar=calendar)

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
        version.approved_at = now
        version.approved_by = actor_id
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

        should_notify = True
        if version.reason and version.reason.startswith("__unlock__"):
            should_notify = False
            # Restore original reason
            if "__orig__" in version.reason:
                version.reason = version.reason.split("__orig__", 1)[1]
            else:
                version.reason = None

        if self.triggers is not None and should_notify:
            assignments = self.repo.list_assignments(version.id)
            self.triggers.on_calendar_approved(
                actor_id=actor_id,
                assignments=assignments,
            )

        if self.mission_ranking_service is not None:
            self.mission_ranking_service.generate_ranking(
                actor_id=actor_id,
                year=calendar.year,
                month=calendar.month,
                calendar_version_id=version.id,
            )

        return version

    def unlock_calendar(
        self,
        *,
        actor_id: str,
        calendar_id: str,
    ) -> CalendarVersionModel:
        """Revert an approved calendar back to draft. Keeps all assignments intact."""
        calendar = self.repo.get_calendar_by_id(calendar_id)
        if calendar is None:
            raise CalendarServiceError(
                "calendar_not_found",
                f"Calendar with id {calendar_id} not found.",
            )

        if calendar.status != "approved":
            raise CalendarServiceError(
                "invalid_status_transition",
                "unlock_calendar can only be called on an approved calendar.",
            )

        versions = self.repo.list_versions(calendar_id)
        if not versions:
            raise CalendarServiceError(
                "version_not_found",
                f"No versions found for calendar {calendar_id}.",
            )

        now = datetime.now(UTC)
        version = versions[0]  # latest version (list ordered desc)

        # Snapshot hash of current assignments to detect changes on re-approval
        current_assignments = self.repo.list_assignments(version.id)
        snap_data = "|".join(
            sorted(
                f"{a.service_date}|{a.service_area_id}|{a.doctor_id}"
                for a in current_assignments
            )
        )
        snap_hash = hashlib.md5(snap_data.encode()).hexdigest()
        original_reason = version.reason
        version.reason = f"__unlock__{snap_hash}"
        if original_reason:
            version.reason += f"__orig__{original_reason}"

        version.status = "draft"
        version.approved_at = None
        version.approved_by = None
        self.repo.session.flush()

        calendar.status = "draft"
        calendar.updated_at = now
        self.repo.session.flush()

        if self.audit is not None:
            self.audit.log_calendar_unlocked(
                actor_id=actor_id,
                calendar=calendar,
                version=version,
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

    def approve_week(
        self,
        *,
        actor_id: str,
        week_id: str,
        notes: str | None,
    ) -> CalendarWeekModel:
        """Approve a single calendar week. Notifications fire for its doctors."""
        week = self.repo.get_week_by_id(week_id)
        if week is None:
            raise CalendarServiceError(
                "week_not_found", f"Week {week_id} not found",
            )
        if week.status == "approved":
            raise CalendarServiceError(
                "week_already_approved",
                f"Week {week.week_number} is already approved",
            )

        now = datetime.now(UTC)
        self.repo.update_week_status(week_id, "approved", approved_by=actor_id)
        week.status = "approved"
        week.approved_by = actor_id
        week.approved_at = now

        # Derive calendar status from weeks
        calendar = self.repo.get_calendar_by_id(week.calendar_id)
        all_weeks = self.repo.list_weeks(week.calendar_id)
        all_approved = all(w.status == "approved" for w in all_weeks)
        calendar.status = "approved" if all_approved else "partial"
        calendar.updated_at = now
        self.repo.session.flush()

        # Notify only doctors assigned to this week
        week_assignments: list[CalendarAssignmentModel] = []
        if self.triggers is not None:
            assignments = self.repo.list_assignments(week.calendar_version_id)
            week_assignments = [
                a for a in assignments
                if getattr(a, "calendar_week_id", None) == week_id
            ]
            self.triggers.on_week_approved(
                actor_id=actor_id,
                assignments=week_assignments,
                week=week,
            )

        if self.audit is not None:
            self.audit.log_calendar_approved(
                actor_id=actor_id, calendar=calendar,
                version=self.repo.get_version_by_id(week.calendar_version_id),
            )

        return week

    def unlock_week(
        self,
        *,
        actor_id: str,
        week_id: str,
        notes: str | None,
    ) -> CalendarWeekModel:
        """Revert a week to draft for editing. Stores hash of current assignments."""
        week = self.repo.get_week_by_id(week_id)
        if week is None:
            raise CalendarServiceError(
                "week_not_found", f"Week {week_id} not found",
            )
        if week.status != "approved":
            raise CalendarServiceError(
                "week_not_approved",
                "Only approved weeks can be unlocked",
            )

        # Hash current assignments for change detection on re-approval
        assignments = self.repo.list_assignments(week.calendar_version_id)
        week_assignments = [
            a for a in assignments
            if getattr(a, "calendar_week_id", None) == week_id
        ]
        hash_parts = sorted(
            f"{a.doctor_id}|{a.service_date.isoformat()}|{a.service_area_id}"
            for a in week_assignments
        )
        hash_str = (
            hashlib.md5("|".join(hash_parts).encode()).hexdigest()
            if hash_parts else ""
        )

        self.repo.update_week_status(
            week_id, "draft", previous_assignments_hash=hash_str,
        )
        week.status = "draft"
        week.previous_assignments_hash = hash_str

        calendar = self.repo.get_calendar_by_id(week.calendar_id)
        calendar.status = "partial"
        calendar.updated_at = datetime.now(UTC)
        self.repo.session.flush()

        if self.audit is not None:
            self.audit.log_calendar_unlocked(
                actor_id=actor_id, calendar=calendar,
                version=self.repo.get_version_by_id(week.calendar_version_id),
            )

        return week
