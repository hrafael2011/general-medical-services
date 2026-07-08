# backend/app/domain/calendars/rules/interface.py
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass
class RuleResult:
    """Resultado de evaluar una regla para un doctor+slot."""
    rule_name: str
    score_delta: float = 0.0          # penalización (negativo) o bonificación (positivo)
    warnings: list[str] = field(default_factory=list)
    is_blocking: bool = False         # True = hard block, doctor no elegible
    extra: dict[str, Any] = field(default_factory=dict)  # datos adicionales


@dataclass
class RuleContext:
    """Contexto completo para evaluar todas las reglas en un doctor+slot.

    The pattern-related fields (slot_week_number, weekly_assignments,
    pattern_violations_count) are optional and only used by PatternRule.
    If not provided, PatternRule assumes no pattern applies.

    Note: monthly_count is a convenience field and MUST equal
    len(monthly_assignments) for the caller's doctor_id.
    """
    doctor_id: str
    slot_date: date
    service_area_id: str
    area_weight: float
    monthly_assignments: list[dict]
    historical_assignments: list[dict]
    mission_assignments: list[dict]
    monthly_count: int
    monthly_service_target: int
    monthly_service_max: int
    allowed_area_ids: list[str]
    strong_area_ids: set[str]
    area_weights: dict[str, float]
    is_active: bool
    is_service_active: bool
    hard_block_active: bool
    has_availability: bool

    # Pattern rule fields (optional — default to no pattern)
    slot_week_number: int = 1
    weekly_assignments: dict[int, list[dict]] = field(default_factory=dict)
    pattern_violations_count: int = 0

    # Availability priority: True if the doctor submitted availability records
    # for this month. Used by AvailabilityPriorityRule to prefer doctors who
    # proactively submit their dates.
    submitted_availability: bool = False


class Rule(ABC):
    """Base class for all fairness/eligibility rules.

    ``is_hard`` (class attribute) indicates the rule TYPE: hard rules block
    ineligibility, soft rules contribute score deltas. ``is_blocking`` on
    the returned ``RuleResult`` indicates the EVALUATION OUTCOME for this
    specific call.
    """

    def __init__(self, name: str, is_hard: bool, weight: float = 1.0):
        self.name = name
        self.is_hard = is_hard
        self.weight = weight

    @abstractmethod
    def evaluate(self, ctx: RuleContext) -> RuleResult:
        """Evaluate this rule for a doctor+slot combination.

        Returns a RuleResult with score_delta (negative = penalty, positive = bonus),
        warnings (soft violations), and is_blocking (hard violation).
        """
        ...
