from datetime import date

from backend.app.domain.calendars.rules.interface import RuleContext
from backend.app.domain.calendars.rules.rule_availability_priority import (
    AVAILABILITY_SUBMITTED_BONUS,
    AvailabilityPriorityRule,
)

_SLOT = date(2026, 7, 15)


def _ctx(**overrides) -> RuleContext:
    base = dict(
        doctor_id="doc-1",
        slot_date=_SLOT,
        service_area_id="emergencia",
        area_weight=3.0,
        monthly_assignments=[],
        historical_assignments=[],
        mission_assignments=[],
        monthly_count=0,
        monthly_service_target=3,
        monthly_service_max=3,
        allowed_area_ids=["emergencia", "pista", "disponible"],
        strong_area_ids={"emergencia", "pista"},
        area_weights={"emergencia": 3.0, "pista": 2.0, "disponible": 1.0},
        is_active=True,
        is_service_active=True,
        hard_block_active=False,
        has_availability=True,
        submitted_availability=False,
    )
    base.update(overrides)
    return RuleContext(**base)


def test_no_bonus_without_submitted_availability() -> None:
    result = AvailabilityPriorityRule().evaluate(_ctx(submitted_availability=False))
    assert result.score_delta == 0.0
    assert result.warnings == []


def test_bonus_when_availability_submitted() -> None:
    result = AvailabilityPriorityRule().evaluate(_ctx(submitted_availability=True))
    assert result.score_delta == AVAILABILITY_SUBMITTED_BONUS
    assert result.extra["submitted_availability"] is True


def test_never_blocks() -> None:
    """Regla blanda: nunca es bloqueante."""
    result = AvailabilityPriorityRule().evaluate(_ctx(submitted_availability=False))
    assert result.is_blocking is False
