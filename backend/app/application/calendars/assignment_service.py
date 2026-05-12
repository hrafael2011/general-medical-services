from datetime import UTC, date, datetime
from uuid import uuid4

from backend.app.application.audit.service import AuditService
from backend.app.application.calendars.errors import CalendarServiceError
from backend.app.domain.doctors.eligibility import EligibilityChecker, EligibilityResult
from backend.app.infrastructure.db.models.calendars import CalendarAssignmentModel
from backend.app.infrastructure.repositories.availability import AvailabilityRepository
from backend.app.infrastructure.repositories.calendars import CalendarRepository
from backend.app.infrastructure.repositories.doctors import DoctorRepository

# Codes that indicate a hard block — cannot be overridden.
_HARD_BLOCK_CODES = {"doctor_inactive", "area_not_allowed", "has_hard_block"}


class AssignmentService:
    def __init__(
        self,
        calendar_repo: CalendarRepository,
        doctor_repo: DoctorRepository,
        availability_repo: AvailabilityRepository,
        audit: AuditService | None = None,
    ) -> None:
        self.calendar_repo = calendar_repo
        self.doctor_repo = doctor_repo
        self.availability_repo = availability_repo
        self.audit = audit

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_eligibility(
        self,
        *,
        doctor,
        service_area_id: str,
        target_date: date,
        override_justification: str | None,
    ) -> list[EligibilityResult]:
        """
        Runs EligibilityChecker and raises CalendarServiceError on violations.

        Hard-block results always raise.
        Soft-warning results raise only when no override_justification is provided.
        """
        allowed_area_ids = self.doctor_repo.get_allowed_areas(doctor.id)
        active_restrictions = self.availability_repo.list_active_restrictions_for_doctor(
            doctor.id, target_date
        )
        weekly_availability = self.availability_repo.list_weekly_fixed_for_doctor(doctor.id)
        monthly_availability = self.availability_repo.list_monthly_variable_for_period(
            doctor.id, target_date.year, target_date.month
        )

        checker = EligibilityChecker()
        report = checker.check(
            doctor,
            service_area_id=service_area_id,
            target_date=target_date,
            allowed_area_ids=allowed_area_ids,
            active_restrictions=active_restrictions,
            weekly_availability=weekly_availability,
            monthly_availability=monthly_availability,
        )

        if report.eligible:
            return []

        # Separate failures into hard blocks and soft warnings.
        hard_blocks = [r for r in report.blockers if r.code in _HARD_BLOCK_CODES]
        soft_warnings = [r for r in report.blockers if r.code not in _HARD_BLOCK_CODES]

        if hard_blocks:
            raise CalendarServiceError("hard_block", hard_blocks[0].reason)

        if soft_warnings and not override_justification:
            raise CalendarServiceError("soft_warning", soft_warnings[0].reason)

        return soft_warnings

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def assign_doctor(
        self,
        *,
        actor_id: str,
        version_id: str,
        doctor_id: str,
        date: date,
        service_area_id: str,
        override_justification: str | None = None,
    ) -> CalendarAssignmentModel:
        """
        Assigns a doctor to a slot (date + service_area) within a calendar version.

        Steps:
        1. Load the version; raise CalendarServiceError("version_not_found") if missing.
        2. Raise CalendarServiceError("version_is_approved") if version.status == "approved".
        3. Load the doctor; raise CalendarServiceError("doctor_not_found") if missing.
        4. Run eligibility checks; raise on hard blocks or unacknowledged soft warnings.
        5. Persist the new CalendarAssignmentModel.
        6. Log the audit event.
        """
        # 1. Load version.
        version = self.calendar_repo.get_version_by_id(version_id)
        if version is None:
            raise CalendarServiceError(
                "version_not_found",
                f"Calendar version '{version_id}' not found.",
            )

        # 2. Guard against approved versions.
        if version.status == "approved":
            raise CalendarServiceError(
                "version_is_approved",
                "Cannot modify an approved calendar version.",
            )

        # 3. Load doctor.
        doctor = self.doctor_repo.get_by_id(doctor_id)
        if doctor is None:
            raise CalendarServiceError(
                "doctor_not_found",
                f"Doctor '{doctor_id}' not found.",
            )

        # 4. Eligibility checks.
        soft_warnings = self._run_eligibility(
            doctor=doctor,
            service_area_id=service_area_id,
            target_date=date,
            override_justification=override_justification,
        )

        # 5. Persist assignment.
        # Only store override_justification when the caller explicitly provided one.
        stored_justification = override_justification if override_justification else None
        assignment = CalendarAssignmentModel(
            id=str(uuid4()),
            calendar_version_id=version_id,
            doctor_id=doctor_id,
            service_date=date,
            service_area_id=service_area_id,
            assignment_source="manual",
            rationale=_manual_rationale(soft_warnings),
            override_justification=stored_justification,
            created_by=actor_id,
            created_at=datetime.now(UTC),
        )
        assignment = self.calendar_repo.add_assignment(assignment)

        # 6. Audit.
        if self.audit is not None:
            self.audit.log_assignment_added(actor_id=actor_id, assignment=assignment)

        return assignment

    def remove_assignment(
        self,
        *,
        actor_id: str,
        assignment_id: str,
    ) -> None:
        """
        Removes an existing assignment.

        Raises CalendarServiceError("assignment_not_found") if not found.
        Raises CalendarServiceError("version_is_approved") if the version is approved.
        """
        assignment = self.calendar_repo.get_assignment_by_id(assignment_id)
        if assignment is None:
            raise CalendarServiceError(
                "assignment_not_found",
                f"Assignment '{assignment_id}' not found.",
            )

        version = self.calendar_repo.get_version_by_id(assignment.calendar_version_id)
        if version is not None and version.status == "approved":
            raise CalendarServiceError(
                "version_is_approved",
                "Cannot modify an approved calendar version.",
            )

        self.calendar_repo.delete_assignment(assignment_id)

        if self.audit is not None:
            self.audit.log_assignment_removed(actor_id=actor_id, assignment_id=assignment_id)

    def replace_assignment(
        self,
        *,
        actor_id: str,
        assignment_id: str,
        new_doctor_id: str,
        override_justification: str | None = None,
    ) -> CalendarAssignmentModel:
        """
        Replaces the doctor on an existing assignment slot.

        Runs the same eligibility checks as assign_doctor.
        Updates the existing assignment in-place (does NOT create a new row).

        Raises CalendarServiceError("assignment_not_found") if not found.
        Raises CalendarServiceError("version_is_approved") if the version is approved.
        Raises CalendarServiceError("doctor_not_found") if new_doctor_id is unknown.
        Raises CalendarServiceError("hard_block" | "soft_warning") on eligibility failure.
        """
        # Load existing assignment.
        assignment = self.calendar_repo.get_assignment_by_id(assignment_id)
        if assignment is None:
            raise CalendarServiceError(
                "assignment_not_found",
                f"Assignment '{assignment_id}' not found.",
            )

        # Guard against approved versions.
        version = self.calendar_repo.get_version_by_id(assignment.calendar_version_id)
        if version is not None and version.status == "approved":
            raise CalendarServiceError(
                "version_is_approved",
                "Cannot modify an approved calendar version.",
            )

        # Load new doctor.
        doctor = self.doctor_repo.get_by_id(new_doctor_id)
        if doctor is None:
            raise CalendarServiceError(
                "doctor_not_found",
                f"Doctor '{new_doctor_id}' not found.",
            )

        # Eligibility checks for the new doctor against the existing slot.
        soft_warnings = self._run_eligibility(
            doctor=doctor,
            service_area_id=assignment.service_area_id,
            target_date=assignment.service_date,
            override_justification=override_justification,
        )

        # Update the assignment in-place.
        assignment.doctor_id = new_doctor_id
        assignment.rationale = _manual_rationale(soft_warnings)
        assignment.override_justification = override_justification if override_justification else None
        self.calendar_repo.session.flush()

        if self.audit is not None:
            self.audit.log_assignment_replaced(actor_id=actor_id, assignment=assignment)

        return assignment


def _manual_rationale(soft_warnings: list[EligibilityResult]) -> dict | None:
    if not soft_warnings:
        return None
    return {
        "manual_override_warnings": [
            {"code": warning.code, "reason": warning.reason}
            for warning in soft_warnings
        ]
    }
