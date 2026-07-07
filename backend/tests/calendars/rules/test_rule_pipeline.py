from datetime import date

from backend.app.domain.calendars.rules.rule_pipeline import RulePipeline, PipelineResult
from backend.app.domain.calendars.rules.interface import RuleContext
from backend.app.domain.calendars.rules import build_pipeline

_SLOT = date(2026, 7, 15)


def test_pipeline_aggregates_all_rules():
    """Pipeline with all rules should produce a final score."""
    pipeline = RulePipeline(build_pipeline())
    ctx = RuleContext(
        doctor_id="doc-1", slot_date=_SLOT,
        service_area_id="disponible", area_weight=1.0,
        monthly_assignments=[], historical_assignments=[], mission_assignments=[],
        monthly_count=0, monthly_service_target=3, monthly_service_max=3,
        allowed_area_ids=["emergencia", "pista", "disponible"],
        strong_area_ids={"emergencia", "pista"},
        area_weights={"emergencia": 3.0, "pista": 2.0, "disponible": 1.0},
        is_active=True, is_service_active=True,
        hard_block_active=False, has_availability=True,
    )
    result = pipeline.evaluate(ctx)
    assert result.total_score >= 0  # base 100 + bonuses
    assert len(result.results) > 0
    assert result.is_eligible is True


def test_pipeline_blocks_on_hard_rule():
    """Pipeline must set is_eligible=False when a hard rule blocks."""
    pipeline = RulePipeline(build_pipeline())
    ctx = RuleContext(
        doctor_id="doc-1", slot_date=_SLOT,
        service_area_id="disponible", area_weight=1.0,
        monthly_assignments=[], historical_assignments=[], mission_assignments=[],
        monthly_count=0, monthly_service_target=3, monthly_service_max=3,
        allowed_area_ids=["emergencia", "pista"],  # disponible NOT allowed
        strong_area_ids={"emergencia", "pista"},
        area_weights={"emergencia": 3.0, "pista": 2.0, "disponible": 1.0},
        is_active=True, is_service_active=True,
        hard_block_active=False, has_availability=True,
    )
    result = pipeline.evaluate(ctx)
    assert result.is_eligible is False


def test_pipeline_hard_rules_only_filter():
    """build_pipeline(hard_rules_only=True) should only return hard rules."""
    rules = build_pipeline(hard_rules_only=True)
    assert all(r.is_hard for r in rules)
    assert len(rules) == 5  # active, area_allowed, hard_block, availability, monthly_limit


def test_pipeline_returns_pipeline_result_type():
    """Pipeline must return a PipelineResult, not a plain dict."""
    pipeline = RulePipeline(build_pipeline(hard_rules_only=True))
    ctx = RuleContext(
        doctor_id="doc-1", slot_date=_SLOT,
        service_area_id="disponible", area_weight=1.0,
        monthly_assignments=[], historical_assignments=[], mission_assignments=[],
        monthly_count=0, monthly_service_target=3, monthly_service_max=3,
        allowed_area_ids=["disponible"],
        strong_area_ids=set(),
        area_weights={},
        is_active=True, is_service_active=True,
        hard_block_active=False, has_availability=True,
    )
    result = pipeline.evaluate(ctx)
    assert isinstance(result, PipelineResult)
    assert result.is_eligible is True
    assert result.total_score > 0
