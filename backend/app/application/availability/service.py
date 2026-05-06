import uuid
from datetime import UTC, date, datetime

from backend.app.application.audit.service import AuditService
from backend.app.application.availability.errors import AvailabilityError
from backend.app.infrastructure.db.models.availability import (
    DoctorAvailabilityModel,
    DoctorRestrictionModel,
)
from backend.app.infrastructure.repositories.availability import AvailabilityRepository
from backend.app.infrastructure.repositories.doctors import DoctorRepository


class AvailabilityService:
    def __init__(
        self,
        availability_repo: AvailabilityRepository,
        doctor_repo: DoctorRepository,
        audit: AuditService | None = None,
    ) -> None:
        self.availability = availability_repo
        self.doctors = doctor_repo
        self.audit = audit

    def set_weekly_availability(
        self,
        doctor_id: str,
        *,
        days_of_week: list[int],
        effective_from: date | None = None,
        effective_to: date | None = None,
        actor_id: str,
    ) -> DoctorAvailabilityModel:
        """
        Set fixed weekly availability for a doctor.
        Doctor must have availability_mode = "fixed".
        """
        doctor = self.doctors.get_by_id(doctor_id)
        if doctor is None:
            raise AvailabilityError("doctor_not_found", f"Doctor {doctor_id} not found")
        if doctor.availability_mode != "fixed":
            raise AvailabilityError(
                "mode_mismatch",
                "Doctor availability mode is 'monthly'. "
                "Change the doctor's availability_mode to 'fixed' before setting weekly availability.",
            )
        if not days_of_week or not all(0 <= d <= 6 for d in days_of_week):
            raise AvailabilityError(
                "invalid_days_of_week",
                "days_of_week must be a non-empty list of integers between 0 (Monday) and 6 (Sunday).",
            )

        now = datetime.now(UTC)
        record = DoctorAvailabilityModel(
            id=str(uuid.uuid4()),
            doctor_id=doctor_id,
            availability_type="weekly_fixed",
            days_of_week=list(set(days_of_week)),  # deduplicate
            available_dates=None,
            weekday=None,
            week_number=None,
            year=None,
            month=None,
            submitted_at=None,
            effective_from=effective_from,
            effective_to=effective_to,
            source="manual",
            review_status="approved",
            created_by=actor_id,
            created_at=now,
            updated_at=now,
        )
        result = self.availability.add_availability(record)
        if self.audit:
            self.audit.log_availability_set(actor_id=actor_id, availability=result)
        return result

    def set_monthly_availability(
        self,
        doctor_id: str,
        *,
        year: int,
        month: int,
        available_dates: list[int],
        actor_id: str,
    ) -> DoctorAvailabilityModel:
        """
        Set or replace monthly variable availability for a doctor.
        Doctor must have availability_mode = "monthly".
        Replaces any existing monthly_variable record for the same year+month.
        """
        doctor = self.doctors.get_by_id(doctor_id)
        if doctor is None:
            raise AvailabilityError("doctor_not_found", f"Doctor {doctor_id} not found")
        if doctor.availability_mode != "monthly":
            raise AvailabilityError(
                "mode_mismatch",
                "Doctor availability mode is 'fixed'. "
                "Change the doctor's availability_mode to 'monthly' before setting monthly availability.",
            )
        if not 1 <= month <= 12:
            raise AvailabilityError("invalid_month", "month must be between 1 and 12.")
        if not available_dates or not all(1 <= d <= 31 for d in available_dates):
            raise AvailabilityError(
                "invalid_available_dates",
                "available_dates must be a non-empty list of day-of-month integers (1–31).",
            )

        # Replace existing record for the same period
        existing = self.availability.list_monthly_variable_for_period(doctor_id, year, month)
        for old in existing:
            self.availability.delete_availability(old.id)

        now = datetime.now(UTC)
        submitted_at = now
        record = DoctorAvailabilityModel(
            id=str(uuid.uuid4()),
            doctor_id=doctor_id,
            availability_type="monthly_variable",
            days_of_week=None,
            available_dates=sorted(set(available_dates)),  # deduplicate + sort
            weekday=None,
            week_number=None,
            year=year,
            month=month,
            submitted_at=submitted_at,
            effective_from=None,
            effective_to=None,
            source="manual",
            review_status="approved",
            created_by=actor_id,
            created_at=now,
            updated_at=now,
        )
        result = self.availability.add_availability(record)
        if self.audit:
            self.audit.log_availability_set(actor_id=actor_id, availability=result)
        return result

    def add_restriction(
        self,
        doctor_id: str,
        *,
        restriction_type: str,
        severity: str,
        starts_at: date,
        ends_at: date | None,
        description: str | None,
        reason_id: str | None,
        actor_id: str,
    ) -> DoctorRestrictionModel:
        """Add a restriction or license for a doctor."""
        doctor = self.doctors.get_by_id(doctor_id)
        if doctor is None:
            raise AvailabilityError("doctor_not_found", f"Doctor {doctor_id} not found")

        now = datetime.now(UTC)
        record = DoctorRestrictionModel(
            id=str(uuid.uuid4()),
            doctor_id=doctor_id,
            reason_id=reason_id,
            restriction_type=restriction_type,
            severity=severity,
            description=description,
            starts_at=starts_at,
            ends_at=ends_at,
            source="manual",
            review_status="approved",
            created_by=actor_id,
            created_at=now,
            updated_at=now,
        )
        result = self.availability.add_restriction(record)
        if self.audit:
            self.audit.log_restriction_added(actor_id=actor_id, restriction=result)
        return result

    def lift_restriction(
        self,
        restriction_id: str,
        *,
        actor_id: str,
    ) -> DoctorRestrictionModel:
        """Mark a restriction as lifted (soft delete by setting lifted_at)."""
        restriction = self.availability.get_restriction_by_id(restriction_id)
        if restriction is None:
            raise AvailabilityError("restriction_not_found", f"Restriction {restriction_id} not found")

        now = datetime.now(UTC)
        restriction.lifted_at = now
        restriction.lifted_by = actor_id
        restriction.updated_at = now
        if self.audit:
            self.audit.log_restriction_lifted(actor_id=actor_id, restriction=restriction)
        return restriction

    def has_submitted_monthly_availability(
        self, doctor_id: str, *, year: int, month: int
    ) -> bool:
        """Check if a doctor has submitted monthly availability for a given period."""
        records = self.availability.list_monthly_variable_for_period(doctor_id, year, month)
        return len(records) > 0
