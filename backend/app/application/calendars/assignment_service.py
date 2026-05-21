from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from backend.app.application.audit.service import AuditService
from backend.app.application.calendars.errors import CalendarServiceError
from backend.app.application.notifications.triggers import NotificationTriggers
from backend.app.domain.doctors.eligibility import EligibilityChecker, EligibilityResult
from backend.app.infrastructure.db.models.calendars import CalendarAssignmentModel, UnresolvedGapModel
from backend.app.infrastructure.repositories.availability import AvailabilityRepository
from backend.app.infrastructure.repositories.calendars import CalendarRepository
from backend.app.infrastructure.repositories.doctors import DoctorRepository
from backend.app.infrastructure.repositories.missions import MissionRepository
from backend.app.domain.calendars.engine import CalendarEngine, GenerationContext
from backend.app.domain.calendars.scoring import evaluate_soft_warnings
from backend.app.domain.calendars.types import SlotRequest
from backend.app.domain.availability_rules import belongs_to_operational_month

# Codes that indicate a hard block — cannot be overridden.
_HARD_BLOCK_CODES = {"doctor_inactive", "area_not_allowed", "has_hard_block"}


class _MonthlyLimitWarning:
    code = "monthly_max_exceeded"

    def __init__(self, reason: str) -> None:
        self.reason = reason


class _SoftRuleWarning:
    def __init__(self, code: str, reason: str) -> None:
        self.code = code
        self.reason = reason


