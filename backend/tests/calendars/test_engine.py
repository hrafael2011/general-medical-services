"""
Tests for CalendarEngine.

Pure Python — no database access. GenerationContext is built manually using
SimpleNamespace objects to stand in for ORM models.
"""

import datetime
from types import SimpleNamespace

import pytest

from backend.app.domain.calendars.engine import CalendarEngine, GenerationContext
from backend.app.domain.calendars.scoring import AREA_WEIGHTS


# ---------------------------------------------------------------------------
# Constants shared across tests
# ---------------------------------------------------------------------------

REQUIRED_AREAS = ["emergencia", "pista", "disponible"]

# February 2026 has exactly 28 days.
_YEAR = 2026
_MONTH = 2
_DAYS_IN_MONTH = 28
_TOTAL_SLOTS = _DAYS_IN_MONTH * len(REQUIRED_AREAS)  # 84


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_doctor(doctor_id: str) -> SimpleNamespace:
    """Return a minimal doctor-like object that the engine inspects."""
    return SimpleNamespace(id=doctor_id, active=True, service_active=True)


def _base_context(**overrides) -> GenerationContext:
    """Return a GenerationContext for Feb 2026 with sensible defaults."""
    defaults = dict(
        year=_YEAR,
        month=_MONTH,
        doctors=[],
        allowed_areas={},
        availability={},
        restrictions={},
        existing_assignments=[],
        historical_assignments=[],
        mission_assignments=[],
        required_areas=REQUIRED_AREAS,
        area_weights=AREA_WEIGHTS,
    )
    defaults.update(overrides)
    return GenerationContext(**defaults)


# ---------------------------------------------------------------------------
# test_generate_fills_all_slots_with_one_doctor
# ---------------------------------------------------------------------------


def test_generate_fills_all_slots_with_one_doctor() -> None:
    """A single doctor allowed in all three areas with no restrictions and no
    availability records (unsubmitted → eligible) fills exactly one slot per
    calendar day (the engine enforces one assignment per doctor per day).

    With 28 days and 1 doctor, the engine can assign 28 slots (one per day)
    and must leave the remaining 56 slots (2 per day) as gaps.
    """
    doctor = _make_doctor("doc-1")

    ctx = _base_context(
        doctors=[doctor],
        allowed_areas={"doc-1": ["emergencia", "pista", "disponible"]},
        # Empty dicts → no availability records → unsubmitted = eligible
        availability={},
        restrictions={},
    )

    engine = CalendarEngine()
    summary = engine.generate(ctx)

    assert summary.total_slots == _TOTAL_SLOTS
    assert summary.assigned_count == _DAYS_IN_MONTH   # one slot per day
    assert summary.gap_count == _TOTAL_SLOTS - _DAYS_IN_MONTH
    assert summary.year == _YEAR
    assert summary.month == _MONTH

    # Every assigned slot must belong to doc-1
    assigned_doctors = {
        r.assigned_doctor_id
        for r in summary.slot_results
        if r.assigned_doctor_id is not None
    }
    assert assigned_doctors == {"doc-1"}


# ---------------------------------------------------------------------------
# test_generate_creates_gap_when_no_doctor
# ---------------------------------------------------------------------------


def test_generate_creates_gap_when_no_doctor() -> None:
    """With no doctors in the context, every slot must become a gap."""
    ctx = _base_context(
        doctors=[],
        allowed_areas={},
    )

    engine = CalendarEngine()
    summary = engine.generate(ctx)

    assert summary.total_slots == _TOTAL_SLOTS
    assert summary.gap_count == _TOTAL_SLOTS
    assert summary.assigned_count == 0

    # Every result should have no assigned doctor and a gap rationale.
    for result in summary.slot_results:
        assert result.assigned_doctor_id is None
        assert result.rationale.get("gap") is True


# ---------------------------------------------------------------------------
# test_generate_respects_hard_block
# ---------------------------------------------------------------------------


def test_generate_respects_hard_block() -> None:
    """A doctor with a hard_block restriction spanning the full month must not
    be assigned to any slot.  All slots must become gaps.

    The restriction uses datetime objects for starts_at (open-ended via
    ends_at=None), matching the real DoctorRestrictionModel layout.
    """
    doctor = _make_doctor("doc-1")

    # Restriction starts on the first day of the month, ends_at=None → open-ended
    block = SimpleNamespace(
        severity="hard_block",
        starts_at=datetime.datetime(_YEAR, _MONTH, 1, 0, 0, 0),
        ends_at=None,
    )

    ctx = _base_context(
        doctors=[doctor],
        allowed_areas={"doc-1": ["emergencia", "pista", "disponible"]},
        availability={},
        restrictions={"doc-1": [block]},
    )

    engine = CalendarEngine()
    summary = engine.generate(ctx)

    assert summary.total_slots == _TOTAL_SLOTS
    assert summary.gap_count == _TOTAL_SLOTS
    assert summary.assigned_count == 0

    # No slot should be assigned to doc-1
    assigned_doctors = {
        r.assigned_doctor_id
        for r in summary.slot_results
        if r.assigned_doctor_id is not None
    }
    assert "doc-1" not in assigned_doctors
