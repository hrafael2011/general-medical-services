from datetime import date, timedelta
from backend.app.domain.calendars.rules.rule_spacing import SpacingRule
from backend.app.domain.calendars.rules.interface import RuleContext

_SLOT_DATE = date(2026, 7, 15)


def test_no_recent_service_no_warnings():
    rule = SpacingRule()
    ctx = _ctx(monthly=[], historical=[])
    result = rule.evaluate(ctx)
    assert result.warnings == []
    # Sin historial → days_since_last=999, days_since_strong=999
    # bonus = min(999,30)*0.5 + min(999,30)*0.3 = 15.0 + 9.0 = 24.0
    assert result.score_delta == 24.0


def test_strong_service_5_days_ago_warning_on_strong_slot():
    rule = SpacingRule()
    last = _SLOT_DATE - timedelta(days=5)
    ctx = _ctx(
        service_area_id="emergencia",
        monthly=[{"doctor_id": "doc-1", "service_date": last, "service_area_id": "emergencia"}],
    )
    result = rule.evaluate(ctx)
    assert any("14" in w for w in result.warnings)
    # rest_bonus=5*0.5=2.5 + strong_bonus=5*0.3=1.5 - warning_penalty=5.0 = -1.0
    assert result.score_delta == -1.0


def test_strong_service_3_days_ago_warning_on_disponible():
    rule = SpacingRule()
    last = _SLOT_DATE - timedelta(days=3)
    ctx = _ctx(
        service_area_id="disponible",
        monthly=[{"doctor_id": "doc-1", "service_date": last, "service_area_id": "emergencia"}],
    )
    result = rule.evaluate(ctx)
    assert any("7" in w for w in result.warnings)
    # rest_bonus=3*0.5=1.5 + strong_bonus=3*0.3=0.9 - warning_penalty=5.0 = -2.6
    assert result.score_delta == -2.6


def test_mission_3_days_ago_warning_on_strong():
    rule = SpacingRule()
    ctx = _ctx(
        service_area_id="emergencia",
        missions=[{"doctor_id": "doc-1", "mission_date": _SLOT_DATE - timedelta(days=3)}],
    )
    result = rule.evaluate(ctx)
    assert any("misión" in w for w in result.warnings)


def test_days_since_strong_bonus():
    rule = SpacingRule()
    last = _SLOT_DATE - timedelta(days=20)
    ctx = _ctx(
        service_area_id="disponible",
        monthly=[{"doctor_id": "doc-1", "service_date": last, "service_area_id": "pista"}],
    )
    result = rule.evaluate(ctx)
    # days_since_strong=20 -> 20*0.3 = 6.0; days_since_last=20 -> 20*0.5 = 10.0
    # No warnings since 20 >= 7 -> total bonus = 16.0
    assert result.score_delta == 16.0


def _ctx(service_area_id="disponible", monthly=None, historical=None, missions=None):
    return RuleContext(
        doctor_id="doc-1", slot_date=_SLOT_DATE,
        service_area_id=service_area_id, area_weight=1.0,
        monthly_assignments=monthly or [],
        historical_assignments=historical or [],
        mission_assignments=missions or [],
        monthly_count=len(monthly or []),
        monthly_service_target=3, monthly_service_max=3,
        allowed_area_ids=["emergencia", "pista", "disponible"],
        strong_area_ids={"emergencia", "pista"},
        area_weights={"emergencia": 3.0, "pista": 2.0, "disponible": 1.0},
        is_active=True, is_service_active=True,
        hard_block_active=False, has_availability=True,
    )
