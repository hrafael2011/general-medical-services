"""Tests for the Rule interface."""
from dataclasses import dataclass, field
from datetime import date
from backend.app.domain.calendars.rules.interface import Rule, RuleResult, RuleContext


# ---------------------------------------------------------------------------
# Concrete subclass for testing the ABC contract
# ---------------------------------------------------------------------------


class _ConcreteRule(Rule):
    """Minimal concrete rule used to verify the ABC machinery works."""

    def __init__(self, name: str = "test-rule", is_hard: bool = False):
        super().__init__(name=name, is_hard=is_hard)

    def evaluate(self, ctx: RuleContext) -> RuleResult:
        return RuleResult(rule_name=self.name, score_delta=-5.0, warnings=["test"])


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_rule_abc_can_be_subclassed():
    """The ABC must allow concrete subclasses with a working evaluate()."""
    rule = _ConcreteRule(name="dummy", is_hard=True)
    assert rule.name == "dummy"
    assert rule.is_hard is True
    assert rule.weight == 1.0
    ctx = _minimal_ctx()
    result = rule.evaluate(ctx)
    assert isinstance(result, RuleResult)
    assert result.rule_name == "dummy"
    assert result.score_delta == -5.0
    assert result.warnings == ["test"]
    assert result.is_blocking is False


def test_rule_result_defaults():
    """RuleResult defaults must be sensible — no violations, zero delta."""
    result = RuleResult(rule_name="test")
    assert result.rule_name == "test"
    assert result.score_delta == 0.0
    assert result.warnings == []
    assert result.is_blocking is False


def test_rule_context_constructs_with_all_fields():
    """RuleContext must accept all 17 fields without error."""
    ctx = RuleContext(
        doctor_id="doc-1",
        slot_date=date(2026, 7, 1),
        service_area_id="emergencia",
        area_weight=3.0,
        monthly_assignments=[],
        historical_assignments=[],
        mission_assignments=[],
        monthly_count=0,
        monthly_service_target=3,
        monthly_service_max=3,
        allowed_area_ids=["emergencia", "pista", "disponible"],
        strong_area_ids={"emergencia", "pista"},
        area_weights={"emergencia": 3.0, "pista": 2.0, "disponible": 1.0},
        is_active=True,
        is_service_active=True,
        hard_block_active=False,
        has_availability=True,
    )
    # Verify a representative subset of fields are accessible
    assert ctx.doctor_id == "doc-1"
    assert ctx.slot_date == date(2026, 7, 1)
    assert ctx.service_area_id == "emergencia"
    assert ctx.area_weight == 3.0
    assert ctx.monthly_count == 0
    assert ctx.is_active is True
    assert ctx.has_availability is True


def _minimal_ctx(**overrides: bool) -> RuleContext:
    """Return a minimal RuleContext for use in ABC contract tests."""
    kwargs = dict(
        doctor_id="doc-1",
        slot_date=date(2026, 7, 1),
        service_area_id="disponible",
        area_weight=1.0,
        monthly_assignments=[],
        historical_assignments=[],
        mission_assignments=[],
        monthly_count=0,
        monthly_service_target=3,
        monthly_service_max=3,
        allowed_area_ids=["disponible"],
        strong_area_ids=set(),
        area_weights={},
        is_active=True,
        is_service_active=True,
        hard_block_active=False,
        has_availability=True,
    )
    kwargs.update(overrides)
    return RuleContext(**kwargs)
