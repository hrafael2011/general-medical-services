"""Tests del recordatorio de reintegro (spec licencias-con-fechas-y-recordatorio).

El job abre su propia sesión con `SessionLocal`, así que se parchea por la fábrica de la
base de pruebas: los datos se crean **de verdad** en PostgreSQL (con sus claves foráneas) y
el job los ve porque el montaje se confirma antes de ejecutarlo.

Lo que se prueba aquí es lo que el spec señala como delicado: la ventana, que "Indefinido"
no genere nada, que no se repita, y que editar la fecha **re-arme** el aviso.
"""

import datetime
import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import select

from backend.app.application.scheduler import jobs
from backend.app.infrastructure.db.models.action_alerts import ActionAlertModel
from backend.app.infrastructure.db.models.availability import DoctorRestrictionModel
from backend.app.infrastructure.db.models.catalogs import (
    DeactivationReasonModel,
    SystemSettingModel,
)
from backend.app.infrastructure.db.models.doctors import DoctorModel
from backend.app.infrastructure.db.models.notifications import NotificationEventModel
from backend.app.infrastructure.db.models.user import UserModel

SETTING_KEY = "notifications.license_reminder_days"


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC)


def _today() -> datetime.date:
    return _now().date()


@pytest.fixture
def actor(db_session) -> UserModel:
    user = UserModel(
        id=str(uuid.uuid4()),
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
    reason = DeactivationReasonModel(
        id=str(uuid.uuid4()),
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
    db_session.add(reason)
    db_session.commit()
    return reason


@pytest.fixture
def doctor(db_session, actor) -> DoctorModel:
    now = _now()
    doctor = DoctorModel(
        id=str(uuid.uuid4()),
        name="ANA PEREZ",
        normalized_name="ana perez",
        sex="female",
        active=True,
        service_active=True,
        participa_misiones=True,
        whatsapp_phone="+18095550000",
        created_at=now,
        updated_at=now,
    )
    db_session.add(doctor)
    db_session.commit()
    return doctor


def _add_recipient(db_session, *, chat_id: str = "555", with_permission: bool = True) -> UserModel:
    user = UserModel(
        id=str(uuid.uuid4()),
        email=f"enc-{uuid.uuid4().hex[:6]}@test.com",
        password_hash="hash",
        name="Encargado",
        role="encargado",
        active=True,
        must_change_password=False,
        token_version=1,
        permissions=["receive_escalation_alerts"] if with_permission else [],
        telegram_chat_id=chat_id,
        created_at=_now(),
        updated_at=_now(),
    )
    db_session.add(user)
    db_session.commit()
    return user


def _add_absence(
    db_session,
    doctor,
    reason,
    *,
    ends_at: datetime.date | None,
    starts_at: datetime.date | None = None,
    lifted: bool = False,
) -> DoctorRestrictionModel:
    now = _now()
    restriction = DoctorRestrictionModel(
        id=str(uuid.uuid4()),
        doctor_id=doctor.id,
        reason_id=reason.id,
        restriction_type="license",
        severity="hard_block",
        description=None,
        starts_at=starts_at or _today() - datetime.timedelta(days=10),
        ends_at=ends_at,
        source="manual",
        review_status="approved",
        created_by=None,
        created_at=now,
        updated_at=now,
        lifted_at=now if lifted else None,
        lifted_by=None,
    )
    db_session.add(restriction)
    db_session.commit()
    return restriction


def _run_job(session_local) -> dict:
    with patch(
        "backend.app.infrastructure.db.session.SessionLocal", session_local
    ):
        return jobs.send_license_return_reminders()


def _queued_events(session_local) -> list[NotificationEventModel]:
    with session_local() as s:
        return list(
            s.scalars(
                select(NotificationEventModel).where(
                    NotificationEventModel.notification_type == "license_return_reminder"
                )
            )
        )


def _open_alerts(session_local) -> list[ActionAlertModel]:
    with session_local() as s:
        return list(
            s.scalars(
                select(ActionAlertModel).where(
                    ActionAlertModel.alert_type == "license_return_due"
                )
            )
        )


# ---------------------------------------------------------------------------
# Ventana
# ---------------------------------------------------------------------------


def test_avisa_dentro_de_la_ventana(db_session, session_local, doctor, reason):
    """AC4: a 2 días del reintegro, el encargado recibe el aviso y ve la alerta."""
    _add_recipient(db_session, chat_id="555")
    _add_absence(db_session, doctor, reason, ends_at=_today() + datetime.timedelta(days=2))

    result = _run_job(session_local)

    assert result == {"reminders": 1, "alerts_created": 1}
    events = _queued_events(session_local)
    assert len(events) == 1
    assert events[0].recipient_phone == "555"
    assert "ANA PEREZ" in events[0].payload["message"]
    assert "LICENCIAS MEDICAS" in events[0].payload["message"]
    assert (_today() + datetime.timedelta(days=2)).isoformat() in events[0].payload["message"]

    alerts = _open_alerts(session_local)
    assert len(alerts) == 1
    assert "ANA PEREZ" in alerts[0].message


def test_no_avisa_fuera_de_la_ventana(db_session, session_local, doctor, reason):
    _add_recipient(db_session)
    _add_absence(db_session, doctor, reason, ends_at=_today() + datetime.timedelta(days=9))

    result = _run_job(session_local)

    assert result == {"reminders": 0, "alerts_created": 0}
    assert _queued_events(session_local) == []
    assert _open_alerts(session_local) == []


def test_una_ausencia_vencida_ya_no_avisa(db_session, session_local, doctor, reason):
    _add_recipient(db_session)
    _add_absence(db_session, doctor, reason, ends_at=_today() - datetime.timedelta(days=1))

    assert _run_job(session_local) == {"reminders": 0, "alerts_created": 0}


def test_una_ausencia_levantada_no_avisa(db_session, session_local, doctor, reason):
    """Si el médico volvió antes y se levantó la ausencia, no se anuncia nada."""
    _add_recipient(db_session)
    _add_absence(
        db_session,
        doctor,
        reason,
        ends_at=_today() + datetime.timedelta(days=1),
        lifted=True,
    )

    assert _run_job(session_local) == {"reminders": 0, "alerts_created": 0}


def test_indefinido_no_genera_nada(db_session, session_local, doctor, reason):
    """AC3: una ausencia sin fecha de regreso no programa ningún aviso."""
    _add_recipient(db_session)
    _add_absence(db_session, doctor, reason, ends_at=None)

    assert _run_job(session_local) == {"reminders": 0, "alerts_created": 0}
    assert _queued_events(session_local) == []


# ---------------------------------------------------------------------------
# Idempotencia y re-armado
# ---------------------------------------------------------------------------


def test_no_se_repite_al_correr_dos_veces(db_session, session_local, doctor, reason):
    """AC5: dos corridas seguidas, un solo aviso."""
    _add_recipient(db_session)
    _add_absence(db_session, doctor, reason, ends_at=_today() + datetime.timedelta(days=2))

    _run_job(session_local)
    _run_job(session_local)

    assert len(_queued_events(session_local)) == 1
    assert len(_open_alerts(session_local)) == 1


def test_editar_la_fecha_rearma_y_volver_a_la_anterior_no(db_session, session_local, doctor, reason):
    """AC6: cambiar la fecha vuelve a avisar; volver a la anterior, no."""
    _add_recipient(db_session)
    original = _today() + datetime.timedelta(days=2)
    restriction = _add_absence(db_session, doctor, reason, ends_at=original)

    _run_job(session_local)
    assert len(_queued_events(session_local)) == 1

    # Se adelanta el reintegro: la clave de idempotencia cambia y el aviso vuelve a salir.
    restriction.ends_at = _today() + datetime.timedelta(days=1)
    db_session.commit()
    _run_job(session_local)
    assert len(_queued_events(session_local)) == 2

    # Y volver a la fecha anterior NO re-avisa: esa clave ya existía.
    restriction.ends_at = original
    db_session.commit()
    _run_job(session_local)
    assert len(_queued_events(session_local)) == 2

    # La alerta de la campana es una sola y muestra la fecha vigente, no una vieja.
    alerts = _open_alerts(session_local)
    assert len(alerts) == 1
    assert original.isoformat() in alerts[0].message


# ---------------------------------------------------------------------------
# Configuración y destinatarios
# ---------------------------------------------------------------------------


def test_la_ventana_sale_de_la_configuracion(db_session, session_local, doctor, reason):
    """Fase 2: los días de aviso son un ajuste, no un número escrito en el código."""
    _add_recipient(db_session)
    _add_absence(db_session, doctor, reason, ends_at=_today() + datetime.timedelta(days=5))

    # Con el valor por defecto (2) todavía no toca avisar.
    assert _run_job(session_local) == {"reminders": 0, "alerts_created": 0}

    db_session.add(
        SystemSettingModel(
            key=SETTING_KEY,
            value="5",
            description="Días de antelación del recordatorio de reintegro.",
            updated_at=_now(),
        )
    )
    db_session.commit()

    assert _run_job(session_local)["reminders"] == 1


def test_sin_destinatarios_no_encola_pero_deja_la_alerta(db_session, session_local, doctor, reason):
    """Sin nadie vinculado el aviso no sale, pero la campana no depende de Telegram."""
    _add_recipient(db_session, chat_id="555", with_permission=False)
    _add_absence(db_session, doctor, reason, ends_at=_today() + datetime.timedelta(days=1))

    result = _run_job(session_local)

    assert result == {"reminders": 1, "alerts_created": 1}
    assert _queued_events(session_local) == []
    assert len(_open_alerts(session_local)) == 1
