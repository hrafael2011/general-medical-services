from datetime import date, timedelta
from backend.app.domain.calendars.rules.rule_area_rotation import AreaRotationRule
from backend.app.domain.calendars.rules.interface import RuleContext

_SLOT = date(2026, 7, 15)


def test_different_area_no_penalty():
    rule = AreaRotationRule()
    ctx = _ctx(service_area_id="emergencia", last_area="disponible")
    result = rule.evaluate(ctx)
    assert result.score_delta == 0.0


def test_same_area_penalty():
    rule = AreaRotationRule()
    ctx = _ctx(service_area_id="emergencia", last_area="emergencia")
    result = rule.evaluate(ctx)
    assert result.score_delta == -3.0


def _ctx(service_area_id: str, last_area: str) -> RuleContext:
    last_week = _SLOT - timedelta(days=7)
    return RuleContext(
        doctor_id="doc-1", slot_date=_SLOT,
        service_area_id=service_area_id, area_weight=3.0,
        monthly_assignments=[{"doctor_id": "doc-1", "service_date": last_week, "service_area_id": last_area}],
        historical_assignments=[], mission_assignments=[],
        monthly_count=1, monthly_service_target=3, monthly_service_max=3,
        allowed_area_ids=["emergencia", "pista", "disponible"],
        strong_area_ids={"emergencia", "pista"},
        area_weights={"emergencia": 3.0, "pista": 2.0, "disponible": 1.0},
        is_active=True, is_service_active=True,
        hard_block_active=False, has_availability=True,
    )
