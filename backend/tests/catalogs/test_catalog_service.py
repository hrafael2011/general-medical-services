from backend.app.application.catalogs.service import CatalogService
from backend.app.infrastructure.repositories.catalogs import CatalogRepository


def test_seed_initial_catalogs_creates_mvp_service_areas(db_session) -> None:
    repository = CatalogRepository(db_session)
    service = CatalogService(repository)

    service.seed_initial_catalogs()

    areas = repository.list_service_areas()
    area_codes = {area.code for area in areas}

    assert area_codes == {"emergencia", "pista", "disponible"}
    assert repository.get_service_area_by_code("emergencia").load_weight == 3
    assert repository.get_service_area_by_code("pista").load_weight == 2
    assert repository.get_service_area_by_code("disponible").load_weight == 1

    department_names = {department.name for department in repository.list_departments()}
    assert department_names == {
        "Licencias Médicas",
        "Enseñanza",
        "Evaluaciones Médicas",
        "Subdirección",
        "Recursos Humanos",
    }


def test_seed_initial_catalogs_is_idempotent(db_session) -> None:
    repository = CatalogRepository(db_session)
    service = CatalogService(repository)

    service.seed_initial_catalogs()
    service.seed_initial_catalogs()

    assert len(repository.list_service_areas()) == 3
    assert len(repository.list_deactivation_reasons()) == 9
    assert len(repository.list_departments()) == 5


def test_pregnancy_reason_only_applies_to_female_doctors(db_session) -> None:
    repository = CatalogRepository(db_session)
    CatalogService(repository).seed_initial_catalogs()

    female_codes = {
        reason.code for reason in repository.list_deactivation_reasons_for_sex("female")
    }
    male_codes = {reason.code for reason in repository.list_deactivation_reasons_for_sex("male")}

    assert "pregnancy" in female_codes
    assert "pregnancy" not in male_codes


def test_create_rank_and_department(db_session) -> None:
    repository = CatalogRepository(db_session)
    service = CatalogService(repository)

    rank = service.create_rank("Coronel", "Cnel.")
    department = service.create_department("Emergencia")

    assert rank.normalized_name == "coronel"
    assert department.normalized_name == "emergencia"


def test_create_update_and_soft_delete_deactivation_reason(db_session) -> None:
    repository = CatalogRepository(db_session)
    service = CatalogService(repository)

    reason = service.create_deactivation_reason(
        code="training_leave",
        display_name="Capacitación",
        requires_detail=True,
        applies_to_sex=None,
        severity="warn",
    )

    assert reason.code == "training_leave"
    assert reason.display_name == "Capacitación"
    assert reason.active is True
    assert reason.requires_detail is True
    assert reason.applies_to_sex is None
    assert reason.severity == "warn"

    updated = service.update_deactivation_reason(
        reason.id,
        display_name="Capacitación externa",
        requires_detail=False,
        applies_to_sex="female",
        severity="hard_block",
        active=False,
    )

    assert updated.display_name == "Capacitación externa"
    assert updated.requires_detail is False
    assert updated.applies_to_sex == "female"
    assert updated.severity == "hard_block"
    assert updated.active is False

    affected = service.soft_delete_deactivation_reason(reason.id)

    assert affected == 0
    assert repository.get_deactivation_reason_by_id(reason.id).active is False
