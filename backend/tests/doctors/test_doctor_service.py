from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest

from backend.app.application.action_alerts.service import ActionAlertService
from backend.app.application.doctors.service import DoctorService
from backend.app.application.catalogs.service import CatalogService
from backend.app.infrastructure.db.models.doctors import DoctorModel
from backend.app.infrastructure.db.models.missions import (
    MissionAssignmentModel,
    MissionParticipantModel,
)
from backend.app.infrastructure.repositories.action_alerts import ActionAlertRepository
from backend.app.infrastructure.repositories.catalogs import CatalogRepository
from backend.app.application.doctors.errors import DoctorServiceError
from backend.app.infrastructure.repositories.doctors import DoctorRepository
from backend.app.infrastructure.repositories.missions import MissionRepository


def _make_service(db_session) -> DoctorService:
    return DoctorService(DoctorRepository(db_session))


def _make_alerting_service(db_session) -> DoctorService:
    return DoctorService(
        DoctorRepository(db_session),
        mission_repo=MissionRepository(db_session),
        action_alerts=ActionAlertService(ActionAlertRepository(db_session)),
    )


def _create_confirmed_mission_with_participant(db_session, doctor_id: str):
    now = datetime.now(UTC)
    mission = MissionAssignmentModel(
        id=str(uuid4()),
        mission_date=date.today() + timedelta(days=3),
        mission_start_at=None,
        mission_end_at=None,
        participant_count=1,
        location="Base Norte",
        description=None,
        source="manual",
        status="confirmed",
        created_by="actor",
        confirmed_by="actor",
        confirmed_at=now,
        created_at=now,
        updated_at=now,
        deleted_at=None,
    )
    db_session.add(mission)
    db_session.flush()
    participant = MissionParticipantModel(
        id=str(uuid4()),
        mission_assignment_id=mission.id,
        doctor_id=doctor_id,
        selection_source="manual",
        ranking_position=None,
        score=None,
        reasons=None,
        warnings=None,
        created_at=now,
    )
    db_session.add(participant)
    db_session.flush()
    return mission, participant


def test_create_doctor_stores_basic_fields(db_session) -> None:
    service = _make_service(db_session)

    doctor = service.create_doctor(
        actor_id="actor-001",
        name="  Juan Pérez  ",
        sex="male",
        rank_id=None,
        department_id=None,
        notes=None,
        participa_misiones=True,
        whatsapp_phone="+18095551234",
        monthly_service_target=3,
        monthly_service_max=3,
        monthly_service_limit_mode="warn_only",
        availability_mode="monthly",
        allowed_area_ids=[],
    )

    assert doctor.name == "Juan Pérez"
    assert doctor.sex == "male"
    assert doctor.active is True
    assert doctor.service_active is True
    assert doctor.participa_misiones is True
    assert doctor.created_by == "actor-001"


def test_create_doctor_from_first_and_last_name(db_session) -> None:
    service = _make_service(db_session)

    doctor = service.create_doctor(
        actor_id="actor-001",
        first_name="  Juan Carlos  ",
        last_name="  Pérez Gómez  ",
        sex="male",
        rank_id=None,
        department_id=None,
        notes=None,
        participa_misiones=True,
        whatsapp_phone="+18095551234",
        monthly_service_target=3,
        monthly_service_max=3,
        monthly_service_limit_mode="warn_only",
        availability_mode="monthly",
        allowed_area_ids=[],
    )

    assert doctor.first_name == "Juan Carlos"
    assert doctor.last_name == "Pérez Gómez"
    assert doctor.name == "Juan Carlos Pérez Gómez"
    assert doctor.normalized_name == "juan carlos pérez gómez"


def test_create_doctor_rejects_combined_name_over_column_limit(db_session) -> None:
    service = _make_service(db_session)

    with pytest.raises(DoctorServiceError, match="160 caracteres"):
        service.create_doctor(
            actor_id="actor-001",
            first_name="A" * 100,
            last_name="B" * 100,
            sex="male",
            whatsapp_phone="+18095551234",
        )


def test_create_doctor_trims_name(db_session) -> None:
    service = _make_service(db_session)

    doctor = service.create_doctor(
        actor_id="actor-001",
        name="  Ana García  ",
        sex="female",
        rank_id=None,
        department_id=None,
        notes=None,
        participa_misiones=False,
        whatsapp_phone="+18095551234",
        monthly_service_target=2,
        monthly_service_max=2,
        monthly_service_limit_mode="warn_only",
        availability_mode="fixed",
        allowed_area_ids=[],
    )

    assert doctor.name == "Ana García"
    assert doctor.participa_misiones is False


