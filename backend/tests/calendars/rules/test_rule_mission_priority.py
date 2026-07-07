from datetime import date, timedelta
from backend.app.domain.calendars.rules.rule_mission_priority import MissionPriorityRule
from backend.app.domain.calendars.rules.interface import RuleContext

_SLOT = date(2026, 7, 15)


def test_no_missions_no_effect():
    rule = MissionPriorityRule()
    ctx = _ctx(missions=[])
    result = rule.evaluate(ctx)
    assert result.score_delta == 0.0


def test_recent_mission_reduces_priority():
    rule = MissionPriorityRule()
    ctx = _ctx(missions=[{"doctor_id":"doc-1","mission_date":_SLOT - timedelta(days=2)}])
    result = rule.evaluate(ctx)
    # 14 - 2 = 12 days penalty → -12.0
    assert result.score_delta == -12.0


def test_mission_at_penalty_threshold():
    """Mission exactly 14 days ago has no penalty."""
    rule = MissionPriorityRule()
    ctx = _ctx(missions=[{"doctor_id":"doc-1","mission_date":_SLOT - timedelta(days=14)}])
    result = rule.evaluate(ctx)
    assert result.score_delta == 0.0


def test_mission_beyond_threshold():
    """Mission more than 14 days ago has no penalty."""
    rule = MissionPriorityRule()
    ctx = _ctx(missions=[{"doctor_id":"doc-1","mission_date":_SLOT - timedelta(days=20)}])
    result = rule.evaluate(ctx)
    assert result.score_delta == 0.0


def test_only_own_missions_count():
    """Only missions for the evaluated doctor affect the score."""
    rule = MissionPriorityRule()
    ctx = _ctx(missions=[
        {"doctor_id":"doc-1","mission_date":_SLOT - timedelta(days=2)},
        {"doctor_id":"doc-2","mission_date":_SLOT - timedelta(days=3)},
    ])
    result = rule.evaluate(ctx)
    # doc-1: 14 - 2 = 12 days penalty → -12.0
    # doc-2's mission should be ignored
    assert result.score_delta == -12.0


def _ctx(missions: list) -> RuleContext:
    return RuleContext(
        doctor_id="doc-1", slot_date=_SLOT,
        service_area_id="emergencia", area_weight=3.0,
        monthly_assignments=[], historical_assignments=[], mission_assignments=missions,
        monthly_count=0, monthly_service_target=3, monthly_service_max=3,
        allowed_area_ids=["emergencia"], strong_area_ids={"emergencia"},
        area_weights={"emergencia": 3.0},
        is_active=True, is_service_active=True,
        hard_block_active=False, has_availability=True,
    )
