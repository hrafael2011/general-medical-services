from datetime import date, timedelta
from backend.app.domain.calendars.rules.rule_load_balancing import LoadBalancingRule
from backend.app.domain.calendars.rules.interface import RuleContext

_SLOT = date(2026, 7, 15)
_WEIGHTS = {"emergencia": 3.0, "pista": 2.0, "disponible": 1.0}


def test_no_load_zero_penalty():
    rule = LoadBalancingRule()
    ctx = _ctx(monthly=[], historical=[], missions=[])
    result = rule.evaluate(ctx)
    assert result.score_delta == 0.0


def test_monthly_load_penalty():
    rule = LoadBalancingRule()
    monthly = [
        {"doctor_id":"doc-1","service_date": _SLOT - timedelta(days=d), "service_area_id":"emergencia"}
        for d in [1, 5, 9]
    ]
    ctx = _ctx(monthly=monthly)
    result = rule.evaluate(ctx)
    # monthly_load = 3 * 3.0 = 9.0 -> penalty = 9 * 10 = -90
    assert result.score_delta == -90.0


def test_historical_load_plus_missions():
    rule = LoadBalancingRule()
    hist = [{"doctor_id":"doc-1","service_date":_SLOT-timedelta(days=d),"service_area_id":"pista"} for d in [35, 40]]
    missions = [{"doctor_id":"doc-1","mission_date":_SLOT-timedelta(days=20)}]
    ctx = _ctx(monthly=[], historical=hist, missions=missions)
    result = rule.evaluate(ctx)
    # historical_load = 2 * 2.0 + 1 * 0.5 = 4.5 -> penalty = 4.5 * 3 = -13.5
    assert result.score_delta == -13.5


def _ctx(monthly=None, historical=None, missions=None):
    monthly = monthly or []
    historical = historical or []
    return RuleContext(
        doctor_id="doc-1", slot_date=_SLOT,
        service_area_id="disponible", area_weight=1.0,
        monthly_assignments=monthly,
        historical_assignments=historical,
        mission_assignments=missions or [],
        monthly_count=len(monthly),
        monthly_service_target=3, monthly_service_max=3,
        allowed_area_ids=list(_WEIGHTS.keys()),
        strong_area_ids={"emergencia","pista"},
        area_weights=_WEIGHTS,
        is_active=True, is_service_active=True,
        hard_block_active=False, has_availability=True,
    )