def test_list_all_returns_doctors(db_session) -> None:
    service = _make_service(db_session)
    repo = DoctorRepository(db_session)

    service.create_doctor(
        actor_id="a", name="Doctor A", sex="male", rank_id=None, department_id=None,
        notes=None, participa_misiones=True, whatsapp_phone="+18095551234",
        monthly_service_target=3, monthly_service_max=3,
        monthly_service_limit_mode="warn_only", availability_mode="monthly",
        allowed_area_ids=[],
    )
    service.create_doctor(
        actor_id="a", name="Doctor B", sex="female", rank_id=None, department_id=None,
        notes=None, participa_misiones=True, whatsapp_phone="+18095551234",
        monthly_service_target=3, monthly_service_max=3,
        monthly_service_limit_mode="warn_only", availability_mode="monthly",
        allowed_area_ids=[],
    )

    all_doctors = repo.list_all()
    assert len(all_doctors) == 2


def test_update_doctor_changes_fields(db_session) -> None:
    service = _make_service(db_session)

    doctor = service.create_doctor(
        actor_id="a", name="Original Name", sex="male", rank_id=None, department_id=None,
        notes=None, participa_misiones=True, whatsapp_phone="+18095551234",
        monthly_service_target=3, monthly_service_max=3,
        monthly_service_limit_mode="warn_only", availability_mode="monthly",
        allowed_area_ids=[],
    )

    updated = service.update_doctor(
        doctor.id,
        actor_id="a",
        name="Updated Name",
        sex=None,
        rank_id=None,
        department_id=None,
        whatsapp_phone="555-1234",
        notes=None,
        participa_misiones=None,
        monthly_service_target=None,
        monthly_service_max=None,
        monthly_service_limit_mode=None,
        availability_mode=None,
        allowed_area_ids=None,
    )

    assert updated.name == "Updated Name"
    assert updated.whatsapp_phone == "555-1234"


def test_update_doctor_from_first_and_last_name(db_session) -> None:
    service = _make_service(db_session)

    doctor = service.create_doctor(
        actor_id="a", name="Original Name", sex="male", rank_id=None, department_id=None,
        notes=None, participa_misiones=True, whatsapp_phone="+18095551234",
        monthly_service_target=3, monthly_service_max=3,
        monthly_service_limit_mode="warn_only", availability_mode="monthly",
        allowed_area_ids=[],
    )

    updated = service.update_doctor(
        doctor.id,
        actor_id="a",
        first_name=" Ana ",
        last_name=" García ",
    )

    assert updated.first_name == "Ana"
    assert updated.last_name == "García"
    assert updated.name == "Ana García"
    assert updated.normalized_name == "ana garcía"


def test_update_doctor_can_clear_nullable_fields(db_session) -> None:
    catalog_service = CatalogService(CatalogRepository(db_session))
    department = catalog_service.create_department("Recursos Humanos")
    service = _make_service(db_session)

    doctor = service.create_doctor(
        actor_id="a", name="Doctor Clear", sex="male", rank_id=None, department_id=department.id,
        notes="Nota", participa_misiones=True, whatsapp_phone="555-1111",
        monthly_service_target=3, monthly_service_max=3,
        monthly_service_limit_mode="warn_only", availability_mode="monthly",
        allowed_area_ids=[],
    )

    updated = service.update_doctor(
        doctor.id,
        actor_id="a",
        department_id=None,
        notes=None,
    )

    assert updated.department_id is None
    assert updated.notes is None
    assert updated.whatsapp_phone == "555-1111"


def test_update_doctor_omitted_nullable_fields_are_not_changed(db_session) -> None:
    catalog_service = CatalogService(CatalogRepository(db_session))
    department = catalog_service.create_department("Evaluaciones Médicas")
    service = _make_service(db_session)

    doctor = service.create_doctor(
        actor_id="a", name="Doctor Keep", sex="female", rank_id=None, department_id=department.id,
        notes="Conservar", participa_misiones=True, whatsapp_phone="555-3333",
        monthly_service_target=3, monthly_service_max=3,
        monthly_service_limit_mode="warn_only", availability_mode="monthly",
        allowed_area_ids=[],
    )

    updated = service.update_doctor(doctor.id, actor_id="a", name="Doctor Keep Updated")

    assert updated.department_id == department.id
    assert updated.notes == "Conservar"
    assert updated.whatsapp_phone == "555-3333"


