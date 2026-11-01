"""Desbloquear cancela lo que la semana encoló.

El aviso se encola al aprobar; si desbloquear no lo retira, el worker lo manda
igual y el operador no puede deshacer su error.
"""

from datetime import date
from unittest.mock import MagicMock
from uuid import uuid4

from backend.app.application.calendars.service import CalendarService
from backend.app.infrastructure.db.models.calendars import (
    CalendarAssignmentModel,
    CalendarModel,
    CalendarVersionModel,
    CalendarWeekModel,
)

from .test_week_service import FakeWeekRepo


def _approved_week():
    repo = FakeWeekRepo()
    cal = CalendarModel(
        id=str(uuid4()), year=2026, month=5, status="approved", generation_mode="manual"
    )
    repo.add_calendar(cal)
    version = CalendarVersionModel(
        id=str(uuid4()), calendar_id=cal.id, version_number=1, status="approved"
    )
    repo.add_version(version)
    week = CalendarWeekModel(
        id=str(uuid4()),
        calendar_id=cal.id,
        calendar_version_id=version.id,
        week_number=1,
        label="1RA SEMANA",
        start_date=date(2026, 5, 4),
        end_date=date(2026, 5, 10),
        status="approved",
    )
    repo.add_week(week)
    dentro = CalendarAssignmentModel(
        id=str(uuid4()),
        calendar_version_id=version.id,
        calendar_week_id=week.id,
        service_date=date(2026, 5, 5),
        service_area_id="area1",
        doctor_id="doc1",
    )
    fuera = CalendarAssignmentModel(
        id=str(uuid4()),
        calendar_version_id=version.id,
        calendar_week_id=None,
        service_date=date(2026, 5, 20),
        service_area_id="area1",
        doctor_id="doc2",
    )
    repo.add_assignment(dentro)
    repo.add_assignment(fuera)
    return repo, week, dentro, fuera


def test_unlock_week_cancela_solo_lo_de_la_semana():
    repo, week, dentro, fuera = _approved_week()
    triggers = MagicMock()
    triggers.on_week_unapproved.return_value = {"notifications": 1, "confirmations": 1}

    CalendarService(repo=repo, triggers=triggers).unlock_week(actor_id="user1", week_id=week.id)

    triggers.on_week_unapproved.assert_called_once()
    enviadas = triggers.on_week_unapproved.call_args.kwargs["assignments"]
    assert [a.id for a in enviadas] == [dentro.id]


def test_unlock_calendar_cancela_todas_las_asignaciones():
    repo, week, dentro, fuera = _approved_week()
    triggers = MagicMock()
    triggers.on_week_unapproved.return_value = {"notifications": 2, "confirmations": 2}

    CalendarService(repo=repo, triggers=triggers).unlock_calendar(
        actor_id="user1", calendar_id=week.calendar_id
    )

    triggers.on_week_unapproved.assert_called_once()
    enviadas = triggers.on_week_unapproved.call_args.kwargs["assignments"]
    assert [a.id for a in enviadas] == [dentro.id, fuera.id]


def test_unlock_week_expone_cuantos_cancelo():
    """La pantalla necesita el número para decir qué se deshizo."""
    repo, week, _, _ = _approved_week()
    triggers = MagicMock()
    triggers.on_week_unapproved.return_value = {"notifications": 4, "confirmations": 4}

    result = CalendarService(repo=repo, triggers=triggers).unlock_week(
        actor_id="user1", week_id=week.id
    )

    assert result.cancelled_notifications == 4


def test_unlock_week_sin_triggers_no_falla():
    """El servicio se usa en pruebas y en scripts sin disparadores."""
    repo, week, _, _ = _approved_week()

    result = CalendarService(repo=repo).unlock_week(actor_id="user1", week_id=week.id)

    assert result.status == "draft"
