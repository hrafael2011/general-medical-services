"""
Calendar generation — load calculator and candidate scorer.

Pure domain logic: no SQLAlchemy, no DB access.
All inputs are pre-validated; hard-block filtering is done before calling
``compute_candidate_score``.
"""

from datetime import date

from backend.app.domain.calendars.types import CandidateScore, SlotRequest

# ---------------------------------------------------------------------------
# Weights / spacing constants
# ---------------------------------------------------------------------------

AREA_WEIGHTS: dict[str, float] = {
    "emergencia": 3.0,
    "pista": 2.0,
    "disponible": 1.0,
}

MISSION_WEIGHT = 0.5

STRONG_AREAS = {"emergencia", "pista"}

MIN_SPACING_STRONG = 14                     # days between strong-area services
MIN_SPACING_DISPONIBLE_AFTER_STRONG = 7    # days from strong service before disponible
MIN_SPACING_AFTER_MISSION_DISPONIBLE = 5   # days from mission before disponible
MIN_SPACING_AFTER_MISSION_STRONG = 7       # days from mission before strong-area service


# ---------------------------------------------------------------------------
# Public function
# ---------------------------------------------------------------------------


def compute_candidate_score(
    doctor_id: str,
    slot: SlotRequest,
    monthly_assignments: list[dict],
    historical_assignments: list[dict],
    mission_assignments: list[dict],
    monthly_service_target: int = 3,
) -> CandidateScore:
    """Compute a scheduling score for one doctor on one slot.

    Parameters
    ----------
    doctor_id:
        The doctor being evaluated.
    slot:
        The slot that needs to be filled (date + service_area_id).
    monthly_assignments:
        Assignments already placed in the month currently being generated.
        Each dict has keys: ``doctor_id``, ``service_date`` (date), ``service_area_id``.
    historical_assignments:
        Assignments from the preceding 60 days (outside the current month).
        Same dict shape as ``monthly_assignments``.
    mission_assignments:
        Mission assignments from the preceding 60 days.
        Each dict has keys: ``doctor_id``, ``mission_date`` (date).

    Returns
    -------
    CandidateScore
        All computed metrics plus the final score (higher = better candidate).
    """

    # ------------------------------------------------------------------
    # 1. Filter to this doctor only
    # ------------------------------------------------------------------
    doctor_monthly = [a for a in monthly_assignments if a["doctor_id"] == doctor_id]
    doctor_historical = [a for a in historical_assignments if a["doctor_id"] == doctor_id]
    doctor_missions = [m for m in mission_assignments if m["doctor_id"] == doctor_id]

    # ------------------------------------------------------------------
    # 2. Monthly load (weighted)
    # ------------------------------------------------------------------
    monthly_load: float = sum(
        AREA_WEIGHTS.get(a["service_area_id"], 1.0) for a in doctor_monthly
    )

    # ------------------------------------------------------------------
    # 3. Historical load (weighted assignments + mission weight)
    # ------------------------------------------------------------------
    historical_load: float = (
        sum(AREA_WEIGHTS.get(a["service_area_id"], 1.0) for a in doctor_historical)
        + len(doctor_missions) * MISSION_WEIGHT
    )

    # ------------------------------------------------------------------
    # 4. Monthly count
    # ------------------------------------------------------------------
    monthly_count: int = len(doctor_monthly)

    # ------------------------------------------------------------------
    # 5. Days since last service (any type)
    # ------------------------------------------------------------------
    all_service_dates: list[date] = [
        a["service_date"] for a in doctor_monthly + doctor_historical
    ]

    if all_service_dates:
        last_service_date = max(all_service_dates)
        days_since_last: int = max(0, (slot.date - last_service_date).days)
    else:
        days_since_last = 999

    # ------------------------------------------------------------------
    # 6. Days since last strong-area service
    # ------------------------------------------------------------------
    strong_service_dates: list[date] = [
        a["service_date"]
        for a in doctor_monthly + doctor_historical
        if a["service_area_id"] in STRONG_AREAS
    ]

    if strong_service_dates:
        last_strong_date = max(strong_service_dates)
        days_since_strong: int = max(0, (slot.date - last_strong_date).days)
    else:
        days_since_strong = 999

    # ------------------------------------------------------------------
    # 7. Last mission date
    # ------------------------------------------------------------------
    mission_dates: list[date] = [m["mission_date"] for m in doctor_missions]
    last_mission_date: date | None = max(mission_dates) if mission_dates else None

    # ------------------------------------------------------------------
    # 8. Spacing warnings (soft rule violations)
    # ------------------------------------------------------------------
    warnings: list[str] = []
    slot_area = slot.service_area_id

    # Strong-area spacing
    if slot_area in STRONG_AREAS:
        if days_since_strong < MIN_SPACING_STRONG:
            warnings.append("spacing < 14 días desde último turno fuerte")
    elif slot_area == "disponible":
        if days_since_strong < MIN_SPACING_DISPONIBLE_AFTER_STRONG:
            warnings.append("spacing < 7 días desde turno fuerte")

    # Mission-based spacing
    if last_mission_date is not None:
        days_since_mission = max(0, (slot.date - last_mission_date).days)
        if slot_area in STRONG_AREAS and days_since_mission < MIN_SPACING_AFTER_MISSION_STRONG:
            warnings.append("spacing < 7 días desde misión")
        elif slot_area == "disponible" and days_since_mission < MIN_SPACING_AFTER_MISSION_DISPONIBLE:
            warnings.append("spacing < 5 días desde misión")

    # ------------------------------------------------------------------
    # 9. Spacing violation flag (reserved for future strict mode)
    # ------------------------------------------------------------------
    is_spacing_violation: bool = len(warnings) > 0

    # ------------------------------------------------------------------
    # 10. Target-aware bonus (prefer doctors below their monthly target)
    # ------------------------------------------------------------------
    target_bonus: float = max(0, monthly_service_target - monthly_count) * 2

    # ------------------------------------------------------------------
    # 11. Area rotation bonus (prefer different area from last assignment)
    # ------------------------------------------------------------------
    area_penalty: float = 0.0
    if all_service_dates:
        # Most recent assignment (by date), then check its area
        last_assignment = max(
            doctor_monthly + doctor_historical,
            key=lambda a: a["service_date"],
        )
        if last_assignment["service_area_id"] == slot.service_area_id:
            area_penalty = 3.0  # small penalty for same area

    # ------------------------------------------------------------------
    # 12. Final score (higher = better)
    # ------------------------------------------------------------------
    score: float = (
        100.0
        - monthly_load * 10
        - historical_load * 3
        + min(days_since_last, 30) * 0.5
        + min(days_since_strong, 30) * 0.3
        - len(warnings) * 5
        + target_bonus
        - area_penalty
    )

    return CandidateScore(
        doctor_id=doctor_id,
        score=score,
        monthly_load=monthly_load,
        historical_load=historical_load,
        days_since_last=days_since_last,
        days_since_strong=days_since_strong,
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
) -> list[str]:
    """Return soft-rule warnings for a doctor+slot combination.

    Does NOT compute a full score. Only returns the warning strings
    that would be generated by ``compute_candidate_score`` for the
    same inputs.
    """
    result = compute_candidate_score(
        doctor_id=doctor_id,
        slot=slot,
        monthly_assignments=monthly_assignments,
        historical_assignments=historical_assignments,
        mission_assignments=mission_assignments,
    )
    return result.warnings
