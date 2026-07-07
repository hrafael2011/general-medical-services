from datetime import date
from backend.app.domain.calendars.rules.rule_coverage import CoverageRule
from backend.app.domain.calendars.rules.interface import RuleContext


def test_coverage_noop_in_scoring():
    """CoverageRule must not affect scoring (engine handles gaps)."""
    rule = CoverageRule()
    ctx = RuleContext(
        doctor_id="doc-1", slot_date=date(2026, 7, 1),
        service_area_id="emergencia", area_weight=3.0,
        monthly_assignments=[], historical_assignments=[], mission_assignments=[],
        monthly_count=0, monthly_service_target=3, monthly_service_max=3,
        allowed_area_ids=["emergencia"], strong_area_ids={"emergencia"},
        area_weights={"emergencia": 3.0},
        is_active=True, is_service_active=True,
        hard_block_active=False, has_availability=True,
    )
    result = rule.evaluate(ctx)
    assert result.score_delta == 0.0
    assert result.warnings == []
    assert result.is_blocking is False
