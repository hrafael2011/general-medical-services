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
            raise AvailabilityError("doctor_not_found", f"Médico {doctor_id} no encontrado.")
        if doctor.availability_mode != "fixed":
            raise AvailabilityError(
                "mode_mismatch",
                "El modo de disponibilidad del médico es 'mensual'. "
                "Cambia el availability_mode a 'fixed' antes de configurar disponibilidad semanal.",
            )
        if not days_of_week or not all(0 <= d <= 6 for d in days_of_week):
            raise AvailabilityError(
                "invalid_days_of_week",
                "days_of_week debe ser una lista no vacía de enteros entre 0 (Lunes) y 6 (Domingo).",
            )

        for old in self.availability.list_fixed_patterns_for_doctor(doctor_id):
            self.availability.delete_availability(old.id)

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
            raise AvailabilityError("doctor_not_found", f"Médico {doctor_id} no encontrado.")
        if doctor.availability_mode != "monthly":
            raise AvailabilityError(
                "mode_mismatch",
                "El modo de disponibilidad del médico es 'fixed'. "
                "Cambia el availability_mode a 'monthly' antes de configurar disponibilidad mensual.",
            )
        if not 1 <= month <= 12:
            raise AvailabilityError("invalid_month", "El mes debe estar entre 1 y 12.")
        if not available_dates or not all(1 <= d <= 31 for d in available_dates):
            raise AvailabilityError(
                "invalid_available_dates",
                "available_dates debe ser una lista no vacía de días del mes (1-31).",
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

    def set_recurring_availability(
        self,
        doctor_id: str,
        *,
        weekday: int,
        week_number: int,
        actor_id: str,
    ) -> DoctorAvailabilityModel:
        """Set a recurring availability pattern (e.g., "last Friday of each month")."""
        doctor = self.doctors.get_by_id(doctor_id)
        if doctor is None:
            raise AvailabilityError("doctor_not_found", f"Médico {doctor_id} no encontrado.")
        if doctor.availability_mode != "fixed":
            raise AvailabilityError(
                "mode_mismatch",
                "La disponibilidad recurrente requiere availability_mode = 'fixed'.",
            )
        if not 0 <= weekday <= 6:
            raise AvailabilityError("invalid_weekday", "El día de la semana debe ser 0 (Lunes) a 6 (Domingo).")
        if week_number not in (-1, 0, 1, 2, 3):
            raise AvailabilityError("invalid_week_number", "El número de semana debe ser -1 (último) o 0-3.")

        for old in self.availability.list_fixed_patterns_for_doctor(doctor_id):
            self.availability.delete_availability(old.id)

        now = datetime.now(UTC)
        record = DoctorAvailabilityModel(
            id=str(uuid.uuid4()),
            doctor_id=doctor_id,
            availability_type="recurring",
            days_of_week=None,
            available_dates=None,
            weekday=weekday,
            week_number=week_number,
            year=None,
            month=None,
            submitted_at=None,
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
            raise AvailabilityError("doctor_not_found", f"Médico {doctor_id} no encontrado.")

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
            raise AvailabilityError("restriction_not_found", f"Restricción {restriction_id} no encontrada.")

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

    def get_available_doctor_ids(self, target_date: date) -> list[str]:
        """Return IDs of service-active doctors available on the given date."""
        from backend.app.domain.doctors.eligibility import AvailabilitySpec

        doctors = self.doctors.list_service_active()
        spec = AvailabilitySpec()
        available: list[str] = []

        for doctor in doctors:
            weekly = self.availability.list_weekly_fixed_for_doctor(doctor.id)
            monthly = self.availability.list_monthly_variable_for_period(
                doctor.id, target_date.year, target_date.month,
            )
            result = spec.check(doctor, target_date, weekly, monthly)
            if result.passed:
                available.append(doctor.id)

        return available
