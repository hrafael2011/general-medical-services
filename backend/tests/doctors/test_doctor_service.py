from backend.app.application.doctors.service import DoctorService
from backend.app.infrastructure.repositories.doctors import DoctorRepository


def _make_service(db_session) -> DoctorService:
    return DoctorService(DoctorRepository(db_session))


def test_create_doctor_stores_basic_fields(db_session) -> None:
    service = _make_service(db_session)

    doctor = service.create_doctor(
        actor_id="actor-001",
        name="  Juan Pérez  ",
        sex="male",
        rank_id=None,
        department_id=None,
        phone=None,
        notes=None,
        participa_misiones=True,
        whatsapp_phone=None,
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


def test_create_doctor_trims_name(db_session) -> None:
    service = _make_service(db_session)

    doctor = service.create_doctor(
        actor_id="actor-001",
        name="  Ana García  ",
        sex="female",
        rank_id=None,
        department_id=None,
        phone=None,
        notes=None,
        participa_misiones=False,
        whatsapp_phone=None,
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
        phone=None, notes=None, participa_misiones=True, whatsapp_phone=None,
        monthly_service_target=3, monthly_service_max=3,
        monthly_service_limit_mode="warn_only", availability_mode="monthly",
        allowed_area_ids=[],
    )
    service.create_doctor(
        actor_id="a", name="Doctor B", sex="female", rank_id=None, department_id=None,
        phone=None, notes=None, participa_misiones=True, whatsapp_phone=None,
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
        phone=None, notes=None, participa_misiones=True, whatsapp_phone=None,
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
        phone="555-1234",
        notes=None,
        participa_misiones=None,
        whatsapp_phone=None,
        monthly_service_target=None,
        monthly_service_max=None,
        monthly_service_limit_mode=None,
        availability_mode=None,
        allowed_area_ids=None,
    )

    assert updated.name == "Updated Name"
    assert updated.phone == "555-1234"


def test_deactivate_and_reactivate_service(db_session) -> None:
    service = _make_service(db_session)

    doctor = service.create_doctor(
        actor_id="a", name="Dr. Test", sex="male", rank_id=None, department_id=None,
        phone=None, notes=None, participa_misiones=True, whatsapp_phone=None,
        monthly_service_target=3, monthly_service_max=3,
        monthly_service_limit_mode="warn_only", availability_mode="monthly",
        allowed_area_ids=[],
    )
    assert doctor.service_active is True

    service.deactivate_service(doctor.id, actor_id="a", reason_id="reason-001", detail="En licencia")
    assert doctor.service_active is False
    assert doctor.service_inactive_reason_id == "reason-001"
    assert doctor.service_inactive_detail == "En licencia"

    service.reactivate_service(doctor.id, actor_id="a")
    assert doctor.service_active is True
    assert doctor.service_inactive_reason_id is None


def test_service_active_filter(db_session) -> None:
    service = _make_service(db_session)
    repo = DoctorRepository(db_session)

    d1 = service.create_doctor(
        actor_id="a", name="Active Doc", sex="male", rank_id=None, department_id=None,
        phone=None, notes=None, participa_misiones=True, whatsapp_phone=None,
        monthly_service_target=3, monthly_service_max=3,
        monthly_service_limit_mode="warn_only", availability_mode="monthly",
        allowed_area_ids=[],
    )
    service.create_doctor(
        actor_id="a", name="Inactive Doc", sex="female", rank_id=None, department_id=None,
        phone=None, notes=None, participa_misiones=True, whatsapp_phone=None,
        monthly_service_target=3, monthly_service_max=3,
        monthly_service_limit_mode="warn_only", availability_mode="monthly",
        allowed_area_ids=[],
    )
    service.deactivate_service(d1.id, actor_id="a", reason_id="r1", detail=None)

    active_docs = repo.list_service_active()
    names = [d.name for d in active_docs]
    assert "Active Doc" not in names
    assert "Inactive Doc" in names
