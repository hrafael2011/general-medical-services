from backend.app.application.action_alerts.service import ActionAlertService
from backend.app.infrastructure.repositories.action_alerts import ActionAlertRepository


def _make_service(db_session) -> ActionAlertService:
    return ActionAlertService(ActionAlertRepository(db_session))


def test_create_alert_starts_open(db_session) -> None:
    service = _make_service(db_session)

    alert = service.create_alert(
        alert_type="mission_replacement_required",
        section="missions",
        severity="critical",
        title="Reemplazo requerido",
        message="Un médico desactivado está asignado a una misión confirmada.",
        entity_type="mission",
        entity_id="mission-1",
        action_url="/missions",
        created_by="user-1",
    )

    assert alert.id is not None
    assert alert.status == "open"
    assert alert.section == "missions"
    assert alert.severity == "critical"
    assert alert.resolved_at is None


def test_count_open_by_section_ignores_resolved(db_session) -> None:
    service = _make_service(db_session)
    repo = ActionAlertRepository(db_session)

    open_alert = service.create_alert(
        alert_type="mission_replacement_required",
        section="missions",
        title="Reemplazo requerido",
        message="Debe reemplazar un médico.",
    )
    service.create_alert(
        alert_type="service_confirmation_overdue",
        section="calendar",
        title="Confirmación vencida",
        message="Un médico no ha confirmado servicio.",
    )
    service.resolve(open_alert.id, actor_id="user-1")

    counts = repo.count_open_by_section()

    assert counts == {"calendar": 1}


def test_dismiss_alert_keeps_record(db_session) -> None:
    service = _make_service(db_session)
    repo = ActionAlertRepository(db_session)
    alert = service.create_alert(
        alert_type="notification_failed",
        section="notifications",
        title="Notificación fallida",
        message="No se pudo enviar una notificación.",
    )

    dismissed = service.dismiss(alert.id, actor_id="user-1")
    fetched = repo.get_by_id(alert.id)

    assert dismissed.status == "dismissed"
    assert fetched is not None
    assert fetched.id == alert.id
    assert fetched.dismissed_at is not None
