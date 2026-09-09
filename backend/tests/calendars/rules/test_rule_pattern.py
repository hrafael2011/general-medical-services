from datetime import date

from backend.app.domain.calendars.rules.interface import RuleContext
from backend.app.domain.calendars.rules.rule_pattern import (
    PATTERN_PENALTY_CONSECUTIVE_STRONG,
    PATTERN_PENALTY_SAME_WEEK,
    PATTERN_PENALTY_TIER_MISMATCH,
    PatternRule,
)

_SLOT = date(2026, 7, 15)


def _ctx(**overrides) -> RuleContext:
    base = dict(
        doctor_id="doc-1",
        slot_date=_SLOT,
        service_area_id="emergencia",
        area_weight=3.0,
        monthly_assignments=[],
        historical_assignments=[],
        mission_assignments=[],
        monthly_count=1,
        monthly_service_target=3,
        monthly_service_max=3,
        allowed_area_ids=["emergencia", "pista", "disponible"],
        strong_area_ids={"emergencia", "pista"},
        area_weights={"emergencia": 3.0, "pista": 2.0, "disponible": 1.0},
        is_active=True,
        is_service_active=True,
        hard_block_active=False,
        has_availability=True,
        slot_week_number=1,
        weekly_assignments={},
    )
    base.update(overrides)
    return RuleContext(**base)


def test_tier_one_has_no_pattern_constraints() -> None:
    """Target 1 → sin penalidades de patrón."""
    result = PatternRule().evaluate(_ctx(monthly_service_target=1))
    assert result.score_delta == 0.0
    assert result.warnings == []


def test_same_week_second_service_penalized() -> None:
    """T2+: un segundo servicio en la misma semana penaliza."""
    ctx = _ctx(
        monthly_service_target=2,
        slot_week_number=2,
        weekly_assignments={2: [{"service_area_id": "disponible"}]},
    )
    result = PatternRule().evaluate(ctx)
    assert result.score_delta == -PATTERN_PENALTY_SAME_WEEK
    assert any("misma semana" in w for w in result.warnings)


def test_consecutive_strong_weeks_penalized() -> None:
    """Servicio fuerte en semana consecutiva a otro fuerte penaliza."""
    ctx = _ctx(
        monthly_service_target=2,
        slot_week_number=2,
        weekly_assignments={1: [{"service_area_id": "pista"}]},
    )
    result = PatternRule().evaluate(ctx)
    assert result.score_delta == -PATTERN_PENALTY_CONSECUTIVE_STRONG
    assert any("consecutivas" in w for w in result.warnings)


def test_clean_alternation_no_penalty() -> None:
    """T3 con alternancia limpia (semana previa no fuerte) no penaliza."""
    ctx = _ctx(
        monthly_service_target=3,
        slot_week_number=2,
        weekly_assignments={1: [{"service_area_id": "disponible"}]},
    )
    result = PatternRule().evaluate(ctx)
    assert result.score_delta == 0.0
    assert result.warnings == []


def test_t3_no_rest_week_penalized() -> None:
    """T3: si el slot llenaría las 4 semanas (sin descanso) penaliza."""
    ctx = _ctx(
        monthly_service_target=3,
        slot_week_number=4,
        weekly_assignments={
            1: [{"service_area_id": "emergencia"}],
            2: [{"service_area_id": "disponible"}],
            3: [{"service_area_id": "pista"}],
        },
    )
    result = PatternRule().evaluate(ctx)
    assert result.score_delta <= -PATTERN_PENALTY_TIER_MISMATCH


def test_prior_violations_add_fairness_penalty() -> None:
    """Violaciones previas del mes añaden penalidad proporcional."""
    ctx = _ctx(
        monthly_service_target=3,
        pattern_violations_count=2,
        weekly_assignments={},
    )
    result = PatternRule().evaluate(ctx)
    assert result.extra["pattern_penalty"] >= 2 * 5.0
    assert any("fuera de su patrón" in w for w in result.warnings)
