from backend.app.infrastructure.db.models.calendars import CalendarModel


def test_calendar_generation_mode_has_database_default() -> None:
    """Calendar inserts omitted by older code paths still default to manual."""
    column = CalendarModel.__table__.c.generation_mode

    assert column.default is not None
    assert column.server_default is not None
