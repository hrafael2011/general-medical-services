from datetime import date

from backend.app.domain.calendars.rules.rule_day_of_week_consistency import (
    DayOfWeekConsistencyRule,
    PRIMARY_MISMATCH_PENALTY,
    DISPERSION_PER_WEEKDAY_PENALTY,
)
from backend.app.domain.calendars.rules.interface import RuleContext

_SLOT = date(2026, 7, 15)  # Wednesday (weekday=2)


def test_no_primary_day_no_penalty():
    """Doctor without primary weekday → no penalty."""
    rule = DayOfWeekConsistencyRule()
    ctx = _ctx(primary_weekday=None, monthly=[])
    result = rule.evaluate(ctx)
    assert result.score_delta == 0.0
    assert result.warnings == []


def test_matches_primary_day_no_penalty():
    """Slot on the doctor's primary weekday → no penalty."""
    rule = DayOfWeekConsistencyRule()
    # slot is Wednesday (2), primary is Wednesday (2) → match
    ctx = _ctx(primary_weekday=2, monthly=[])
    result = rule.evaluate(ctx)
    assert result.score_delta == 0.0
    assert result.warnings == []


def test_mismatch_primary_day_penalty():
    """Slot different from primary weekday → penalty."""
    rule = DayOfWeekConsistencyRule()
    # slot is Wednesday (2), primary is Monday (0) → mismatch
    ctx = _ctx(primary_weekday=0, monthly=[])
    result = rule.evaluate(ctx)
    assert result.score_delta == -PRIMARY_MISMATCH_PENALTY
    assert any("preferido" in w for w in result.warnings)


def test_priority_mandatory_extra_penalty():
    """'mandatory' day priority adds extra penalty for that specific day."""
    rule = DayOfWeekConsistencyRule()
    # Slot is Wednesday (2), which has mandatory priority → extra penalty
    from backend.app.domain.calendars.rules.rule_day_of_week_consistency import MANDATORY_EXTRA
    ctx = _ctx(
        primary_weekday=2,  # Wednesday — matches slot
        day_priorities={2: "mandatory"},
        monthly=[],
    )
    result = rule.evaluate(ctx)
    # No PRIMARY_MISMATCH_PENALTY (primary matches slot)
    # But MANDATORY_EXTRA applies
    assert result.score_delta == MANDATORY_EXTRA
    assert any("obligatorio" in w for w in result.warnings)


def test_dispersion_penalty_new_weekday():
    """Introducing a new weekday for a doctor → dispersion penalty."""
    rule = DayOfWeekConsistencyRule()
    # Doctor already has assignments on Monday (0) and Tuesday (1)
    # Slot is Wednesday (2) → new weekday, 3rd distinct day
    ctx = _ctx(
        primary_weekday=0,
        monthly=[
            {"doctor_id": "doc-1", "service_date": date(2026, 7, 13), "service_area_id": "emergencia"},  # Monday
            {"doctor_id": "doc-1", "service_date": date(2026, 7, 14), "service_area_id": "pista"},       # Tuesday
        ],
    )
    result = rule.evaluate(ctx)
    penalty = -PRIMARY_MISMATCH_PENALTY - DISPERSION_PER_WEEKDAY_PENALTY * 3
    assert result.score_delta == penalty
    assert any("distinto" in w for w in result.warnings)


def test_no_dispersion_for_first_assignment():
    """First assignment in the month → no dispersion penalty (no prior days)."""
    rule = DayOfWeekConsistencyRule()
    ctx = _ctx(primary_weekday=None, monthly=[])  # No existing assignments
    result = rule.evaluate(ctx)
    assert result.score_delta == 0.0


def test_same_weekday_no_new_dispersion():
    """Reusing an existing weekday → no dispersion penalty."""
    rule = DayOfWeekConsistencyRule()
    ctx = _ctx(
        primary_weekday=2,  # Wednesday
        monthly=[
            {"doctor_id": "doc-1", "service_date": date(2026, 7, 8), "service_area_id": "emergencia"},  # Wednesday
        ],
    )
    result = rule.evaluate(ctx)
    # Slot is Wednesday (same) → no mismatch penalty, no dispersion
    assert result.score_delta == 0.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ctx(
    primary_weekday: int | None = None,
    day_priorities: dict[int, str] | None = None,
    monthly: list | None = None,
) -> RuleContext:
    return RuleContext(
        doctor_id="doc-1",
        slot_date=_SLOT,
        service_area_id="disponible",
        area_weight=1.0,
        monthly_assignments=monthly or [],
        historical_assignments=[],
        mission_assignments=[],
        monthly_count=len(monthly or []),
        monthly_service_target=3,
        monthly_service_max=3,
        allowed_area_ids=["disponible"],
        strong_area_ids={"emergencia", "pista"},
        area_weights={"emergencia": 3.0, "pista": 2.0, "disponible": 1.0},
        is_active=True,
        is_service_active=True,
        hard_block_active=False,
        has_availability=True,
        primary_weekday=primary_weekday,
        day_priorities=day_priorities or {},
    )