class AssignmentService:
    def __init__(
        self,
        calendar_repo: CalendarRepository,
        doctor_repo: DoctorRepository,
        availability_repo: AvailabilityRepository,
        audit: AuditService | None = None,
        triggers: NotificationTriggers | None = None,
    ) -> None:
        self.calendar_repo = calendar_repo
        self.doctor_repo = doctor_repo
        self.availability_repo = availability_repo
        self.audit = audit
        self.triggers = triggers

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _has_availability_for_date(
        self, doctor_id: str, target_date: date, year: int, month: int
    ) -> bool:
        """Check if doctor is available on target_date (same logic as engine)."""
        weekly = [
            record for record in self.availability_repo.list_availability_for_doctor(doctor_id)
            if record.availability_type in ("weekly_fixed", "recurring")
        ]
        monthly_var = self.availability_repo.list_monthly_variable_for_period(doctor_id, year, month)
        records = weekly + monthly_var

        if not records:
            return True

        for record in records:
            availability_type = record.availability_type

            effective_from = getattr(record, "effective_from", None)
            effective_to = getattr(record, "effective_to", None)

            if effective_from is not None:
                eff_from = effective_from.date() if hasattr(effective_from, "date") else effective_from
                if target_date < eff_from:
                    continue

            if effective_to is not None:
                eff_to = effective_to.date() if hasattr(effective_to, "date") else effective_to
                if target_date > eff_to:
                    continue

            if availability_type == "monthly_variable":
                rec_month = getattr(record, "month", None)
                rec_year = getattr(record, "year", None)
                if rec_month != target_date.month or rec_year != target_date.year:
                    continue
                available_days = (
                    getattr(record, "available_days", None)
                    or getattr(record, "available_dates", None)
                    or []
                )
                if available_days is None:
                    available_days = []
                if target_date.day in available_days:
                    return True

            elif availability_type == "weekly_fixed":
                days_of_week = getattr(record, "days_of_week", None) or []
                if days_of_week is None:
                    days_of_week = []
                if target_date.weekday() in days_of_week:
                    return True

        return False

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
        weekly_availability = [
            record for record in self.availability_repo.list_availability_for_doctor(doctor.id)
            if record.availability_type in ("weekly_fixed", "recurring")
        ]
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

    def _run_eligibility_with_force(
        self,
        *,
        doctor,
        service_area_id: str,
        target_date: date,
        force_warnings: list[str],
    ) -> list:
        """Run eligibility but suppress soft warnings covered by force_warnings."""
        allowed_area_ids = self.doctor_repo.get_allowed_areas(doctor.id)
        active_restrictions = self.availability_repo.list_active_restrictions_for_doctor(
            doctor.id, target_date
        )
        weekly_availability = [
            record for record in self.availability_repo.list_availability_for_doctor(doctor.id)
            if record.availability_type in ("weekly_fixed", "recurring")
        ]
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

        hard_blocks = [r for r in report.blockers if r.code in _HARD_BLOCK_CODES]
        soft_warnings = [r for r in report.blockers if r.code not in _HARD_BLOCK_CODES]

        if hard_blocks:
            raise CalendarServiceError("hard_block", hard_blocks[0].reason)

        unacknowledged = [w for w in soft_warnings if w.code not in force_warnings]
        if unacknowledged:
            raise CalendarServiceError("soft_warning", f"Falta confirmar: {unacknowledged[0].reason}")

        return soft_warnings

    def _check_monthly_limit(
        self,
        *,
        version_id: str,
        doctor,
        target_date: date,
        exclude_assignment_id: str | None = None,
    ) -> _MonthlyLimitWarning | None:
        version = self.calendar_repo.get_version_by_id(version_id)
        if version is None:
            return None
        calendar = self.calendar_repo.get_calendar_by_id(version.calendar_id)
        if calendar is None:
            return None

        current_count = sum(
            1
            for assignment in self.calendar_repo.list_assignments(version_id)
            if assignment.doctor_id == doctor.id
            and assignment.id != exclude_assignment_id
            and belongs_to_operational_month(assignment.service_date, calendar.year, calendar.month)
        )
        monthly_max = getattr(doctor, "monthly_service_max", 3) or 3
        if current_count < monthly_max:
            return None

        reason = f"Ya alcanzó el máximo mensual ({monthly_max}) servicios."
        if getattr(doctor, "monthly_service_limit_mode", "warn_only") == "hard_limit":
            raise CalendarServiceError("hard_block", reason)
        return _MonthlyLimitWarning(reason)

    def _apply_monthly_limit(
        self,
        *,
        version_id: str,
        doctor,
        target_date: date,
        force_warnings: list[str] | None,
        soft_warnings: list,
        exclude_assignment_id: str | None = None,
    ) -> list:
        monthly_warning = self._check_monthly_limit(
            version_id=version_id,
            doctor=doctor,
            target_date=target_date,
            exclude_assignment_id=exclude_assignment_id,
        )
        if monthly_warning is None:
            return soft_warnings
        if force_warnings is not None and monthly_warning.code in force_warnings:
            return [*soft_warnings, monthly_warning]
        raise CalendarServiceError("soft_warning", monthly_warning.reason)

    def _collect_scoring_warnings(
        self,
        *,
        version_id: str,
        doctor_id: str,
        target_date: date,
        service_area_id: str,
        exclude_assignment_id: str | None = None,
    ) -> list[_SoftRuleWarning]:
        version = self.calendar_repo.get_version_by_id(version_id)
        if version is None:
            return []
        calendar = self.calendar_repo.get_calendar_by_id(version.calendar_id)
        if calendar is None:
            return []

        monthly_assignments = [
            {
                "doctor_id": assignment.doctor_id,
                "service_date": assignment.service_date,
                "service_area_id": assignment.service_area_id,
            }
            for assignment in self.calendar_repo.list_assignments(version_id)
            if assignment.id != exclude_assignment_id
            and assignment.doctor_id == doctor_id
            and belongs_to_operational_month(assignment.service_date, calendar.year, calendar.month)
        ]

        history_start = target_date - timedelta(days=60)
        history_end = target_date - timedelta(days=1)
        historical_assignments = [
            {
                "doctor_id": assignment.doctor_id,
                "service_date": assignment.service_date,
                "service_area_id": assignment.service_area_id,
            }
            for assignment in self.calendar_repo.list_assignments_in_date_range(
                history_start,
                history_end,
            )
            if assignment.id != exclude_assignment_id
        ]

        mission_repo = MissionRepository(self.calendar_repo.session)
        confirmed_missions = mission_repo.list_confirmed_in_range(history_start, history_end)
        mission_assignments: list[dict] = []
        for mission, participants in confirmed_missions:
            for participant in participants:
                mission_assignments.append({
                    "doctor_id": participant.doctor_id,
                    "mission_date": mission.mission_date,
                })

        area_weights, strong_uuids = self._build_area_metadata()
        slot = SlotRequest(
            date=target_date,
            service_area_id=service_area_id,
            area_weight=area_weights.get(service_area_id, 1.0),
        )
        return [
            _SoftRuleWarning(code=warning, reason=warning)
            for warning in evaluate_soft_warnings(
                doctor_id=doctor_id,
                slot=slot,
                monthly_assignments=monthly_assignments,
                historical_assignments=historical_assignments,
                mission_assignments=mission_assignments,
                area_weights=area_weights,
                strong_area_ids=strong_uuids,
            )
        ]

    def _apply_scoring_warnings(
        self,
        *,
        version_id: str,
        doctor_id: str,
        target_date: date,
        service_area_id: str,
        force_warnings: list[str] | None,
        override_justification: str | None,
        soft_warnings: list,
        exclude_assignment_id: str | None = None,
    ) -> list:
        scoring_warnings = self._collect_scoring_warnings(
            version_id=version_id,
            doctor_id=doctor_id,
            target_date=target_date,
            service_area_id=service_area_id,
            exclude_assignment_id=exclude_assignment_id,
        )
        if not scoring_warnings:
            return soft_warnings

        if override_justification:
            return [*soft_warnings, *scoring_warnings]

        if force_warnings is not None:
            unacknowledged = [
                warning for warning in scoring_warnings if warning.code not in force_warnings
            ]
            if unacknowledged:
                raise CalendarServiceError(
                    "soft_warning",
                    f"Falta confirmar: {unacknowledged[0].reason}",
                )
            return [*soft_warnings, *scoring_warnings]

        raise CalendarServiceError("soft_warning", scoring_warnings[0].reason)

    def get_eligible_doctors_for_slot(
        self,
        *,
        version_id: str,
        target_date: date,
        service_area_id: str,
    ) -> list:
        """Return eligible doctors for a specific slot (date + area).

        Loads all necessary data (doctors, areas, availability, restrictions,
        existing assignments, historical assignments, missions) and builds a
        GenerationContext that the domain engine's get_eligible_doctors needs.
        """
        # 1. Load version and calendar.
        version = self.calendar_repo.get_version_by_id(version_id)
        if version is None:
            raise CalendarServiceError(
                "version_not_found",
                f"Calendar version '{version_id}' not found.",
            )

        calendar = self.calendar_repo.get_calendar_by_id(version.calendar_id)
        if calendar is None:
            raise CalendarServiceError(
                "calendar_not_found",
                f"Calendar for version '{version_id}' not found.",
            )

        # 2. Load all service-active doctors.
        doctors = self.doctor_repo.list_service_active()

        # 3. Load allowed areas per doctor.
        allowed_areas: dict[str, list[str]] = {}
        for d in doctors:
            allowed_areas[d.id] = self.doctor_repo.get_allowed_areas(d.id)

        # 4. Load availability per doctor.
        availability: dict[str, list] = {}
        for d in doctors:
            availability[d.id] = self.availability_repo.list_availability_for_doctor(d.id)

        # 5. Load active restrictions per doctor for target_date.
        restrictions: dict[str, list] = {}
        for d in doctors:
            restrictions[d.id] = self.availability_repo.list_active_restrictions_for_doctor(
                d.id, target_date
            )

        # 6. Load existing assignments for this version.
        existing = self.calendar_repo.list_assignments(version_id)
        existing_dicts = [
            {
                "doctor_id": a.doctor_id,
                "service_date": a.service_date,
                "service_area_id": a.service_area_id,
            }
            for a in existing
        ]

        # 7. Load historical assignments (60 days before target_date).
        history_start = target_date - timedelta(days=60)
        history_end = target_date - timedelta(days=1)
        historical = self.calendar_repo.list_assignments_in_date_range(history_start, history_end)
        historical_dicts = [
            {
                "doctor_id": a.doctor_id,
                "service_date": a.service_date,
                "service_area_id": a.service_area_id,
            }
            for a in historical
        ]

        # 8. Load 60-day mission assignments for spacing rules.
        mission_repo = MissionRepository(self.calendar_repo.session)
        confirmed_missions = mission_repo.list_confirmed_in_range(history_start, history_end)
        mission_dicts: list[dict] = []
        for _mission, participants in confirmed_missions:
            for p in participants:
                mission_dicts.append({
                    "doctor_id": p.doctor_id,
                    "mission_date": _mission.mission_date,
                })

        # 9. Build area metadata from DB for UUID-native scoring.
        area_weights, strong_uuids = self._build_area_metadata()

        # 10. Build GenerationContext for the engine.
        ctx = GenerationContext(
            year=calendar.year,
            month=calendar.month,
            doctors=doctors,
            allowed_areas=allowed_areas,
            availability=availability,
            restrictions=restrictions,
            existing_assignments=existing_dicts,
            historical_assignments=historical_dicts,
            mission_assignments=mission_dicts,
            required_areas=[],
            area_weights=area_weights,
            strong_area_ids=strong_uuids,
            monthly_service_targets={d.id: getattr(d, "monthly_service_target", 3) for d in doctors},
            monthly_service_maxes={d.id: getattr(d, "monthly_service_max", 3) for d in doctors},
        )

        # 11. Build SlotRequest.
        slot = SlotRequest(
            date=target_date,
            service_area_id=service_area_id,
            area_weight=area_weights.get(service_area_id, 1.0),
        )

        # 11. Delegate to the domain engine.
        engine = CalendarEngine()
        return engine.get_eligible_doctors(slot, ctx, existing_dicts)

    def evaluate_slot(
        self,
        *,
        version_id: str,
        doctor_id: str,
        target_date: date,
        service_area_id: str,
    ) -> dict:
        """Evaluate a doctor for a specific slot.

        Returns
        -------
        dict with keys:
            hard_blocks : list[dict]
                Blocking issues found (empty list = no hard blocks).
            warnings : list[str]
                Soft-rule warnings from the scoring module (empty when hard_blocks
                are present, since evaluation stops at the first hard block).
        """
        # 1. Load version and calendar.
        version = self.calendar_repo.get_version_by_id(version_id)
        if version is None:
            raise CalendarServiceError(
                "version_not_found",
                f"Calendar version '{version_id}' not found.",
            )

        calendar = self.calendar_repo.get_calendar_by_id(version.calendar_id)
        if calendar is None:
            raise CalendarServiceError(
                "calendar_not_found",
                f"Calendar for version '{version_id}' not found.",
            )

        # 2. Load doctor.
        doctor = self.doctor_repo.get_by_id(doctor_id)
        if doctor is None:
            raise CalendarServiceError(
                "doctor_not_found",
                f"Doctor '{doctor_id}' not found.",
            )

        hard_blocks: list[dict] = []

        # 3a. Inactive doctor.
        if not doctor.active or not doctor.service_active:
            hard_blocks.append({
                "code": "doctor_inactive",
                "description": "El médico no está activo o no tiene servicio activo.",
            })

        # 3b. Area not allowed.
        allowed_areas = self.doctor_repo.get_allowed_areas(doctor.id)
        if service_area_id not in allowed_areas:
            hard_blocks.append({
                "code": "area_not_allowed",
                "description": "El médico no tiene permiso para esta área.",
            })

        # 3c. Has hard-block restriction.
        restrictions = self.availability_repo.list_active_restrictions_for_doctor(
            doctor.id, target_date
        )
        for r in restrictions:
            if getattr(r, "severity", None) == "hard_block":
                hard_blocks.append({
                    "code": "has_hard_block",
                    "description": getattr(r, "reason", None) or "Restricción de tipo hard block.",
                })
                break

        # 3d. No availability for target_date.
        if not self._has_availability_for_date(
            doctor.id, target_date, target_date.year, target_date.month
        ):
            hard_blocks.append({
                "code": "no_availability",
                "description": "No tiene disponibilidad para esta fecha.",
            })

        # 3e. Already assigned on this date.
        existing_today = self.calendar_repo.list_assignments_for_date(version_id, target_date)
        if any(a.doctor_id == doctor_id for a in existing_today):
            hard_blocks.append({
                "code": "already_assigned_today",
                "description": "Ya tiene un turno asignado en esta fecha.",
            })

        # 3f. Monthly max exceeded.
        monthly_assignments_all = self.calendar_repo.list_assignments(version_id)
        monthly_for_doctor = [
            a
            for a in monthly_assignments_all
            if a.doctor_id == doctor_id
            and belongs_to_operational_month(a.service_date, calendar.year, calendar.month)
        ]
        monthly_max = getattr(doctor, "monthly_service_max", 3) or 3
        if len(monthly_for_doctor) >= monthly_max:
            limit_item = {
                "code": "monthly_max_exceeded",
                "description": f"Ya alcanzó el máximo mensual ({monthly_max}) servicios.",
            }
            if getattr(doctor, "monthly_service_limit_mode", "warn_only") == "hard_limit":
                hard_blocks.append(limit_item)

        # 3g. Slot occupied by another doctor.
        existing_slot = self.calendar_repo.get_assignment_for_slot(
            version_id, target_date, service_area_id
        )
        if existing_slot is not None and existing_slot.doctor_id != doctor_id:
            hard_blocks.append({
                "code": "slot_occupied",
                "description": "El turno ya está ocupado por otro médico.",
            })

        # Return early if any hard blocks found.
        if hard_blocks:
            return {"hard_blocks": hard_blocks, "warnings": []}

        warning_items = [
            {"code": warning.code, "description": warning.reason}
            for warning in self._collect_scoring_warnings(
                version_id=version_id,
                doctor_id=doctor_id,
                target_date=target_date,
                service_area_id=service_area_id,
            )
        ]
        if len(monthly_for_doctor) >= monthly_max:
            warning_items.append({
                "code": "monthly_max_exceeded",
                "description": f"Ya alcanzó el máximo mensual ({monthly_max}) servicios.",
            })

        return {"hard_blocks": hard_blocks, "warnings": warning_items}

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
        force_warnings: list[str] | None = None,
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
        self._ensure_week_is_editable(version_id=version_id, service_date=date)

        # 3. Load doctor.
        doctor = self.doctor_repo.get_by_id(doctor_id)
        if doctor is None:
            raise CalendarServiceError(
                "doctor_not_found",
                f"Doctor '{doctor_id}' not found.",
            )

        # 4. Eligibility checks.
        if force_warnings is not None:
            soft_warnings_raw = self._run_eligibility_with_force(
                doctor=doctor,
                service_area_id=service_area_id,
                target_date=date,
                force_warnings=force_warnings,
            )
        else:
            soft_warnings_raw = self._run_eligibility(
                doctor=doctor,
                service_area_id=service_area_id,
                target_date=date,
                override_justification=override_justification,
            )
        soft_warnings_raw = self._apply_monthly_limit(
            version_id=version_id,
            doctor=doctor,
            target_date=date,
            force_warnings=force_warnings,
            soft_warnings=soft_warnings_raw,
        )
        soft_warnings_raw = self._apply_scoring_warnings(
            version_id=version_id,
            doctor_id=doctor_id,
            target_date=date,
            service_area_id=service_area_id,
            force_warnings=force_warnings,
            override_justification=override_justification,
            soft_warnings=soft_warnings_raw,
        )

        # 5. Persist assignment.
        stored_justification = override_justification if override_justification else None
        rationale = {
            "overridden_warnings": force_warnings or [],
            "forced_by": actor_id,
        } if force_warnings else _manual_rationale(soft_warnings_raw)

        assignment = CalendarAssignmentModel(
            id=str(uuid4()),
            calendar_version_id=version_id,
            doctor_id=doctor_id,
            service_date=date,
            service_area_id=service_area_id,
            assignment_source="manual",
            rationale=rationale,
            override_justification=stored_justification,
            created_by=actor_id,
            created_at=datetime.now(UTC),
        )
        assignment = self.calendar_repo.add_assignment(assignment)

        # 5b. Resolve any matching gap — a manual assignment fills the slot.
        from sqlalchemy import delete as sql_delete

        self.calendar_repo.session.execute(
            sql_delete(UnresolvedGapModel).where(
                UnresolvedGapModel.calendar_version_id == version_id,
                UnresolvedGapModel.service_date == date,
                UnresolvedGapModel.service_area_id == service_area_id,
            )
        )
        self.calendar_repo.session.flush()

        # 6. Audit.
        if self.audit is not None:
            self.audit.log_assignment_added(actor_id=actor_id, assignment=assignment)

        if self._is_unlocked_approved_version(version):
            self._notify_assignment_added(actor_id=actor_id, assignment=assignment)

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
        self._ensure_week_is_editable(
            version_id=assignment.calendar_version_id,
            service_date=assignment.service_date,
        )

        service_area_name = self._service_area_name(assignment.service_area_id)
        should_notify = self._is_unlocked_approved_version(version)
        self.calendar_repo.delete_assignment(assignment_id)

        if self.audit is not None:
            self.audit.log_assignment_removed(actor_id=actor_id, assignment_id=assignment_id)

        if should_notify and self.triggers is not None:
            self.triggers.on_calendar_assignment_removed_after_approval(
                actor_id=actor_id,
                assignment=assignment,
                service_area_name=service_area_name,
            )

    def replace_assignment(
        self,
        *,
        actor_id: str,
        assignment_id: str,
        new_doctor_id: str,
        override_justification: str | None = None,
        force_warnings: list[str] | None = None,
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
        self._ensure_week_is_editable(
            version_id=assignment.calendar_version_id,
            service_date=assignment.service_date,
        )

        # Load new doctor.
        doctor = self.doctor_repo.get_by_id(new_doctor_id)
        if doctor is None:
            raise CalendarServiceError(
                "doctor_not_found",
                f"Doctor '{new_doctor_id}' not found.",
            )

        # Eligibility checks for the new doctor against the existing slot.
        if force_warnings is not None:
            soft_warnings_raw = self._run_eligibility_with_force(
                doctor=doctor,
                service_area_id=assignment.service_area_id,
                target_date=assignment.service_date,
                force_warnings=force_warnings,
            )
        else:
            soft_warnings_raw = self._run_eligibility(
                doctor=doctor,
                service_area_id=assignment.service_area_id,
                target_date=assignment.service_date,
                override_justification=override_justification,
            )
        soft_warnings_raw = self._apply_monthly_limit(
            version_id=assignment.calendar_version_id,
            doctor=doctor,
            target_date=assignment.service_date,
            force_warnings=force_warnings,
            soft_warnings=soft_warnings_raw,
            exclude_assignment_id=assignment.id,
        )
        soft_warnings_raw = self._apply_scoring_warnings(
            version_id=assignment.calendar_version_id,
            doctor_id=new_doctor_id,
            target_date=assignment.service_date,
            service_area_id=assignment.service_area_id,
            force_warnings=force_warnings,
            override_justification=override_justification,
            soft_warnings=soft_warnings_raw,
            exclude_assignment_id=assignment.id,
        )

        old_doctor_id = assignment.doctor_id
        should_notify = self._is_unlocked_approved_version(version)
        service_area_name = self._service_area_name(assignment.service_area_id)

        # Update the assignment in-place.
        rationale = {
            "overridden_warnings": force_warnings or [],
            "forced_by": actor_id,
        } if force_warnings else _manual_rationale(soft_warnings_raw)

        assignment.doctor_id = new_doctor_id
        assignment.rationale = rationale
        assignment.override_justification = (
            override_justification if override_justification else None
        )
        self.calendar_repo.session.flush()

        if self.audit is not None:
            self.audit.log_assignment_replaced(actor_id=actor_id, assignment=assignment)

        if should_notify and self.triggers is not None and old_doctor_id != new_doctor_id:
            removed_assignment = _assignment_snapshot(assignment, doctor_id=old_doctor_id)
            self.triggers.on_calendar_assignment_removed_after_approval(
                actor_id=actor_id,
                assignment=removed_assignment,
                service_area_name=service_area_name,
            )
            self.triggers.on_calendar_assignment_updated_after_approval(
                actor_id=actor_id,
                assignment=assignment,
                service_area_name=service_area_name,
            )

        return assignment

    def _is_unlocked_approved_version(self, version) -> bool:
        return bool(version and version.reason and version.reason.startswith("__unlock__"))

    def _build_area_metadata(self) -> tuple[dict[str, float], set[str]]:
        """Return (area_weights_by_uuid, strong_area_uuids) from the DB."""
        areas = self.calendar_repo.list_service_areas()
        weights = {a.id: float(a.load_weight) for a in areas}
        strong_codes = {"emergencia", "pista"}
        strong_uuids = {a.id for a in areas if a.code in strong_codes}
        return weights, strong_uuids

    def _service_area_name(self, service_area_id: str) -> str:
        for area in self.calendar_repo.list_service_areas():
            if area.id == service_area_id:
                return area.display_name
        return service_area_id

    def _ensure_week_is_editable(self, *, version_id: str, service_date: date) -> None:
        week = self.calendar_repo.get_week_for_date(version_id, service_date)
        if week is not None and week.status == "approved":
            raise CalendarServiceError(
                "week_locked",
                "No se puede modificar una semana aprobada. Desbloquea la semana primero.",
            )

    def _notify_assignment_added(
        self,
        *,
        actor_id: str,
        assignment: CalendarAssignmentModel,
    ) -> None:
        if self.triggers is None:
            return
        self.triggers.on_calendar_assignment_added_after_approval(
            actor_id=actor_id,
            assignment=assignment,
            service_area_name=self._service_area_name(assignment.service_area_id),
        )


def _manual_rationale(soft_warnings: list) -> dict | None:
    if not soft_warnings:
        return None
    return {
        "manual_override_warnings": [
            {"code": warning.code, "reason": warning.reason}
            for warning in soft_warnings
        ]
    }


def _assignment_snapshot(assignment: CalendarAssignmentModel, *, doctor_id: str):
    class AssignmentSnapshot:
        pass

    snapshot = AssignmentSnapshot()
    snapshot.id = assignment.id
    snapshot.calendar_version_id = assignment.calendar_version_id
    snapshot.doctor_id = doctor_id
    snapshot.service_date = assignment.service_date
    snapshot.service_area_id = assignment.service_area_id
    return snapshot
