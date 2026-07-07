"""Tests for the Rule interface."""
from dataclasses import dataclass, field
from datetime import date
from backend.app.domain.calendars.rules.interface import Rule, RuleResult, RuleContext


def test_rule_result_defaults():
    """RuleResult defaults must be sensible — no violations, zero delta."""
    result = RuleResult(rule_name="test")
    assert result.rule_name == "test"
    assert result.score_delta == 0.0
    assert result.warnings == []
    assert result.is_blocking is False


def test_rule_context_has_required_fields():
    """RuleContext must carry all fields needed by any rule."""
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
    assert ctx.doctor_id == "doc-1"
    assert ctx.slot_date == date(2026, 7, 1)
    assert ctx.service_area_id == "emergencia"
