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


def test_pipeline_scales_delta_by_rule_weight():
    """Rule.weight modula la contribución: una regla con weight=2 duplica su delta."""
    from backend.app.domain.calendars.rules.interface import Rule, RuleResult

    class WeightedRule(Rule):
        def __init__(self, weight: float, delta: float) -> None:
            super().__init__(name="weighted", is_hard=False, weight=weight)
            self._delta = delta

        def evaluate(self, ctx: RuleContext) -> RuleResult:
            return RuleResult(rule_name=self.name, score_delta=self._delta)

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
    single = RulePipeline([WeightedRule(weight=1.0, delta=-10.0)]).evaluate(ctx)
    assert single.total_score == 100.0 - 10.0

    doubled = RulePipeline([WeightedRule(weight=2.0, delta=-10.0)]).evaluate(ctx)
    assert doubled.total_score == 100.0 - 20.0


def test_pipeline_hard_rules_only_filter():
    """build_pipeline(hard_rules_only=True) should only return hard rules."""
    rules = build_pipeline(hard_rules_only=True)
    assert all(r.is_hard for r in rules)
    assert len(rules) == 4  # active, area_allowed, hard_block, availability


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
