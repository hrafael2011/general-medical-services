"""
Pure-Python tests for compute_candidate_score.

No database access needed — all inputs are plain Python dicts and date objects.
"""

import datetime

import pytest

from backend.app.domain.calendars.scoring import (
    MIN_SPACING_DISPONIBLE_AFTER_STRONG,
    MIN_SPACING_STRONG,
    compute_candidate_score,
)
from backend.app.domain.calendars.types import SlotRequest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SLOT_DATE = datetime.date(2026, 2, 15)

_SLOT_EMERGENCIA = SlotRequest(
    date=_SLOT_DATE,
    service_area_id="emergencia",
    area_weight=3.0,
)

_SLOT_PISTA = SlotRequest(
    date=_SLOT_DATE,
    service_area_id="pista",
    area_weight=2.0,
)

_SLOT_DISPONIBLE = SlotRequest(
    date=_SLOT_DATE,
    service_area_id="disponible",
    area_weight=1.0,
)


# ---------------------------------------------------------------------------
# test_score_no_history
# ---------------------------------------------------------------------------


def test_score_no_history() -> None:
    """A doctor with no prior assignments should receive a high score.

    Expected indicators:
    - days_since_last == 999 (sentinel for "never assigned")
    - days_since_strong == 999
    - no warnings
    - score should be notably high (above the 100.0 base after rests are added)
    """
    result = compute_candidate_score(
        doctor_id="doc-1",
        slot=_SLOT_EMERGENCIA,
        monthly_assignments=[],
        historical_assignments=[],
        mission_assignments=[],
    )

    assert result.doctor_id == "doc-1"
    assert result.days_since_last == 999
    assert result.days_since_strong == 999
    assert result.warnings == []
    assert result.is_spacing_violation is False
    # With no load and max day bonuses the score should be well above 100
    assert result.score > 100.0


# ---------------------------------------------------------------------------
# test_score_high_monthly_load_lowers_score
# ---------------------------------------------------------------------------


def test_score_high_monthly_load_lowers_score() -> None:
    """A doctor with 3 emergencia assignments this month scores lower than one with 0.

    emergencia weight = 3.0, so 3 assignments → monthly_load = 9.0
    Score penalty = monthly_load * 10 = 90 points.
    """
    slot = _SLOT_PISTA  # neutral area so no spacing warnings interfere

    heavy_assignments = [
        {
            "doctor_id": "doc-heavy",
            "service_date": datetime.date(2026, 2, d),
            "service_area_id": "emergencia",
        }
        for d in (1, 5, 9)
    ]

    score_heavy = compute_candidate_score(
        doctor_id="doc-heavy",
        slot=slot,
        monthly_assignments=heavy_assignments,
        historical_assignments=[],
        mission_assignments=[],
    )

    score_light = compute_candidate_score(
        doctor_id="doc-light",
        slot=slot,
        monthly_assignments=[],
        historical_assignments=[],
        mission_assignments=[],
    )

    assert score_heavy.monthly_load == 9.0
    assert score_light.monthly_load == 0.0
    assert score_heavy.score < score_light.score


# ---------------------------------------------------------------------------
# test_score_spacing_warning_strong
# ---------------------------------------------------------------------------


def test_score_spacing_warning_strong() -> None:
    """A doctor whose last emergencia was 5 days ago gets a spacing warning
    when being scored for another strong-area slot (emergencia).

    MIN_SPACING_STRONG = 14 days; 5 < 14 → warning expected.
    """
    last_strong_date = _SLOT_DATE - datetime.timedelta(days=5)

    monthly_assignments = [
        {
            "doctor_id": "doc-1",
            "service_date": last_strong_date,
            "service_area_id": "emergencia",
        }
    ]

    result = compute_candidate_score(
        doctor_id="doc-1",
        slot=_SLOT_EMERGENCIA,
        monthly_assignments=monthly_assignments,
        historical_assignments=[],
        mission_assignments=[],
    )

    assert result.days_since_strong == 5
    assert any("14" in w for w in result.warnings), (
        f"Expected spacing < 14 warning, got: {result.warnings}"
    )
    assert result.is_spacing_violation is True


# ---------------------------------------------------------------------------
# test_score_spacing_warning_disponible_after_strong
# ---------------------------------------------------------------------------


def test_score_spacing_warning_disponible_after_strong() -> None:
    """A doctor whose last emergencia was 3 days ago gets a spacing warning
    when being scored for a disponible slot.

    MIN_SPACING_DISPONIBLE_AFTER_STRONG = 7 days; 3 < 7 → warning expected.
    """
    last_strong_date = _SLOT_DATE - datetime.timedelta(days=3)

    monthly_assignments = [
        {
            "doctor_id": "doc-1",
            "service_date": last_strong_date,
            "service_area_id": "emergencia",
        }
    ]

    result = compute_candidate_score(
        doctor_id="doc-1",
        slot=_SLOT_DISPONIBLE,
        monthly_assignments=monthly_assignments,
        historical_assignments=[],
        mission_assignments=[],
    )

    assert result.days_since_strong == 3
    assert any("7" in w for w in result.warnings), (
        f"Expected spacing < 7 warning, got: {result.warnings}"
    )
    assert result.is_spacing_violation is True


# ---------------------------------------------------------------------------
# test_is_spacing_violation_set
# ---------------------------------------------------------------------------


def test_is_spacing_violation_set() -> None:
    """is_spacing_violation must be True whenever warnings is non-empty,
    and False when warnings is empty.
    """
    # Trigger a violation: last pista was 2 days ago, scoring for emergencia
    last_strong_date = _SLOT_DATE - datetime.timedelta(days=2)

    monthly_assignments = [
        {
            "doctor_id": "doc-1",
            "service_date": last_strong_date,
            "service_area_id": "pista",
        }
    ]

    with_violation = compute_candidate_score(
        doctor_id="doc-1",
        slot=_SLOT_EMERGENCIA,
        monthly_assignments=monthly_assignments,
        historical_assignments=[],
        mission_assignments=[],
    )

    assert len(with_violation.warnings) > 0
    assert with_violation.is_spacing_violation is True

    # Clean slate: no prior assignments → no warnings
    no_violation = compute_candidate_score(
        doctor_id="doc-2",
        slot=_SLOT_EMERGENCIA,
        monthly_assignments=[],
        historical_assignments=[],
        mission_assignments=[],
    )

    assert no_violation.warnings == []
    assert no_violation.is_spacing_violation is False
