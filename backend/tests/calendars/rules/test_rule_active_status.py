from datetime import date
from backend.app.domain.calendars.rules.rule_active_status import ActiveStatusRule
from backend.app.domain.calendars.rules.interface import RuleContext


def test_active_doctor_passes():
    rule = ActiveStatusRule()
    ctx = _ctx(is_active=True, is_service_active=True)
    result = rule.evaluate(ctx)
    assert result.is_blocking is False
    assert result.score_delta == 0.0


def test_inactive_doctor_blocks():
    rule = ActiveStatusRule()
    ctx = _ctx(is_active=False, is_service_active=True)
    result = rule.evaluate(ctx)
    assert result.is_blocking is True
    assert result.score_delta < 0


def test_service_inactive_blocks():
    rule = ActiveStatusRule()
    ctx = _ctx(is_active=True, is_service_active=False)
    result = rule.evaluate(ctx)
    assert result.is_blocking is True


def _ctx(is_active: bool, is_service_active: bool) -> RuleContext:
    return RuleContext(
        doctor_id="doc-1", slot_date=date(2026, 7, 1),
        service_area_id="emergencia", area_weight=3.0,
        monthly_assignments=[], historical_assignments=[], mission_assignments=[],
        monthly_count=0, monthly_service_target=3, monthly_service_max=3,
        allowed_area_ids=["emergencia"], strong_area_ids={"emergencia"},
        area_weights={"emergencia": 3.0},
        is_active=is_active, is_service_active=is_service_active,
        hard_block_active=False, has_availability=True,
    )