def test_deactivate_and_reactivate_service(db_session) -> None:
    service = _make_service(db_session)

    doctor = service.create_doctor(
        actor_id="a", name="Dr. Test", sex="male", rank_id=None, department_id=None,
        notes=None, participa_misiones=True, whatsapp_phone="+18095551234",
        monthly_service_target=3, monthly_service_max=3,
        monthly_service_limit_mode="warn_only", availability_mode="monthly",
        allowed_area_ids=[],
    )
    assert doctor.service_active is True

    service.deactivate_service(doctor.id, actor_id="a", reason_id="reason-001", detail="En licencia")
    assert doctor.service_active is False
    assert doctor.service_inactive_reason_id == "reason-001"
    assert doctor.service_inactive_detail == "En licencia"
    assert doctor.participa_misiones is False

    service.reactivate_service(doctor.id, actor_id="a")
    assert doctor.service_active is True
    assert doctor.service_inactive_reason_id is None
    assert doctor.participa_misiones is True


def test_service_active_filter(db_session) -> None:
    service = _make_service(db_session)
    repo = DoctorRepository(db_session)

    d1 = service.create_doctor(
        actor_id="a", name="Active Doc", sex="male", rank_id=None, department_id=None,
        notes=None, participa_misiones=True, whatsapp_phone="+18095551234",
        monthly_service_target=3, monthly_service_max=3,
        monthly_service_limit_mode="warn_only", availability_mode="monthly",
        allowed_area_ids=[],
    )
    service.create_doctor(
        actor_id="a", name="Inactive Doc", sex="female", rank_id=None, department_id=None,
        notes=None, participa_misiones=True, whatsapp_phone="+18095551234",
        monthly_service_target=3, monthly_service_max=3,
        monthly_service_limit_mode="warn_only", availability_mode="monthly",
        allowed_area_ids=[],
    )
    service.deactivate_service(d1.id, actor_id="a", reason_id="r1", detail=None)

    active_docs = repo.list_service_active()
    names = [d.name for d in active_docs]
    assert "Active Doc" not in names
    assert "Inactive Doc" in names


def test_list_all_active_only_filters_service_active_doctors(db_session) -> None:
    service = _make_service(db_session)
    repo = DoctorRepository(db_session)

    d1 = service.create_doctor(
        actor_id="a", name="Service Inactive Doc", sex="male", rank_id=None, department_id=None,
        notes=None, participa_misiones=True, whatsapp_phone="+18095551234",
        monthly_service_target=3, monthly_service_max=3,
        monthly_service_limit_mode="warn_only", availability_mode="monthly",
        allowed_area_ids=[],
    )
    service.create_doctor(
        actor_id="a", name="Service Active Doc", sex="female", rank_id=None, department_id=None,
        notes=None, participa_misiones=True, whatsapp_phone="+18095551234",
        monthly_service_target=3, monthly_service_max=3,
        monthly_service_limit_mode="warn_only", availability_mode="monthly",
        allowed_area_ids=[],
    )
    service.deactivate_service(d1.id, actor_id="a", reason_id="r1", detail=None)

    all_names = [doctor.name for doctor in repo.list_all(active_only=False)]
    active_names = [doctor.name for doctor in repo.list_all(active_only=True)]

    assert "Service Inactive Doc" in all_names
    assert "Service Active Doc" in all_names
    assert "Service Inactive Doc" not in active_names
    assert "Service Active Doc" in active_names


def test_deactivate_service_creates_alert_for_future_confirmed_mission(db_session) -> None:
    service = _make_alerting_service(db_session)
    alerts = ActionAlertRepository(db_session)

    doctor = service.create_doctor(
        actor_id="a", name="Doctor Mission", sex="male", rank_id=None, department_id=None,
        notes=None, participa_misiones=True, whatsapp_phone="+18095551234",
        monthly_service_target=3, monthly_service_max=3,
        monthly_service_limit_mode="warn_only", availability_mode="monthly",
        allowed_area_ids=[],
    )
    mission, participant = _create_confirmed_mission_with_participant(db_session, doctor.id)

    service.deactivate_service(doctor.id, actor_id="a", reason_id="r1", detail="Licencia")

    open_alerts = alerts.list_all(status="open", section="missions")
    assert len(open_alerts) == 1
    assert open_alerts[0].alert_type == "mission_replacement_required"
    assert open_alerts[0].entity_type == "mission_participant"
    assert open_alerts[0].entity_id == participant.id
    assert open_alerts[0].alert_metadata["mission_id"] == mission.id
    assert "Doctor Mission" in open_alerts[0].message


