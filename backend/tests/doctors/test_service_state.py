"""El estado "activo para servicio" se deriva de las ausencias (extensión v1.3.0).

Antes había dos formas de decir que un médico no está disponible y dejaban estados distintos.
Ahora hay una sola —la ausencia— y el flag `doctors.service_active` es un **valor calculado**:
activo = sin ausencia vigente hoy.

Estos tests comprueban lo que eso significa en la práctica: que una ausencia vigente lo saca,
que una futura todavía no, que levantar la ausencia lo devuelve, que el motivo se copia, que
editar las fechas recalcula, y que nada de esto **borra** su disponibilidad ni sus áreas.
"""

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest

from backend.app.application.audit.service import AuditService
from backend.app.application.availability.service import AvailabilityService
from backend.app.application.doctors.errors import DoctorServiceError
from backend.app.application.doctors.service import DoctorService
from backend.app.application.doctors.service_state import sync_service_state
from backend.app.infrastructure.db.models.audit import AuditEventModel
from backend.app.infrastructure.db.models.availability import (
    DoctorAvailabilityModel,
    DoctorRestrictionModel,
)
from backend.app.infrastructure.db.models.catalogs import (
    DeactivationReasonModel,
    ServiceAreaModel,
)
from backend.app.infrastructure.db.models.doctors import DoctorModel
from backend.app.infrastructure.db.models.user import UserModel
from backend.app.infrastructure.repositories.audit import AuditRepository
from backend.app.infrastructure.repositories.availability import AvailabilityRepository
from backend.app.infrastructure.repositories.catalogs import CatalogRepository
from backend.app.infrastructure.repositories.doctors import DoctorRepository


def _now() -> datetime:
    return datetime.now(UTC)


def _today() -> date:
    return _now().date()


