import hashlib
import uuid
from calendar import monthrange
from datetime import UTC, date, datetime
from uuid import uuid4

from backend.app.application.audit.service import AuditService
from backend.app.application.calendars.errors import CalendarServiceError
from backend.app.application.notifications.triggers import NotificationTriggers
from backend.app.domain.calendars.coverage import (
    CoverageGap,
    RequiredArea,
    find_coverage_gaps,
    format_coverage_message,
)
from backend.app.domain.calendars.weeks import compute_weeks
from backend.app.infrastructure.db.models.calendars import (
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

    # --- Cobertura obligatoria ---

    def _coverage_gaps(
        self,
        *,
        assignments,
        start_date: date,
        end_date: date,
    ) -> list[CoverageGap]:
        """Huecos de cobertura en el rango, leyendo las áreas del catálogo."""
        areas = self.repo.list_service_areas()
        code_by_id = {area.id: area.code for area in areas}
        required = [
            RequiredArea(code=area.code, display_name=area.display_name)
            for area in areas
            if area.active and area.required_for_daily_coverage
        ]
        return find_coverage_gaps(
            start_date=start_date,
            end_date=end_date,
            required_areas=required,
            assignments=[
                (a.service_date, code_by_id.get(a.service_area_id, a.service_area_id))
                for a in assignments
            ],
        )

    @staticmethod
    def _month_bounds(year: int, month: int) -> tuple[date, date]:
        last_day = monthrange(year, month)[1]
        return date(year, month, 1), date(year, month, last_day)

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
                f"Modo de generación de calendario no soportado: {generation_mode}.",
            )

        existing = self.repo.get_calendar_by_period(year, month)
        if existing is not None:
            raise CalendarServiceError(
                "calendar_already_exists",
                f"Ya existe un calendario para {year}-{month:02d}.",
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

        # Create weeks for the calendar month (Monday-Sunday weeks)
        for week in compute_weeks(year, month):
            week_model = CalendarWeekModel(
                id=str(uuid.uuid4()),
                calendar_id=calendar.id,
                calendar_version_id=version.id,
                week_number=week[0],
                label=week[1],
                start_date=date(week[2], week[3], week[4]),
                end_date=date(week[5], week[6], week[7]),
            )
            self.repo.add_week(week_model)

        if self.audit is not None:
            self.audit.log_calendar_created(actor_id=actor_id, calendar=calendar)

        # Generate empty initial ranking (no assignments yet, but ranking record exists)
        if self.mission_ranking_service is not None:
            try:
                self.mission_ranking_service.generate_ranking(
                    actor_id=actor_id,
                    year=year,
                    month=month,
                    calendar_version_id=version.id,
                )
            except Exception:
                import logging
                _logger = logging.getLogger(__name__)
                _logger.exception(
                    "Failed to generate initial ranking for %d/%02d (non-fatal)",
                    year, month,
                )

        return calendar

    def get_calendar(self, calendar_id: str) -> CalendarModel:
        calendar = self.repo.get_calendar_by_id(calendar_id)
        if calendar is None:
            raise CalendarServiceError(
                "calendar_not_found",
                f"Calendario con id {calendar_id} no encontrado.",
            )
        return calendar

    def list_calendars(self) -> list[CalendarModel]:
        return self.repo.list_calendars()

    def soft_delete_calendar(self, *, actor_id: str, calendar_id: str) -> None:
        """Permanently delete a calendar and all its related data."""
        calendar = self.repo.get_calendar_by_id(calendar_id)
        if calendar is None:
            raise CalendarServiceError(
                "calendar_not_found",
                f"Calendario con id {calendar_id} no encontrado.",
            )
        self.repo.hard_delete_calendar(calendar_id)

        if self.audit is not None:
            self.audit.log_calendar_deleted(actor_id=actor_id, calendar=calendar)

    def restore_calendar(self, *, actor_id: str, calendar_id: str) -> CalendarModel:
        """Restore a soft-deleted calendar and all its versions."""
        calendar = self.repo.get_calendar_by_id_including_deleted(calendar_id)
        if calendar is None:
            raise CalendarServiceError(
                "calendar_not_found",
                f"Calendario con id {calendar_id} no encontrado.",
            )
        if calendar.deleted_at is None:
            raise CalendarServiceError(
                "calendar_not_deleted",
                "El calendario no está eliminado.",
            )
        self.repo.restore_calendar(calendar_id)
        if self.audit is not None:
            self.audit.log_calendar_restored(actor_id=actor_id, calendar=calendar)
        return calendar

    def hard_delete_calendar(self, *, actor_id: str, calendar_id: str) -> None:
        """Permanently remove a calendar and all related data."""
        calendar = self.repo.get_calendar_by_id_including_deleted(calendar_id)
        if calendar is None:
            raise CalendarServiceError(
                "calendar_not_found",
                f"Calendario con id {calendar_id} no encontrado.",
            )
        self.repo.hard_delete_calendar(calendar_id)

    def list_deleted_calendars(self) -> list[CalendarModel]:
        """List soft-deleted calendars for trash/recovery UI."""
        return self.repo.list_deleted_calendars()

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
                f"Calendario con id {calendar_id} no encontrado.",
            )

        versions = self.repo.list_versions(calendar_id)
        version = next(
            (v for v in versions if v.version_number == version_number), None
        )
        if version is None:
            raise CalendarServiceError(
                "version_not_found",
                f"Versión {version_number} no encontrada para el calendario {calendar_id}.",
            )

        if version.status == "approved":
            raise CalendarServiceError(
                "calendar_already_approved",
                f"La versión {version_number} ya está aprobada.",
            )

        # Aprobar publica y avisa: no puede salir un mes con días o áreas vacías.
        month_start, month_end = self._month_bounds(calendar.year, calendar.month)
        gaps = self._coverage_gaps(
            assignments=self.repo.list_assignments(version.id),
            start_date=month_start,
            end_date=month_end,
        )
        if gaps:
            raise CalendarServiceError(
                "calendar_incomplete",
                format_coverage_message(gaps),
                details=[gap.to_detail() for gap in gaps],
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

        # Re-aprobar tras un desbloqueo SÍ avisa: corregir un error tiene que
        # llegar a los médicos. Antes se callaba todo con el `__unlock__`, y la
        # versión buena no le llegaba a nadie. El aviso se reutiliza (misma
        # clave de idempotencia), así que re-aprobar no lo duplica.
        if version.reason and version.reason.startswith("__unlock__"):
            # Restore original reason
            if "__orig__" in version.reason:
                version.reason = version.reason.split("__orig__", 1)[1]
            else:
                version.reason = None

        if self.triggers is not None:
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
                f"Calendario con id {calendar_id} no encontrado.",
            )

        if calendar.status != "approved":
            raise CalendarServiceError(
                "invalid_status_transition",
                "Solo se puede desbloquear un calendario aprobado.",
            )

        versions = self.repo.list_versions(calendar_id)
        if not versions:
            raise CalendarServiceError(
                "version_not_found",
                f"No se encontraron versiones para el calendario {calendar_id}.",
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

        # Mismo criterio que `unlock_week`: lo que el calendario encoló y aún
        # no ha salido se cancela antes de devolverlo a borrador.
        cancelled = {"notifications": 0, "confirmations": 0}
        if self.triggers is not None:
            cancelled = self.triggers.on_week_unapproved(
                actor_id=actor_id,
                assignments=current_assignments,
            )
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
            if cancelled["notifications"] or cancelled["confirmations"]:
                self.audit.log_notifications_cancelled(
                    actor_id=actor_id,
                    calendar=calendar,
                    scope="calendar",
                    notification_count=cancelled["notifications"],
                    confirmation_count=cancelled["confirmations"],
                )

        version.cancelled_notifications = cancelled["notifications"]

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
                f"Calendario con id {calendar_id} no encontrado.",
            )

        if calendar.status != "approved":
            raise CalendarServiceError(
                "invalid_status_transition",
                "Solo se puede crear una nueva versión desde un calendario aprobado.",
            )

        versions = self.repo.list_versions(calendar_id)
        if not versions:
            raise CalendarServiceError(
                "version_not_found",
                f"No se encontraron versiones para el calendario {calendar_id}.",
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

    # --- Week-level operations ---

    def approve_week(
        self,
        *,
        actor_id: str,
        week_id: str,
        notes: str | None = None,
    ) -> CalendarWeekModel:
        """Approve a single week's assignments and notify assigned doctors."""
        week = self.repo.get_week_by_id(week_id)
        if week is None:
            raise CalendarServiceError(
                "week_not_found",
                f"Semana {week_id} no encontrada.",
            )

        if week.status == "approved":
            raise CalendarServiceError(
                "week_already_approved",
                f"La semana {week_id} ya está aprobada.",
            )

        # Require at least one assignment to approve a week
        week_assignments = self.repo.list_assignments(week.calendar_version_id)
        assignments_in_week = [
            a for a in week_assignments
            if week.start_date <= a.service_date <= week.end_date
        ]
        if not assignments_in_week:
            raise CalendarServiceError(
                "week_empty",
                "No puedes aprobar una semana sin médicos asignados. "
                "Asigna al menos un médico antes de aprobar.",
            )

        # Los días de la semana que caen en el mes siguiente pertenecen a otro
        # calendario: no se reclaman aquí.
        calendar = self.repo.get_calendar_by_id(week.calendar_id)
        if calendar is not None:
            month_start, month_end = self._month_bounds(calendar.year, calendar.month)
            gaps = self._coverage_gaps(
                assignments=assignments_in_week,
                start_date=max(week.start_date, month_start),
                end_date=min(week.end_date, month_end),
            )
            if gaps:
                raise CalendarServiceError(
                    "week_incomplete",
                    format_coverage_message(gaps),
                    details=[gap.to_detail() for gap in gaps],
                )

        now = datetime.now(UTC)
        self.repo.update_week_status(
            week_id=week_id,
            status="approved",
            approved_by=actor_id,
        )
        # Refresh so the returned object reflects the update
        week.status = "approved"
        week.approved_by = actor_id
        week.approved_at = now

        # Update calendar status
        if calendar is not None:
            all_weeks = self.repo.list_weeks(calendar.id)
            if all(w.status == "approved" for w in all_weeks):
                calendar.status = "approved"
                calendar.approved_at = now
                calendar.approved_by = actor_id

                # Mark the version as approved too (mirrors approve_version)
                version = self.repo.get_version_by_id(week.calendar_version_id)
                if version is not None and version.status != "approved":
                    version.status = "approved"
                    version.approved_at = now
                    version.approved_by = actor_id

                    if self.audit is not None:
                        self.audit.log_calendar_approved(
                            actor_id=actor_id,
                            calendar=calendar,
                            version=version,
                        )

                    # Generate mission ranking for the approved calendar
                    if self.mission_ranking_service is not None:
                        self.mission_ranking_service.generate_ranking(
                            actor_id=actor_id,
                            year=calendar.year,
                            month=calendar.month,
                            calendar_version_id=version.id,
                        )

            elif calendar.status == "draft":
                calendar.status = "partial"

                # Generate mission ranking when entering partial (first week approved)
                if self.mission_ranking_service is not None:
                    version = self.repo.get_version_by_id(week.calendar_version_id)
                    if version is not None:
                        self.mission_ranking_service.generate_ranking(
                            actor_id=actor_id,
                            year=calendar.year,
                            month=calendar.month,
                            calendar_version_id=version.id,
                        )
            calendar.updated_at = now
            self.repo.session.flush()

        # Notify doctors assigned in this week
        if self.triggers is not None:
            assignments = self.repo.list_assignments(week.calendar_version_id)
            week_assignments = [
                a for a in assignments
                if week.start_date <= a.service_date <= week.end_date
            ]
            self.triggers.on_week_approved(
                actor_id=actor_id,
                assignments=week_assignments,
                week=week,
            )

        return week

    def unlock_week(
        self,
        *,
        actor_id: str,
        week_id: str,
        notes: str | None = None,
    ) -> CalendarWeekModel:
        """Revert a week to draft status for editing."""
        week = self.repo.get_week_by_id(week_id)
        if week is None:
            raise CalendarServiceError(
                "week_not_found",
                f"Semana {week_id} no encontrada.",
            )

        if week.status != "approved":
            raise CalendarServiceError(
                "week_not_approved",
                f"La semana {week_id} no está aprobada, no se puede desbloquear.",
            )

        # Compute hash of current assignments before reverting
        assignments = self.repo.list_assignments(week.calendar_version_id)
        week_assignments = sorted(
            [
                a
                for a in assignments
                if week.start_date <= a.service_date <= week.end_date
            ],
            key=lambda a: (a.service_date, a.service_area_id, a.doctor_id),
        )
        hash_input = "|".join(
            f"{a.doctor_id}|{a.service_date}|{a.service_area_id}"
            for a in week_assignments
        )
        assignments_hash = hashlib.md5(hash_input.encode()).hexdigest()

        now = datetime.now(UTC)
        # Deshacer debe deshacer: lo que esta semana encoló y aún no ha salido
        # se cancela aquí, mientras seguimos sabiendo a qué semana pertenece.
        cancelled = {"notifications": 0, "confirmations": 0}
        if self.triggers is not None:
            cancelled = self.triggers.on_week_unapproved(
                actor_id=actor_id,
                assignments=week_assignments,
            )
        self.repo.update_week_status(
            week_id=week_id,
            status="draft",
            previous_assignments_hash=assignments_hash,
        )
        week.status = "draft"
        week.approved_by = None
        week.approved_at = None
        week.previous_assignments_hash = assignments_hash

        # Set calendar back to partial (at least one week is now draft)
        calendar = self.repo.get_calendar_by_id(week.calendar_id)
        if calendar is not None and calendar.status == "approved":
            calendar.status = "partial"
            calendar.updated_at = now

        # Reset version status to draft (mirrors unlock_calendar)
        version = self.repo.get_version_by_id(week.calendar_version_id)
        if version is not None:
            version.status = "draft"
            version.approved_at = None
            version.approved_by = None
            # snapshot hash for change detection on re-approval
            original_reason = version.reason
            if assignments_hash:
                version.reason = f"__unlock__{assignments_hash}"
                if original_reason:
                    version.reason += f"__orig__{original_reason}"

        self.repo.session.flush()

        if (
            self.audit is not None
            and calendar is not None
            and (cancelled["notifications"] or cancelled["confirmations"])
        ):
            self.audit.log_notifications_cancelled(
                actor_id=actor_id,
                calendar=calendar,
                scope="week",
                notification_count=cancelled["notifications"],
                confirmation_count=cancelled["confirmations"],
            )

        # Atributo transitorio: lo lee la respuesta HTTP para decir cuántos
        # avisos se retiraron. No se persiste.
        week.cancelled_notifications = cancelled["notifications"]

        return week