def test_deactivate_service_does_not_duplicate_replacement_alert(db_session) -> None:
    service = _make_alerting_service(db_session)
    alerts = ActionAlertRepository(db_session)

    doctor = service.create_doctor(
        actor_id="a", name="Doctor Duplicate", sex="female", rank_id=None, department_id=None,
        notes=None, participa_misiones=True, whatsapp_phone="+18095551234",
        monthly_service_target=3, monthly_service_max=3,
        monthly_service_limit_mode="warn_only", availability_mode="monthly",
        allowed_area_ids=[],
    )
    _create_confirmed_mission_with_participant(db_session, doctor.id)

    service.deactivate_service(doctor.id, actor_id="a", reason_id="r1", detail=None)
    service.deactivate_service(doctor.id, actor_id="a", reason_id="r1", detail=None)

    assert len(alerts.list_all(status="open", section="missions")) == 1


# ---------------------------------------------------------------------------
# Soft delete
# ---------------------------------------------------------------------------


def test_soft_delete_doctor_marks_deleted_at(db_session) -> None:
    service = _make_service(db_session)
    repo = DoctorRepository(db_session)

    doctor = service.create_doctor(
        actor_id="a", name="Dr. To Delete", sex="male", rank_id=None, department_id=None,
        notes=None, participa_misiones=True, whatsapp_phone="+18095551234",
        monthly_service_target=3, monthly_service_max=3,
        monthly_service_limit_mode="warn_only", availability_mode="monthly",
        allowed_area_ids=[],
    )

    service.soft_delete_doctor(doctor.id, actor_id="a")

    deleted = repo.session.get(DoctorModel, doctor.id)
    assert deleted.deleted_at is not None


def test_soft_delete_doctor_hides_from_queries(db_session) -> None:
    service = _make_service(db_session)
    repo = DoctorRepository(db_session)

    doctor = service.create_doctor(
        actor_id="a", name="Dr. Hidden", sex="female", rank_id=None, department_id=None,
        notes=None, participa_misiones=True, whatsapp_phone="+18095551234",
        monthly_service_target=3, monthly_service_max=3,
        monthly_service_limit_mode="warn_only", availability_mode="monthly",
        allowed_area_ids=[],
    )
    service.soft_delete_doctor(doctor.id, actor_id="a")

    assert repo.get_by_id(doctor.id) is None
    assert doctor.name not in [d.name for d in repo.list_all()]
    assert doctor.name not in [d.name for d in repo.list_service_active()]
    assert doctor.name not in [d.name for d in repo.list_with_filters(active_only=False)]


def test_soft_delete_doctor_not_found(db_session) -> None:
    service = _make_service(db_session)

    with pytest.raises(DoctorServiceError) as exc_info:
        service.soft_delete_doctor("nonexistent-id", actor_id="a")
    assert exc_info.value.code == "doctor_not_found"


def test_soft_delete_doctor_updates_updated_at(db_session) -> None:
    service = _make_service(db_session)
    repo = DoctorRepository(db_session)

    doctor = service.create_doctor(
        actor_id="a", name="Dr. Timestamp", sex="male", rank_id=None, department_id=None,
        notes=None, participa_misiones=True, whatsapp_phone="+18095551234",
        monthly_service_target=3, monthly_service_max=3,
        monthly_service_limit_mode="warn_only", availability_mode="monthly",
        allowed_area_ids=[],
    )
    original_updated_at = doctor.updated_at

    service.soft_delete_doctor(doctor.id, actor_id="a")

    deleted = repo.session.get(DoctorModel, doctor.id)
    assert deleted.updated_at > original_updated_at


# ---------------------------------------------------------------------------
# list_by_day
# ---------------------------------------------------------------------------


