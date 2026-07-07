from datetime import date
from backend.app.domain.calendars.rules.rule_monthly_limit import MonthlyLimitRule
from backend.app.domain.calendars.rules.interface import RuleContext


def test_below_max_passes_and_gives_target_bonus():
    rule = MonthlyLimitRule()
    ctx = _ctx(monthly_count=1, target=3, max_val=3)
    result = rule.evaluate(ctx)
    assert result.is_blocking is False
    # 2 below target → bonus = 2 * 2 = 4
    assert result.score_delta == 4.0


def test_at_target_gives_zero_bonus():
    rule = MonthlyLimitRule()
    # count == target but below max → bonus should be 0
    ctx = _ctx(monthly_count=3, target=3, max_val=5)
    result = rule.evaluate(ctx)
    assert result.score_delta == 0.0


def test_at_max_blocks():
    rule = MonthlyLimitRule()
    ctx = _ctx(monthly_count=3, target=3, max_val=3)
    result = rule.evaluate(ctx)
    assert result.is_blocking is True


def test_below_max_not_blocking():
    rule = MonthlyLimitRule()
    ctx = _ctx(monthly_count=2, target=3, max_val=3)
    result = rule.evaluate(ctx)
    assert result.is_blocking is False


def _ctx(monthly_count: int, target: int, max_val: int) -> RuleContext:
    return RuleContext(
        doctor_id="doc-1", slot_date=date(2026, 7, 1),
        service_area_id="disponible", area_weight=1.0,
        monthly_assignments=[], historical_assignments=[], mission_assignments=[],
        monthly_count=monthly_count, monthly_service_target=target, monthly_service_max=max_val,
        allowed_area_ids=["disponible"], strong_area_ids=set(),
        area_weights={}, is_active=True, is_service_active=True,
        hard_block_active=False, has_availability=True,
    )
