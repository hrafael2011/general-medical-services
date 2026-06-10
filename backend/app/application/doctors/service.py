import re
from datetime import UTC, date, datetime
from uuid import uuid4

from backend.app.application.action_alerts.service import ActionAlertService
from backend.app.application.audit.service import AuditService
from backend.app.application.catalogs.service import normalize_name
from backend.app.application.doctors.errors import DoctorServiceError
from backend.app.infrastructure.db.models.doctors import DoctorModel
from backend.app.infrastructure.repositories.catalogs import CatalogRepository
from backend.app.infrastructure.repositories.availability import AvailabilityRepository
from backend.app.infrastructure.repositories.doctors import DoctorRepository
from backend.app.infrastructure.repositories.missions import MissionRepository


def _strip_html(value: str | None) -> str | None:
    """Remove HTML/JS tags from free-text fields to prevent stored XSS."""
    if value is None:
        return None
    return re.sub(r"<[^>]*>", "", value).strip()


_MISSING = object()
MAX_DOCTOR_NAME_LENGTH = 160


def _clean_name_part(value: str | None) -> str | None:
    cleaned = _strip_html(value)
    return cleaned or None


def _join_name_parts(first_name: str | None, last_name: str | None) -> str:
    return " ".join(part for part in (first_name, last_name) if part).strip()


def _validate_doctor_name_length(doctor_name: str) -> None:
    if len(doctor_name) > MAX_DOCTOR_NAME_LENGTH:
        raise DoctorServiceError(
            "doctor_name_too_long",
            "El nombre completo del médico no puede superar 160 caracteres.",
        )