def test_list_by_day_groups_weekly_fixed_doctors(db_session):
    from backend.app.infrastructure.db.models.availability import DoctorAvailabilityModel

    service = _make_service(db_session)
    now = datetime.now(UTC)

    doctor = DoctorModel(
        id=str(uuid4()),
        name="Lunes Doc",
        normalized_name="lunes doc",
        sex="male",
        whatsapp_phone="+18095551234",
        created_at=now,
        updated_at=now,
    )
    db_session.add(doctor)
    db_session.flush()

    avail = DoctorAvailabilityModel(
        id=str(uuid4()),
        doctor_id=doctor.id,
        availability_type="weekly_fixed",
        days_of_week=[0],
        review_status="approved",
        created_at=now,
        updated_at=now,
    )
    db_session.add(avail)
    db_session.commit()

    result = service.list_by_day()
    assert result["0"]["label"] == "Lunes"
    assert result["0"]["count"] == 1
    assert result["0"]["doctors"][0]["name"] == "Lunes Doc"
    assert result["1"]["count"] == 0


def test_list_by_day_includes_recurring_tag(db_session):
    from backend.app.infrastructure.db.models.availability import DoctorAvailabilityModel

    service = _make_service(db_session)
    now = datetime.now(UTC)

    doctor = DoctorModel(
        id=str(uuid4()),
        name="Recurring Doc",
        normalized_name="recurring doc",
        sex="female",
        whatsapp_phone="+18095551234",
        created_at=now,
        updated_at=now,
    )
    db_session.add(doctor)
    db_session.flush()

    avail = DoctorAvailabilityModel(
        id=str(uuid4()),
        doctor_id=doctor.id,
        availability_type="recurring",
        days_of_week=None,
        weekday=4,
        week_number=-1,
        review_status="approved",
        created_at=now,
        updated_at=now,
    )
    db_session.add(avail)
    db_session.commit()

    result = service.list_by_day()
    assert result["4"]["count"] == 1
    assert result["4"]["doctors"][0]["recurring_tag"] == "último Viernes"


def test_list_by_day_deduplicates_doctor_with_weekly_and_recurring_same_day(db_session):
    from backend.app.infrastructure.db.models.availability import DoctorAvailabilityModel

    service = _make_service(db_session)
    now = datetime.now(UTC)

    doctor = DoctorModel(
        id=str(uuid4()),
        name="Duplicate Tuesday Doc",
        normalized_name="duplicate tuesday doc",
        sex="male",
        whatsapp_phone="+18095551234",
        created_at=now,
        updated_at=now,
    )
    db_session.add(doctor)
    db_session.flush()

    db_session.add(
        DoctorAvailabilityModel(
            id=str(uuid4()),
            doctor_id=doctor.id,
            availability_type="weekly_fixed",
            days_of_week=[1],
            review_status="approved",
            created_at=now,
            updated_at=now,
        )
    )
    db_session.add(
        DoctorAvailabilityModel(
            id=str(uuid4()),
            doctor_id=doctor.id,
            availability_type="recurring",
            days_of_week=None,
            weekday=1,
            week_number=1,
            review_status="approved",
            created_at=now,
            updated_at=now,
        )
    )
    db_session.commit()

    result = service.list_by_day()

    assert result["1"]["count"] == 1
    assert [doc["id"] for doc in result["1"]["doctors"]] == [doctor.id]
    assert result["1"]["doctors"][0]["recurring_tag"] == "segundo Martes"


def test_list_by_day_excludes_monthly_variable(db_session):
    from backend.app.infrastructure.db.models.availability import DoctorAvailabilityModel

    service = _make_service(db_session)
    now = datetime.now(UTC)

    doctor = DoctorModel(
        id=str(uuid4()),
        name="Monthly Doc",
        normalized_name="monthly doc",
        sex="male",
        whatsapp_phone="+18095551234",
        created_at=now,
        updated_at=now,
    )
    db_session.add(doctor)
    db_session.flush()

    avail = DoctorAvailabilityModel(
        id=str(uuid4()),
        doctor_id=doctor.id,
        availability_type="monthly_variable",
        available_dates=[5, 12, 20],
        year=2026,
        month=5,
        review_status="approved",
        created_at=now,
        updated_at=now,
    )
    db_session.add(avail)
    db_session.commit()

    result = service.list_by_day()
    total = sum(day["count"] for day in result.values())
    assert total == 0
