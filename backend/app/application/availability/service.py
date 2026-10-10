import uuid
from datetime import UTC, date, datetime

from backend.app.application.audit.service import AuditService
from backend.app.application.availability.errors import AvailabilityError
from backend.app.application.doctors.service_state import sync_service_state
from backend.app.infrastructure.db.models.availability import (
    DoctorAvailabilityModel,
    DoctorRestrictionModel,
)
from backend.app.infrastructure.repositories.availability import AvailabilityRepository
from backend.app.infrastructure.repositories.catalogs import CatalogRepository
from backend.app.infrastructure.repositories.doctors import DoctorRepository


class AvailabilityService:
    def __init__(
        self,
        availability_repo: AvailabilityRepository,
        doctor_repo: DoctorRepository,
        audit: AuditService | None = None,
        catalog_repo: CatalogRepository | None = None,
    ) -> None:
        self.availability = availability_repo
        self.doctors = doctor_repo
        self.audit = audit
        self.catalog_repo = catalog_repo
        # Lo que la última operación limpió de los calendarios en borrador (lo lee la ruta).
        self._last_cleanup_info: dict = {}

    # --- Ausencias con fechas (eje 2) -------------------------------------------------
    #
    # Una ausencia es una `doctor_restriction`: el motor de asignación ya la respeta por
    # rango, así que el médico queda fuera **solo** entre `starts_at` y `ends_at` y vuelve
    # solo, sin que nadie lo reactive. `ends_at = None` es "indefinido": bloquea desde
    # `starts_at` sin fecha de fin y **no** genera recordatorio.
    # Ver `docs/specs/2026-10-09-licencias-con-fechas-y-recordatorio.md`.

    def _validate_restriction_dates(self, starts_at: date, ends_at: date | None) -> None:
        if ends_at is not None and ends_at < starts_at:
            raise AvailabilityError(
                "invalid_date_range",
                "La fecha de regreso no puede ser anterior a la fecha de inicio.",
            )

    def _cleanup_draft_assignments(self, doctor_id: str, starts_at, ends_at) -> None:
        """Quita al médico de los calendarios **en borrador** dentro del rango de la ausencia.

        Una asignación en un día que no puede servir es una asignación inválida: dejarla
        crearía un hueco de cobertura que nadie más va a arreglar. No toca los calendarios
        aprobados (eso es una versión nueva, un acto deliberado) ni nada fuera del rango.
        El resultado se deja en `_last_cleanup_info` para que la ruta pueda informarlo.
        """
        from backend.app.infrastructure.repositories.calendars import CalendarRepository

        # Una ausencia Indefinida no tiene fecha de fin (`None` = sin límite): ningún turno
        # futuro suyo en un borrador es válido, porque no se sabe cuándo vuelve.
        count, calendar_ids = CalendarRepository(
            self.availability.session
        ).delete_assignments_for_doctor_in_range(doctor_id, starts_at, ends_at)
        self._last_cleanup_info = {
            "removed_assignments": count,
            "affected_calendar_ids": calendar_ids,
        }

    def _validate_restriction_reason(self, reason_id: str | None, doctor) -> None:
        """El motivo debe existir y aplicar al sexo del médico.

        Se decide por el **atributo** del motivo, nunca por su `code`: el catálogo es
        editable y un motivo nuevo tiene que funcionar sin tocar código.
        """
        if reason_id is None or self.catalog_repo is None:
            return
        reason = self.catalog_repo.get_deactivation_reason_by_id(reason_id)
        if reason is None:
            raise AvailabilityError(
                "reason_not_found", f"El motivo de ausencia {reason_id} no existe."
            )
        if reason.applies_to_sex is not None and doctor.sex != reason.applies_to_sex:
            raise AvailabilityError(
                "reason_sex_mismatch",
                "Este motivo de ausencia no aplica al sexo del médico.",
            )

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
            doctor.availability_mode = "monthly"
            self.doctors.update(doctor)
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

        self._validate_restriction_dates(starts_at, ends_at)
        self._validate_restriction_reason(reason_id, doctor)

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
        if severity == "hard_block":
            self._cleanup_draft_assignments(doctor_id, starts_at, ends_at)
        # Registrar una ausencia cambia el estado del médico: se recalcula aquí mismo para que
        # el tablero, el asistente y los reportes lo vean al instante.
        sync_service_state(
            self.availability.session, doctor_ids=[doctor_id], actor_id=actor_id
        )
        return result

    def update_restriction(
        self,
        restriction_id: str,
        *,
        starts_at: date,
        ends_at: date | None,
        reason_id: str | None,
        description: str | None,
        severity: str,
        actor_id: str,
    ) -> DoctorRestrictionModel:
        """Corrige una ausencia ya registrada.

        Cambiar la fecha de regreso **re-arma el aviso**: la clave de idempotencia del
        recordatorio incluye esa fecha, así que con una fecha nueva el aviso vuelve a estar
        permitido y con la misma fecha no se repite. No hay que tocar nada más.
        """
        restriction = self.availability.get_restriction_by_id(restriction_id)
        if restriction is None:
            raise AvailabilityError(
                "restriction_not_found", f"Restricción {restriction_id} no encontrada."
            )
        doctor = self.doctors.get_by_id(restriction.doctor_id)
        if doctor is None:
            raise AvailabilityError(
                "doctor_not_found", f"Médico {restriction.doctor_id} no encontrado."
            )

        self._validate_restriction_dates(starts_at, ends_at)
        self._validate_restriction_reason(reason_id, doctor)

        previous_ends_at = restriction.ends_at
        restriction.starts_at = starts_at
        restriction.ends_at = ends_at
        restriction.reason_id = reason_id
        restriction.description = description
        restriction.severity = severity
        restriction.updated_at = datetime.now(UTC)
        if self.audit:
            self.audit.log_restriction_updated(
                actor_id=actor_id,
                restriction=restriction,
                previous_ends_at=previous_ends_at,
            )
        # Cambiar las fechas puede meter o sacar al médico de una ausencia vigente, y deja
        # turnos de borrador dentro del rango nuevo que ya no puede cubrir.
        if severity == "hard_block":
            self._cleanup_draft_assignments(restriction.doctor_id, starts_at, ends_at)
        sync_service_state(
            self.availability.session, doctor_ids=[restriction.doctor_id], actor_id=actor_id
        )
        return restriction

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
        # Levantar la ausencia es lo que devuelve al médico al servicio.
        sync_service_state(
            self.availability.session, doctor_ids=[restriction.doctor_id], actor_id=actor_id
        )
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
