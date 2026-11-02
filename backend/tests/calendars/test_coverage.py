"""Tests for the day × required-area coverage rule."""
from datetime import date

from backend.app.domain.calendars.coverage import (
    RequiredArea,
    find_coverage_gaps,
    format_coverage_message,
)

EMERGENCIA = RequiredArea(code="emergencia", display_name="Emergencia")
PISTA = RequiredArea(code="pista", display_name="Pista")
DISPONIBLE = RequiredArea(code="disponible", display_name="Disponible")
AREAS = [EMERGENCIA, PISTA, DISPONIBLE]


def _full_week(start: date, areas: list[RequiredArea]) -> list[tuple[date, str]]:
    """Every day of the week covered in every area."""
    return [
        (date.fromordinal(start.toordinal() + offset), area.code)
        for offset in range(7)
        for area in areas
    ]


def test_find_coverage_gaps_returns_empty_when_week_is_complete():
    start = date(2026, 5, 4)  # Monday
    gaps = find_coverage_gaps(
        start_date=start,
        end_date=date(2026, 5, 10),
        required_areas=AREAS,
        assignments=_full_week(start, AREAS),
    )

    assert gaps == []


def test_find_coverage_gaps_reports_day_with_no_doctors():
    start = date(2026, 5, 4)
    assignments = [
        pair for pair in _full_week(start, AREAS)
        if pair[0] != date(2026, 5, 6)  # Wednesday empty
    ]

    gaps = find_coverage_gaps(
        start_date=start,
        end_date=date(2026, 5, 10),
        required_areas=AREAS,
        assignments=assignments,
    )

    assert len(gaps) == 1
    assert gaps[0].service_date == date(2026, 5, 6)
    assert gaps[0].area_names == ["Emergencia", "Pista", "Disponible"]


def test_find_coverage_gaps_reports_area_missing_on_every_day():
    start = date(2026, 5, 4)
    assignments = [
        pair for pair in _full_week(start, AREAS)
        if pair[1] != DISPONIBLE.code
    ]

    gaps = find_coverage_gaps(
        start_date=start,
        end_date=date(2026, 5, 10),
        required_areas=AREAS,
        assignments=assignments,
    )

    assert len(gaps) == 7
    assert all(gap.area_names == ["Disponible"] for gap in gaps)


def test_find_coverage_gaps_ignores_areas_outside_the_range():
    assignments = _full_week(date(2026, 5, 4), AREAS)

    gaps = find_coverage_gaps(
        start_date=date(2026, 5, 4),
        end_date=date(2026, 5, 5),  # only Monday and Tuesday
        required_areas=AREAS,
        assignments=assignments,
    )

    assert gaps == []


def test_find_coverage_gaps_without_required_areas_never_blocks():
    gaps = find_coverage_gaps(
        start_date=date(2026, 5, 4),
        end_date=date(2026, 5, 10),
        required_areas=[],
        assignments=[],
    )

    assert gaps == []


def test_detail_shape_is_date_and_area_names():
    gaps = find_coverage_gaps(
        start_date=date(2026, 5, 4),
        end_date=date(2026, 5, 4),
        required_areas=AREAS,
        assignments=[(date(2026, 5, 4), "emergencia"), (date(2026, 5, 4), "pista")],
    )

    assert gaps[0].to_detail() == {"date": "2026-05-04", "areas": ["Disponible"]}


def test_format_coverage_message_names_day_and_area():
    gaps = find_coverage_gaps(
        start_date=date(2026, 5, 4),
        end_date=date(2026, 5, 4),
        required_areas=AREAS,
        assignments=[(date(2026, 5, 4), "emergencia"), (date(2026, 5, 4), "pista")],
    )

    message = format_coverage_message(gaps)

    assert message == (
        "No se puede aprobar: faltan médicos en lunes 04/05 (Disponible)."
    )


def test_format_coverage_message_lists_every_incomplete_day():
    gaps = find_coverage_gaps(
        start_date=date(2026, 5, 4),
        end_date=date(2026, 5, 6),
        required_areas=AREAS,
        assignments=[],
    )

    message = format_coverage_message(gaps)

    assert "lunes 04/05" in message
    assert "martes 05/05" in message
    assert "miércoles 06/05" in message


def test_format_coverage_message_summarises_long_lists():
    gaps = find_coverage_gaps(
        start_date=date(2026, 5, 4),
        end_date=date(2026, 5, 31),
        required_areas=AREAS,
        assignments=[],
    )

    message = format_coverage_message(gaps)

    assert "lunes 04/05" in message
    assert message.endswith("y 21 días más sin cubrir.")
    assert "sábado 30/05" not in message