class DoctorService:
    def __init__(
        self,
        doctors: DoctorRepository,
        catalog_repo: CatalogRepository | None = None,
        audit: AuditService | None = None,
        mission_repo: MissionRepository | None = None,
        action_alerts: ActionAlertService | None = None,
    ) -> None:
        self.doctors = doctors
        self.catalog_repo = catalog_repo
        self.audit = audit
        self.mission_repo = mission_repo
        self.action_alerts = action_alerts
        self._last_cleanup_info: dict = {}

    def create_doctor(
        self,
        *,
        actor_id: str,
        sex: str,
        name: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        rank_id: str | None = None,
        department_id: str | None = None,
        notes: str | None = None,
        participa_misiones: bool = True,
        service_active: bool = True,
        whatsapp_phone: str | None = None,
        monthly_service_target: int = 3,
        monthly_service_max: int = 3,
        monthly_service_limit_mode: str = "warn_only",
        availability_mode: str = "monthly",
        allowed_area_ids: list[str] | None = None,
    ) -> DoctorModel:
        if monthly_service_target is not None and monthly_service_max is not None:
            if monthly_service_target > monthly_service_max:
                raise DoctorServiceError(
                    "invalid_service_limits",
                    "El objetivo mensual de servicios no puede superar el máximo mensual.",
                )

        cleaned_first_name = _clean_name_part(first_name)
        cleaned_last_name = _clean_name_part(last_name)
        doctor_name = _join_name_parts(cleaned_first_name, cleaned_last_name)
        if not doctor_name and name is not None:
            doctor_name = _clean_name_part(name) or ""
        if not doctor_name:
            raise DoctorServiceError("missing_doctor_name", "Debe indicar nombre y apellido.")
        _validate_doctor_name_length(doctor_name)
        computed_normalized = normalize_name(doctor_name)

        # Check for duplicate normalized_name
        existing = self.doctors.get_by_normalized_name(computed_normalized)
        if existing is not None:
            raise DoctorServiceError(
                "duplicate_doctor_name",
                f"Ya existe un médico con el nombre «{existing.name}».",
            )

        now = datetime.now(UTC)
        doctor = DoctorModel(
            id=str(uuid4()),
            first_name=cleaned_first_name,
            last_name=cleaned_last_name,
            name=doctor_name,
            normalized_name=computed_normalized,
            sex=sex,
            rank_id=rank_id,
            department_id=department_id,
            notes=_strip_html(notes),
            active=True,
            service_active=service_active,
            service_inactive_reason_id=None,
            service_inactive_detail=None,
            participa_misiones=participa_misiones,
            whatsapp_phone=whatsapp_phone,
            monthly_service_target=monthly_service_target,
            monthly_service_max=monthly_service_max,
            monthly_service_limit_mode=monthly_service_limit_mode,
            availability_mode=availability_mode,
            created_by=actor_id,
            created_at=now,
            updated_at=now,
        )
        doctor = self.doctors.add(doctor)
        if allowed_area_ids:
            self.doctors.set_allowed_areas(doctor.id, allowed_area_ids)
        if self.audit is not None:
            self.audit.log_doctor_created(actor_id=actor_id, doctor=doctor)
        return doctor

    def update_doctor(
        self,
        doctor_id: str,
        *,
        actor_id: str,
        name: str | None = None,
        first_name: str | None | object = _MISSING,
        last_name: str | None | object = _MISSING,
        sex: str | None = None,
        rank_id: str | None | object = _MISSING,
        department_id: str | None | object = _MISSING,
        notes: str | None | object = _MISSING,
        participa_misiones: bool | None = None,
        service_active: bool | None = None,
        whatsapp_phone: str | None | object = _MISSING,
        monthly_service_target: int | None = None,
        monthly_service_max: int | None = None,
        monthly_service_limit_mode: str | None = None,
        availability_mode: str | None = None,
        allowed_area_ids: list[str] | None = None,
    ) -> DoctorModel:
        doctor = self.doctors.get_by_id(doctor_id)
        if doctor is None:
            raise DoctorServiceError("doctor_not_found", f"Médico con id {doctor_id} no encontrado.")

        if monthly_service_target is not None and monthly_service_max is not None:
            if monthly_service_target > monthly_service_max:
                raise DoctorServiceError(
                    "invalid_service_limits",
                    "El objetivo mensual de servicios no puede superar el máximo mensual.",
                )

        # Also check against the existing value when only one side is provided
        if monthly_service_target is not None and monthly_service_max is None:
            effective_max = doctor.monthly_service_max
            if effective_max is not None and monthly_service_target > effective_max:
                raise DoctorServiceError(
                    "invalid_service_limits",
                    "El objetivo mensual de servicios no puede superar el máximo mensual.",
                )
        if monthly_service_max is not None and monthly_service_target is None:
            effective_target = doctor.monthly_service_target
            if effective_target is not None and effective_target > monthly_service_max:
                raise DoctorServiceError(
                    "invalid_service_limits",
                    "El objetivo mensual de servicios no puede superar el máximo mensual.",
                )

        changed_fields: dict = {}
        if first_name is not _MISSING or last_name is not _MISSING:
            cleaned_first_name = (
                _clean_name_part(first_name)
                if first_name is not _MISSING
                else doctor.first_name
            )
            cleaned_last_name = (
                _clean_name_part(last_name)
                if last_name is not _MISSING
                else doctor.last_name
            )
            doctor_name = _join_name_parts(cleaned_first_name, cleaned_last_name)
            if not doctor_name:
                raise DoctorServiceError("missing_doctor_name", "Debe indicar nombre y apellido.")
            _validate_doctor_name_length(doctor_name)
            computed_normalized = normalize_name(doctor_name)

            # Check for duplicate normalized_name (exclude current doctor)
            existing = self.doctors.get_by_normalized_name(computed_normalized)
            if existing is not None and existing.id != doctor_id:
                raise DoctorServiceError(
                    "duplicate_doctor_name",
                    f"Ya existe un médico con el nombre «{existing.name}».",
                )

            doctor.first_name = cleaned_first_name
            doctor.last_name = cleaned_last_name
            doctor.name = doctor_name
            doctor.normalized_name = computed_normalized
            changed_fields["first_name"] = cleaned_first_name
            changed_fields["last_name"] = cleaned_last_name
            changed_fields["name"] = doctor_name
        elif name is not None:
            doctor_name = _clean_name_part(name) or ""
            if not doctor_name:
                raise DoctorServiceError("missing_doctor_name", "Debe indicar nombre y apellido.")
            _validate_doctor_name_length(doctor_name)
            computed_normalized = normalize_name(doctor_name)

            # Check for duplicate normalized_name (exclude current doctor)
            existing = self.doctors.get_by_normalized_name(computed_normalized)
            if existing is not None and existing.id != doctor_id:
                raise DoctorServiceError(
                    "duplicate_doctor_name",
                    f"Ya existe un médico con el nombre «{existing.name}».",
                )

            doctor.name = doctor_name
            doctor.normalized_name = computed_normalized
            changed_fields["name"] = doctor_name
        if sex is not None:
            doctor.sex = sex
            changed_fields["sex"] = sex
        if rank_id is not _MISSING:
            doctor.rank_id = rank_id
            changed_fields["rank_id"] = rank_id
        if department_id is not _MISSING:
            doctor.department_id = department_id
            changed_fields["department_id"] = department_id
        if notes is not _MISSING:
            doctor.notes = _strip_html(notes)
            changed_fields["notes"] = doctor.notes
        if participa_misiones is not None:
            doctor.participa_misiones = participa_misiones
            changed_fields["participa_misiones"] = participa_misiones
        if whatsapp_phone is not _MISSING:
            doctor.whatsapp_phone = _strip_html(whatsapp_phone)
            changed_fields["whatsapp_phone"] = doctor.whatsapp_phone
        if monthly_service_target is not None:
            doctor.monthly_service_target = monthly_service_target
            changed_fields["monthly_service_target"] = monthly_service_target
        if monthly_service_max is not None:
            doctor.monthly_service_max = monthly_service_max
            changed_fields["monthly_service_max"] = monthly_service_max
        if monthly_service_limit_mode is not None:
            doctor.monthly_service_limit_mode = monthly_service_limit_mode
            changed_fields["monthly_service_limit_mode"] = monthly_service_limit_mode
        if availability_mode is not None:
            old_availability_mode = doctor.availability_mode
            doctor.availability_mode = availability_mode
            changed_fields["availability_mode"] = availability_mode
            if old_availability_mode != availability_mode:
                removed = self._cleanup_calendar_assignments(doctor_id)
                if removed > 0:
                    import logging
                    _logger = logging.getLogger(__name__)
                    _logger.info(
                        "Cleaned up %d calendar assignments for doctor %s "
                        "due to availability_mode change (%s → %s)",
                        removed, doctor_id, old_availability_mode, availability_mode,
                    )

        if service_active is not None:
            doctor.service_active = service_active
            changed_fields["service_active"] = service_active
            if not service_active:
                AvailabilityRepository(self.doctors.session).delete_all_for_doctor(doctor_id)
                self.doctors.set_allowed_areas(doctor_id, [])
                changed_fields["allowed_area_ids"] = []
                removed = self._cleanup_calendar_assignments(doctor_id)
                if removed > 0:
                    import logging
                    _logger = logging.getLogger(__name__)
                    _logger.info(
                        "Cleaned up %d calendar assignments for deactivated doctor %s",
                        removed, doctor_id,
                    )

        doctor.updated_at = datetime.now(UTC)
        self.doctors.session.flush()
        if allowed_area_ids is not None:
            self.doctors.set_allowed_areas(doctor_id, allowed_area_ids)
            changed_fields["allowed_area_ids"] = allowed_area_ids

        if self.audit is not None and changed_fields:
            self.audit.log_doctor_updated(actor_id=actor_id, doctor=doctor, changed_fields=changed_fields)

        return doctor

    def _cleanup_calendar_assignments(self, doctor_id: str) -> int:
        """Remove all assignments for a doctor in draft/partial calendars.

        Returns the count of removed assignments.
        Stores result in self._last_cleanup_info for the route layer to read.
        """
        from backend.app.infrastructure.repositories.calendars import CalendarRepository

        repo = CalendarRepository(self.doctors.session)
        count, calendar_ids = repo.delete_assignments_for_doctor_in_active_calendars(doctor_id)
        if count > 0:
            self._last_cleanup_info = {
                "removed_assignments": count,
                "affected_calendar_ids": calendar_ids,
            }
        return count

    WEEKDAY_LABELS = {
        0: "Lunes", 1: "Martes", 2: "Miércoles",
        3: "Jueves", 4: "Viernes", 5: "Sábado", 6: "Domingo",
    }
    WEEK_NUMBER_LABELS = {
        0: "primer", 1: "segundo", 2: "tercer", 3: "cuarto", -1: "último",
    }

    def _make_recurring_tag(self, weekday: int, week_number: int) -> str:
        week_label = self.WEEK_NUMBER_LABELS.get(week_number, "")
        day_label = self.WEEKDAY_LABELS.get(weekday, "")
        return f"{week_label} {day_label}"

    def list_by_day(self) -> dict:
        active_doctors = self.doctors.list_all(active_only=True)
        doctor_ids = [d.id for d in active_doctors]
        avail_by_doctor = self.doctors.load_availability_bulk(doctor_ids)

        # Load rank/department names via catalog repo (DoctorModel has no relationships)
        ranks = {r.id: r.name for r in self.catalog_repo.list_ranks()} if self.catalog_repo else {}
        depts = {d.id: d.name for d in self.catalog_repo.list_departments()} if self.catalog_repo else {}

        days: dict[int, dict] = {
            i: {"label": self.WEEKDAY_LABELS[i], "count": 0, "doctors": []}
            for i in range(7)
        }

        for doctor in active_doctors:
            doctor_days_seen: set[int] = set()
            for record in avail_by_doctor.get(doctor.id, []):
                if record.availability_type == "weekly_fixed" and record.days_of_week:
                    for dow in record.days_of_week:
                        if 0 <= dow <= 6 and dow not in doctor_days_seen:
                            doctor_days_seen.add(dow)
                            days[dow]["doctors"].append({
                                "id": doctor.id,
                                "name": doctor.name,
                                "rank_name": ranks.get(doctor.rank_id),
                                "department_name": depts.get(doctor.department_id),
                                "whatsapp_phone": doctor.whatsapp_phone,
                                "recurring_tag": None,
                            })
                            days[dow]["count"] = len(days[dow]["doctors"])

                elif record.availability_type == "recurring" and record.weekday is not None:
                    dow = record.weekday
                    tag = self._make_recurring_tag(record.weekday, record.week_number)
                    if 0 <= dow <= 6:
                        if dow in doctor_days_seen:
                            for item in days[dow]["doctors"]:
                                if item["id"] == doctor.id:
                                    item["recurring_tag"] = tag
                                    break
                            days[dow]["count"] = len(days[dow]["doctors"])
                            continue
                        doctor_days_seen.add(dow)
                        days[dow]["doctors"].append({
                            "id": doctor.id,
                            "name": doctor.name,
                            "rank_name": ranks.get(doctor.rank_id),
                            "department_name": depts.get(doctor.department_id),
                            "whatsapp_phone": doctor.whatsapp_phone,
                            "recurring_tag": tag,
                        })
                        days[dow]["count"] = len(days[dow]["doctors"])

        return {str(i): days[i] for i in range(7)}

    def list_by_area(self) -> dict:
        active_doctors = self.doctors.list_all(active_only=True)
        doctor_ids = [d.id for d in active_doctors]

        # Bulk-load allowed areas: doctor_id -> [area_id, ...]
        areas_by_doctor = self.doctors.get_allowed_areas_bulk(doctor_ids)

        # Load all active service areas
        all_areas = self.catalog_repo.list_service_areas() if self.catalog_repo else []
        active_areas = [a for a in all_areas if a.active]

        # Load rank/department names
        ranks = {r.id: r.name for r in self.catalog_repo.list_ranks()} if self.catalog_repo else {}
        depts = {d.id: d.name for d in self.catalog_repo.list_departments()} if self.catalog_repo else {}

        # Initialize result: one entry per active area
        areas: dict[str, dict] = {
            a.id: {
                "area_id": a.id,
                "code": a.code,
                "label": a.display_name,
                "count": 0,
                "doctors": [],
            }
            for a in active_areas
        }

        for doctor in active_doctors:
            doc_area_ids = areas_by_doctor.get(doctor.id, [])
            for area_id in doc_area_ids:
                if area_id not in areas:
                    continue  # skip areas that are inactive or unknown
                areas[area_id]["doctors"].append({
                    "id": doctor.id,
                    "name": doctor.name,
                    "rank_name": ranks.get(doctor.rank_id),
                    "department_name": depts.get(doctor.department_id),
                })
                areas[area_id]["count"] = len(areas[area_id]["doctors"])

        return {"areas": areas}

    def list_by_department(self) -> dict:
        active_doctors = self.doctors.list_all(active_only=True)

        # Load all active departments
        all_departments = self.catalog_repo.list_departments() if self.catalog_repo else []
        active_departments = [d for d in all_departments if d.active]

        # Load rank names for display
        ranks = {r.id: r.name for r in self.catalog_repo.list_ranks()} if self.catalog_repo else {}

        # Initialize result: one entry per active department
        departments: dict[str, dict] = {
            d.id: {
                "department_id": d.id,
                "label": d.name,
                "count": 0,
                "doctors": [],
            }
            for d in active_departments
        }

        for doctor in active_doctors:
            dept_id = doctor.department_id
            if not dept_id or dept_id not in departments:
                continue  # skip doctors with no department or an inactive/unknown department
            departments[dept_id]["doctors"].append({
                "id": doctor.id,
                "name": doctor.name,
                "rank_name": ranks.get(doctor.rank_id),
                "department_name": departments[dept_id]["label"],
            })
            departments[dept_id]["count"] = len(departments[dept_id]["doctors"])

        return {"departments": departments}

    def deactivate_service(
        self,
        doctor_id: str,
        *,
        actor_id: str,
        reason_id: str,
        detail: str | None = None,
    ) -> DoctorModel:
        doctor = self.doctors.get_by_id(doctor_id)
        if doctor is None:
            raise DoctorServiceError("doctor_not_found", f"Médico con id {doctor_id} no encontrado.")

        if self.catalog_repo is not None:
            reason = self.catalog_repo.get_deactivation_reason_by_id(reason_id)
            if reason is not None and reason.applies_to_sex is not None:
                if doctor.sex != reason.applies_to_sex:
                    raise DoctorServiceError(
                        "reason_sex_mismatch",
                        "Este motivo de desactivación no aplica al sexo del médico.",
                    )

        doctor.service_active = False
        doctor.service_inactive_reason_id = reason_id
        doctor.service_inactive_detail = _strip_html(detail)
        doctor.participa_misiones = False
        doctor.updated_at = datetime.now(UTC)
        self.doctors.session.flush()

        if self.audit is not None:
            self.audit.log_doctor_service_deactivated(actor_id=actor_id, doctor=doctor)

        self._create_mission_replacement_alerts_for_deactivated_doctor(doctor, actor_id=actor_id)

        return doctor

    def reactivate_service(self, doctor_id: str, *, actor_id: str) -> DoctorModel:
        doctor = self.doctors.get_by_id(doctor_id)
        if doctor is None:
            raise DoctorServiceError("doctor_not_found", f"Médico con id {doctor_id} no encontrado.")

        doctor.service_active = True
        doctor.service_inactive_reason_id = None
        doctor.service_inactive_detail = None
        doctor.participa_misiones = True
        doctor.updated_at = datetime.now(UTC)
        self.doctors.session.flush()

        if self.audit is not None:
            self.audit.log_doctor_service_reactivated(actor_id=actor_id, doctor=doctor)

        return doctor

    def soft_delete_doctor(self, doctor_id: str, *, actor_id: str) -> None:
        doctor = self.doctors.get_by_id(doctor_id)
        if doctor is None:
            raise DoctorServiceError("doctor_not_found", f"Médico con id {doctor_id} no encontrado.")
        self.doctors.soft_delete(doctor_id)
        if self.audit is not None:
            self.audit.log_doctor_deleted(actor_id=actor_id, doctor=doctor)

    def _create_mission_replacement_alerts_for_deactivated_doctor(
        self,
        doctor: DoctorModel,
        *,
        actor_id: str,
    ) -> None:
        if self.mission_repo is None or self.action_alerts is None:
            return

        participations = self.mission_repo.list_future_confirmed_participations_for_doctor(
            doctor.id,
            from_date=date.today(),
        )
        for mission, participant in participations:
            location = f" en {mission.location}" if mission.location else ""
            self.action_alerts.create_if_missing(
                alert_type="mission_replacement_required",
                section="missions",
                severity="critical",
                title="Reemplazo requerido en misión",
                message=(
                    f"{doctor.name} fue desactivado para servicios y está asignado a la "
                    f"misión del {mission.mission_date}{location}. Debe reemplazarse."
                ),
                entity_type="mission_participant",
                entity_id=participant.id,
                action_url="/missions",
                alert_metadata={
                    "doctor_id": doctor.id,
                    "doctor_name": doctor.name,
                    "mission_id": mission.id,
                    "mission_date": str(mission.mission_date),
                    "reason_id": doctor.service_inactive_reason_id,
                    "reason_detail": doctor.service_inactive_detail,
                },
                created_by=actor_id,
            )
