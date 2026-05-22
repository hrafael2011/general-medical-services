import re
from datetime import UTC, date, datetime
from uuid import uuid4

from backend.app.application.action_alerts.service import ActionAlertService
from backend.app.application.audit.service import AuditService
from backend.app.application.catalogs.service import normalize_name
from backend.app.application.doctors.errors import DoctorServiceError
from backend.app.infrastructure.db.models.doctors import DoctorModel
from backend.app.infrastructure.repositories.catalogs import CatalogRepository
from backend.app.infrastructure.repositories.doctors import DoctorRepository
from backend.app.infrastructure.repositories.missions import MissionRepository


def _strip_html(value: str | None) -> str | None:
    """Remove HTML/JS tags from free-text fields to prevent stored XSS."""
    if value is None:
        return None
    return re.sub(r"<[^>]*>", "", value).strip()


_MISSING = object()


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

    def create_doctor(
        self,
        *,
        actor_id: str,
        name: str,
        sex: str,
        rank_id: str | None = None,
        department_id: str | None = None,
        phone: str | None = None,
        notes: str | None = None,
        participa_misiones: bool = True,
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
                    "monthly_service_target cannot exceed monthly_service_max.",
                )

        raw_name = name.strip()
        doctor_name = _strip_html(raw_name)
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
            name=doctor_name,
            normalized_name=computed_normalized,
            sex=sex,
            rank_id=rank_id,
            department_id=department_id,
            phone=_strip_html(phone),
            notes=_strip_html(notes),
            active=True,
            service_active=True,
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
        sex: str | None = None,
        rank_id: str | None | object = _MISSING,
        department_id: str | None | object = _MISSING,
        phone: str | None | object = _MISSING,
        notes: str | None | object = _MISSING,
        participa_misiones: bool | None = None,
        whatsapp_phone: str | None | object = _MISSING,
        monthly_service_target: int | None = None,
        monthly_service_max: int | None = None,
        monthly_service_limit_mode: str | None = None,
        availability_mode: str | None = None,
        allowed_area_ids: list[str] | None = None,
    ) -> DoctorModel:
        doctor = self.doctors.get_by_id(doctor_id)
        if doctor is None:
            raise DoctorServiceError("doctor_not_found", f"Doctor with id {doctor_id} not found")

        if monthly_service_target is not None and monthly_service_max is not None:
            if monthly_service_target > monthly_service_max:
                raise DoctorServiceError(
                    "invalid_service_limits",
                    "monthly_service_target cannot exceed monthly_service_max.",
                )

        # Also check against the existing value when only one side is provided
        if monthly_service_target is not None and monthly_service_max is None:
            effective_max = doctor.monthly_service_max
            if effective_max is not None and monthly_service_target > effective_max:
                raise DoctorServiceError(
                    "invalid_service_limits",
                    "monthly_service_target cannot exceed monthly_service_max.",
                )
        if monthly_service_max is not None and monthly_service_target is None:
            effective_target = doctor.monthly_service_target
            if effective_target is not None and effective_target > monthly_service_max:
                raise DoctorServiceError(
                    "invalid_service_limits",
                    "monthly_service_target cannot exceed monthly_service_max.",
                )

        changed_fields: dict = {}
        if name is not None:
            raw_name = name.strip()
            doctor_name = _strip_html(raw_name)
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
        if phone is not _MISSING:
            doctor.phone = _strip_html(phone)
            changed_fields["phone"] = doctor.phone
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
            doctor.availability_mode = availability_mode
            changed_fields["availability_mode"] = availability_mode

        doctor.updated_at = datetime.now(UTC)
        self.doctors.session.flush()
        if allowed_area_ids is not None:
            self.doctors.set_allowed_areas(doctor_id, allowed_area_ids)
            changed_fields["allowed_area_ids"] = allowed_area_ids

        if self.audit is not None and changed_fields:
            self.audit.log_doctor_updated(actor_id=actor_id, doctor=doctor, changed_fields=changed_fields)

        return doctor

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
            for record in avail_by_doctor.get(doctor.id, []):
                if record.availability_type == "weekly_fixed" and record.days_of_week:
                    for dow in record.days_of_week:
                        if 0 <= dow <= 6:
                            days[dow]["doctors"].append({
                                "id": doctor.id,
                                "name": doctor.name,
                                "rank_name": ranks.get(doctor.rank_id),
                                "department_name": depts.get(doctor.department_id),
                                "phone": doctor.phone,
                                "recurring_tag": None,
                            })
                            days[dow]["count"] = len(days[dow]["doctors"])

                elif record.availability_type == "recurring" and record.weekday is not None:
                    dow = record.weekday
                    tag = self._make_recurring_tag(record.weekday, record.week_number)
                    if 0 <= dow <= 6:
                        days[dow]["doctors"].append({
                            "id": doctor.id,
                            "name": doctor.name,
                            "rank_name": ranks.get(doctor.rank_id),
                            "department_name": depts.get(doctor.department_id),
                            "phone": doctor.phone,
                            "recurring_tag": tag,
                        })
                        days[dow]["count"] = len(days[dow]["doctors"])

        return {str(i): days[i] for i in range(7)}

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
            raise DoctorServiceError("doctor_not_found", f"Doctor with id {doctor_id} not found")

        if self.catalog_repo is not None:
            reason = self.catalog_repo.get_deactivation_reason_by_id(reason_id)
            if reason is not None and reason.applies_to_sex is not None:
                if doctor.sex != reason.applies_to_sex:
                    raise DoctorServiceError(
                        "reason_sex_mismatch",
                        "This deactivation reason does not apply to this doctor's sex.",
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
            raise DoctorServiceError("doctor_not_found", f"Doctor with id {doctor_id} not found")

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
            raise DoctorServiceError("doctor_not_found", f"Doctor with id {doctor_id} not found")
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
