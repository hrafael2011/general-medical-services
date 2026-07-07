from datetime import date
from backend.app.domain.calendars.rules.rule_area_allowed import AreaAllowedRule
from backend.app.domain.calendars.rules.interface import RuleContext


def test_allowed_area_passes():
    rule = AreaAllowedRule()
    ctx = _ctx(service_area_id="emergencia", allowed=["emergencia", "pista"])
    result = rule.evaluate(ctx)
    assert result.is_blocking is False


def test_disallowed_area_blocks():
    rule = AreaAllowedRule()
    ctx = _ctx(service_area_id="disponible", allowed=["emergencia", "pista"])
    result = rule.evaluate(ctx)
    assert result.is_blocking is True


def _ctx(service_area_id: str, allowed: list[str]) -> RuleContext:
    return RuleContext(
        doctor_id="doc-1", slot_date=date(2026, 7, 1),
        service_area_id=service_area_id, area_weight=1.0,
        monthly_assignments=[], historical_assignments=[], mission_assignments=[],
        monthly_count=0, monthly_service_target=3, monthly_service_max=3,
        allowed_area_ids=allowed, strong_area_ids=set(),
        area_weights={}, is_active=True, is_service_active=True,
        hard_block_active=False, has_availability=True,
    )
