"""
Calendar generation — load calculator and candidate scorer.

Now delegates to RulePipeline internally while preserving the exact
same output as the original implementation.
"""

from backend.app.domain.calendars.types import CandidateScore, SlotRequest

# ---------------------------------------------------------------------------
# Weights / spacing constants (kept for external consumers)
# ---------------------------------------------------------------------------

AREA_WEIGHTS: dict[str, float] = {
    "emergencia": 3.0,
    "pista": 2.0,
    "disponible": 1.0,
}

MISSION_WEIGHT = 0.5

STRONG_AREAS = {"emergencia", "pista"}

MIN_SPACING_STRONG = 14
MIN_SPACING_DISPONIBLE_AFTER_STRONG = 7
MIN_SPACING_AFTER_MISSION_DISPONIBLE = 5
MIN_SPACING_AFTER_MISSION_STRONG = 7


# ---------------------------------------------------------------------------
# Public function — delegates to RulePipeline
# ---------------------------------------------------------------------------


def compute_candidate_score(
    doctor_id: str,
    slot: SlotRequest,
    monthly_assignments: list[dict],
    historical_assignments: list[dict],
    mission_assignments: list[dict],
    monthly_service_target: int = 3,
    area_weights: dict[str, float] | None = None,
    strong_area_ids: set[str] | None = None,
) -> CandidateScore:
    """Compute a scheduling score for one doctor on one slot.

    Now delegates to RulePipeline internally.
    Same signature, same return type, same numeric output.
    """
    # Lazy imports to avoid circular dependency
    # (rule_load_balancing imports AREA_WEIGHTS/MISSION_WEIGHT from this module)
    from backend.app.domain.calendars.rules import build_pipeline
    from backend.app.domain.calendars.rules.rule_pipeline import RulePipeline
    from backend.app.domain.calendars.rules.interface import RuleContext

    weights = area_weights or AREA_WEIGHTS
    strong_areas = strong_area_ids or STRONG_AREAS

    # Pre-compute monthly count for this doctor
    monthly_count = len([
        a for a in monthly_assignments if a["doctor_id"] == doctor_id
    ])

    # Build RuleContext
    ctx = RuleContext(
        doctor_id=doctor_id,
        slot_date=slot.date,
        service_area_id=slot.service_area_id,
        area_weight=slot.area_weight,
        monthly_assignments=monthly_assignments,
        historical_assignments=historical_assignments,
        mission_assignments=mission_assignments,
        monthly_count=monthly_count,
        monthly_service_target=monthly_service_target,
        monthly_service_max=999,  # engine handles max separately
        allowed_area_ids=[slot.service_area_id],  # hard filters applied before scoring
        strong_area_ids=strong_areas,
        area_weights=weights,
        is_active=True,
        is_service_active=True,
        hard_block_active=False,
        has_availability=True,
    )

    pipeline = RulePipeline(build_pipeline(hard_rules_only=False))
    result = pipeline.evaluate(ctx)

    warnings = result.all_warnings
    is_spacing_violation = any(
        "spacing" in w.lower() for w in warnings
    )

    # Build CandidateScore with exact same fields as original
    return CandidateScore(
        doctor_id=doctor_id,
        score=result.total_score,
        monthly_load=result.monthly_load,
        historical_load=result.historical_load,
        days_since_last=result.days_since_last,
        days_since_strong=result.days_since_strong,
        monthly_count=monthly_count,
        warnings=warnings,
        is_spacing_violation=is_spacing_violation,
    )


# ---------------------------------------------------------------------------
# Public evaluation function (used by evaluate endpoint)
# ---------------------------------------------------------------------------


def evaluate_soft_warnings(
    doctor_id: str,
    slot: SlotRequest,
    monthly_assignments: list[dict],
    historical_assignments: list[dict],
    mission_assignments: list[dict],
    area_weights: dict[str, float] | None = None,
    strong_area_ids: set[str] | None = None,
) -> list[str]:
    """Return soft-rule warnings for a doctor+slot combination.

    Does NOT compute a full score. Only returns the warning strings.
    """
    result = compute_candidate_score(
        doctor_id=doctor_id,
        slot=slot,
        monthly_assignments=monthly_assignments,
        historical_assignments=historical_assignments,
        mission_assignments=mission_assignments,
        area_weights=area_weights,
        strong_area_ids=strong_area_ids,
    )
    return result.warnings
