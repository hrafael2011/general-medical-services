from datetime import date
from backend.app.domain.calendars.rules.rule_availability import AvailabilityRule
from backend.app.domain.calendars.rules.interface import RuleContext


def test_has_availability_passes():
    rule = AvailabilityRule()
    ctx = _ctx(has_availability=True)
    result = rule.evaluate(ctx)
    assert result.is_blocking is False


def test_no_availability_blocks():
    rule = AvailabilityRule()
    ctx = _ctx(has_availability=False)
    result = rule.evaluate(ctx)
    assert result.is_blocking is True


def _ctx(has_availability: bool) -> RuleContext:
    return RuleContext(
        doctor_id="doc-1", slot_date=date(2026, 7, 1),
        service_area_id="emergencia", area_weight=3.0,
        monthly_assignments=[], historical_assignments=[], mission_assignments=[],
        monthly_count=0, monthly_service_target=3, monthly_service_max=3,
        allowed_area_ids=["emergencia"], strong_area_ids={"emergencia"},
        area_weights={"emergencia": 3.0},
        is_active=True, is_service_active=True,
        hard_block_active=False, has_availability=has_availability,
    )