@pytest.fixture
def actor(db_session) -> UserModel:
    user = UserModel(
        id="actor-1",
        email="actor@test.com",
        password_hash="hash",
        name="Actor",
        role="admin",
        active=True,
        must_change_password=False,
        token_version=1,
        created_at=_now(),
        updated_at=_now(),
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def reason(db_session) -> DeactivationReasonModel:
    r = DeactivationReasonModel(
        id="r-licencia",
        code="licencias_medicas",
        display_name="LICENCIAS MEDICAS",
        active=True,
        requires_detail=False,
        applies_to_sex=None,
        severity="hard_block",
        expects_return=True,
        created_at=_now(),
        updated_at=_now(),
    )
    db_session.add(r)
    db_session.commit()
    return r


@pytest.fixture
def area(db_session) -> ServiceAreaModel:
    a = ServiceAreaModel(
        id="area-1",
        code="emergencia",
        display_name="Emergencia",
        active=True,
        required_for_daily_coverage=True,
        load_weight=3,
        created_at=_now(),
        updated_at=_now(),
    )
    db_session.add(a)
    db_session.commit()
    return a


@pytest.fixture
def doctor(db_session) -> DoctorModel:
    d = DoctorModel(
        id=str(uuid4()),
        name="ANA PEREZ",
        normalized_name="ana perez",
        sex="female",
        active=True,
        service_active=True,
        participa_misiones=True,
        whatsapp_phone="+18095550000",
        availability_mode="monthly",
        created_at=_now(),
        updated_at=_now(),
    )
    db_session.add(d)
    db_session.commit()
    return d


def _availability_service(db_session) -> AvailabilityService:
    return AvailabilityService(
        availability_repo=AvailabilityRepository(db_session),
        doctor_repo=DoctorRepository(db_session),
        audit=AuditService(AuditRepository(db_session)),
        catalog_repo=CatalogRepository(db_session),
    )


def _add_absence(db_session, doctor, reason, *, starts_at: date, ends_at: date | None):
    record = _availability_service(db_session).add_restriction(
        doctor.id,
        restriction_type="license",
        severity="hard_block",
        starts_at=starts_at,
        ends_at=ends_at,
        description="Licencia de prueba",
        reason_id=reason.id,
        actor_id="actor-1",
    )
    db_session.commit()
    return record


def _reload(db_session, doctor) -> DoctorModel:
    db_session.expire_all()
    return db_session.get(DoctorModel, doctor.id)


# ---------------------------------------------------------------------------
# El estado se deriva
# ---------------------------------------------------------------------------


def test_una_ausencia_vigente_lo_saca_de_servicio(db_session, doctor, reason) -> None:
    _add_absence(db_session, doctor, reason, starts_at=_today() - timedelta(days=1),
                 ends_at=_today() + timedelta(days=3))

    assert _reload(db_session, doctor).service_active is False


def test_una_ausencia_futura_todavia_no_lo_saca(db_session, doctor, reason) -> None:
    """El médico sigue trabajando hasta que la ausencia empieza: eso es lo que la hace útil."""
    _add_absence(db_session, doctor, reason, starts_at=_today() + timedelta(days=3),
                 ends_at=_today() + timedelta(days=5))

    assert _reload(db_session, doctor).service_active is True


def test_una_ausencia_terminada_lo_devuelve_solo(db_session, doctor, reason) -> None:
    _add_absence(db_session, doctor, reason, starts_at=_today() - timedelta(days=9),
                 ends_at=_today() - timedelta(days=2))

    assert _reload(db_session, doctor).service_active is True


def test_levantar_la_ausencia_lo_devuelve(db_session, doctor, reason) -> None:
    record = _add_absence(db_session, doctor, reason, starts_at=_today() - timedelta(days=1),
                          ends_at=None)
    assert _reload(db_session, doctor).service_active is False

    _availability_service(db_session).lift_restriction(record.id, actor_id="actor-1")
    db_session.commit()

    reactivated = _reload(db_session, doctor)
    assert reactivated.service_active is True
    assert reactivated.service_inactive_reason_id is None


def test_editar_las_fechas_recalcula_el_estado(db_session, doctor, reason) -> None:
    """Mover la ausencia al futuro devuelve al médico al servicio, y viceversa."""
    record = _add_absence(db_session, doctor, reason, starts_at=_today() - timedelta(days=1),
                          ends_at=None)
    assert _reload(db_session, doctor).service_active is False

    _availability_service(db_session).update_restriction(
        record.id,
        starts_at=_today() + timedelta(days=10),
        ends_at=_today() + timedelta(days=20),
        reason_id=reason.id,
        description=None,
        severity="hard_block",
        actor_id="actor-1",
    )
    db_session.commit()

    assert _reload(db_session, doctor).service_active is True


def test_el_motivo_y_el_detalle_se_copian_de_la_ausencia(db_session, doctor, reason) -> None:
    """La vista por departamento tiene que poder explicar por qué no está."""
    _add_absence(db_session, doctor, reason, starts_at=_today() - timedelta(days=1), ends_at=None)

    with_absence = _reload(db_session, doctor)
    assert with_absence.service_inactive_reason_id == reason.id
    assert with_absence.service_inactive_detail == "Licencia de prueba"


def test_el_recálculo_es_idempotente(db_session, doctor, reason) -> None:
    _add_absence(db_session, doctor, reason, starts_at=_today() - timedelta(days=1), ends_at=None)
    db_session.commit()

    assert sync_service_state(db_session) == []  # ya está en el estado correcto
    db_session.commit()


def test_el_cambio_por_fecha_queda_auditado_como_sistema(db_session, doctor, reason) -> None:
    """Si el estado cambia porque pasó la fecha, el historial dice que lo hizo el sistema.

    Se simula el caso real del job: la ausencia ya existía (la registró el script de conversión
    o una persona) y el estado se recalcula sin que nadie toque la ficha.
    """
    db_session.add(
        DoctorRestrictionModel(
            id=str(uuid4()),
            doctor_id=doctor.id,
            reason_id=reason.id,
            restriction_type="license",
            severity="hard_block",
            description="Ausencia que ya existía",
            starts_at=_today() - timedelta(days=1),
            ends_at=None,
            source="manual",
            review_status="approved",
            created_by=None,
            created_at=_now(),
            updated_at=_now(),
            lifted_at=None,
        )
    )
    db_session.commit()
    assert _reload(db_session, doctor).service_active is True, "todavía no se ha recalculado"

    # El recálculo del job: sin actor, porque no lo provocó una persona.
    changed = sync_service_state(db_session)
    db_session.commit()

    assert changed == [doctor.id]
    event = (
        db_session.query(AuditEventModel)
        .filter(
            AuditEventModel.action_type == "doctor_service_deactivated",
            AuditEventModel.entity_id == doctor.id,
        )
        .one()
    )
    assert event.actor_id is None, "la interfaz lo muestra como «Sistema»"


# ---------------------------------------------------------------------------
# Registrar una ausencia no destruye nada (AC13)
# ---------------------------------------------------------------------------


def test_registrar_una_ausencia_no_borra_disponibilidad_ni_areas(
    db_session, doctor, reason, area
) -> None:
    doctors = DoctorRepository(db_session)
    doctors.set_allowed_areas(doctor.id, [area.id])
    db_session.add(
        DoctorAvailabilityModel(
            id=str(uuid4()),
            doctor_id=doctor.id,
            availability_type="monthly_variable",
            available_dates=[3, 7, 15],
            year=_today().year,
            month=_today().month,
            day_priority="available",
            source="manual",
            review_status="approved",
            created_at=_now(),
            updated_at=_now(),
        )
    )
    db_session.commit()

    _add_absence(db_session, doctor, reason, starts_at=_today() - timedelta(days=1), ends_at=None)

    assert _reload(db_session, doctor).service_active is False
    assert doctors.get_allowed_areas(doctor.id) == [area.id], "las áreas no se tocan"
    availability = AvailabilityRepository(db_session).list_availability_for_doctor(doctor.id)
    assert len(availability) == 1, "la disponibilidad no se borra"
    assert availability[0].available_dates == [3, 7, 15]


# ---------------------------------------------------------------------------
# Las dos viejas puertas ahora escriben una ausencia
# ---------------------------------------------------------------------------


def test_desactivar_el_servicio_registra_una_ausencia_indefinida(
    db_session, doctor, reason, actor
) -> None:
    service = DoctorService(DoctorRepository(db_session))

    service.deactivate_service(doctor.id, actor_id=actor.id, reason_id=reason.id, detail="Reposo")
    db_session.commit()

    inactive = _reload(db_session, doctor)
    assert inactive.service_active is False
    assert inactive.participa_misiones is False

    restrictions = AvailabilityRepository(db_session).list_restrictions_for_doctor(doctor.id)
    assert len(restrictions) == 1
    assert restrictions[0].ends_at is None, "desactivar es una ausencia sin fecha de regreso"
    assert restrictions[0].reason_id == reason.id
    assert restrictions[0].description == "Reposo"


def test_reactivar_el_servicio_levanta_la_ausencia(db_session, doctor, reason, actor) -> None:
    service = DoctorService(DoctorRepository(db_session))
    service.deactivate_service(doctor.id, actor_id=actor.id, reason_id=reason.id, detail=None)
    db_session.commit()

    service.reactivate_service(doctor.id, actor_id=actor.id)
    db_session.commit()

    reactivated = _reload(db_session, doctor)
    assert reactivated.service_active is True
    assert reactivated.participa_misiones is True
    restrictions = AvailabilityRepository(db_session).list_restrictions_for_doctor(doctor.id)
    assert all(r.lifted_at is not None for r in restrictions)


def test_editar_con_service_inactive_false_sin_motivo_falla(db_session, doctor) -> None:
    """El motivo sigue siendo obligatorio; lo que cambia es dónde se guarda."""
    service = DoctorService(DoctorRepository(db_session))

    with pytest.raises(DoctorServiceError) as exc:
        service.update_doctor(doctor.id, actor_id="actor-1", service_active=False)

    assert exc.value.code == "reason_required"
    assert _reload(db_session, doctor).service_active is True, "no se cambia nada a medias"


def test_editar_con_service_inactive_false_registra_la_ausencia(
    db_session, doctor, reason, actor
) -> None:
    service = DoctorService(DoctorRepository(db_session))

    service.update_doctor(
        doctor.id,
        actor_id=actor.id,
        service_active=False,
        service_inactive_reason_id=reason.id,
        service_inactive_detail="Reposo",
    )
    db_session.commit()

    inactive = _reload(db_session, doctor)
    assert inactive.service_active is False
    assert inactive.participa_misiones is False
    restrictions = AvailabilityRepository(db_session).list_restrictions_for_doctor(doctor.id)
    assert len(restrictions) == 1
    assert restrictions[0].ends_at is None
    assert restrictions[0].description == "Reposo"


def test_desactivar_dos_veces_no_acumula_ausencias(db_session, doctor, reason, actor) -> None:
    service = DoctorService(DoctorRepository(db_session))
    service.deactivate_service(doctor.id, actor_id=actor.id, reason_id=reason.id, detail=None)
    db_session.commit()
    service.deactivate_service(doctor.id, actor_id=actor.id, reason_id=reason.id, detail=None)
    db_session.commit()

    restrictions = AvailabilityRepository(db_session).list_restrictions_for_doctor(doctor.id)
    assert len(restrictions) == 1, "reutiliza la ausencia que ya tenía"


def _service_without_audit(db_session) -> AvailabilityService:
    """El servicio **sin auditoría**, que es lo que destapó el fallo.

    Con auditoría, el `flush` del evento tapaba que el recálculo no veía los cambios
    pendientes; sin ella, el estado se quedaba un paso por detrás. Estos tests fijan que el
    recálculo haga su propio flush y no dependa de nadie.
    """
    return AvailabilityService(
        availability_repo=AvailabilityRepository(db_session),
        doctor_repo=DoctorRepository(db_session),
        catalog_repo=CatalogRepository(db_session),
    )


def test_editar_las_fechas_recalcula_sin_depender_del_audit(db_session, doctor, reason) -> None:
    service = _service_without_audit(db_session)
    record = service.add_restriction(
        doctor.id,
        restriction_type="license",
        severity="hard_block",
        starts_at=_today() - timedelta(days=1),
        ends_at=None,
        description=None,
        reason_id=reason.id,
        actor_id="actor-1",
    )
    db_session.commit()
    assert _reload(db_session, doctor).service_active is False

    # Mover la ausencia al futuro tiene que devolverlo al servicio **ya**, no en la próxima.
    service.update_restriction(
        record.id,
        starts_at=_today() + timedelta(days=10),
        ends_at=_today() + timedelta(days=20),
        reason_id=reason.id,
        description=None,
        severity="hard_block",
        actor_id="actor-1",
    )
    db_session.commit()

    assert _reload(db_session, doctor).service_active is True


def test_levantar_recalcula_sin_depender_del_audit(db_session, doctor, reason) -> None:
    service = _service_without_audit(db_session)
    record = service.add_restriction(
        doctor.id,
        restriction_type="license",
        severity="hard_block",
        starts_at=_today() - timedelta(days=1),
        ends_at=None,
        description=None,
        reason_id=reason.id,
        actor_id="actor-1",
    )
    db_session.commit()
    assert _reload(db_session, doctor).service_active is False

    service.lift_restriction(record.id, actor_id="actor-1")
    db_session.commit()

    reactivated = _reload(db_session, doctor)
    assert reactivated.service_active is True
    assert reactivated.service_inactive_reason_id is None
