"""PatternRule — enforce weekly assignment patterns per tier.

Tier is derived from monthly_service_target:

    target >= 4  → T4  (4 assignments, strong-disponible alternation)
    target == 3  → T3  (3 assignments, 2 strong + 1 disponible + 1 rest)
    target == 2  → T2  (2 assignments, one week gap between them)
    target == 1  → T1  (no pattern constraints)

This is a SOFT rule: violations never block, only penalise and warn.
The penalty is tuned so that GAP_PENALTY (10k) ≫ pattern penalty (500)
in the CP-SAT objective, ensuring the solver never leaves a gap to
satisfy a pattern when a violation is the alternative.

Fairness tracker — if a doctor has accumulated pattern violations
(ctx.pattern_violations_count), an extra penalty is applied so that
doctors with fewer prior violations are preferred when a violation
is unavoidable.
"""
from backend.app.domain.calendars.rules.interface import Rule, RuleContext, RuleResult

PATTERN_PENALTY_SAME_WEEK = 30.0
PATTERN_PENALTY_CONSECUTIVE_STRONG = 40.0
PATTERN_PENALTY_TIER_MISMATCH = 20.0
PATTERN_PENALTY_PER_PRIOR_VIOLATION = 5.0


class PatternRule(Rule):
    """Soft rule: enforce weekly assignment tier patterns."""

    def __init__(self):
        super().__init__(name="pattern", is_hard=False, weight=1.0)

    def evaluate(self, ctx: RuleContext) -> RuleResult:
        tier = self._get_tier(ctx)
        if tier <= 1:
            return RuleResult(rule_name=self.name)

        warnings: list[str] = []
        penalty = 0.0

        # --- Constraint 1: max 1 service per week (T2-T4) ---
        existing_this_week = [
            a for a in ctx.weekly_assignments.get(ctx.slot_week_number, [])
        ]
        if existing_this_week:
            penalty += PATTERN_PENALTY_SAME_WEEK
            warnings.append("Pattern: más de 1 servicio en la misma semana")

        # --- Constraint 2: no consecutive strong weeks (T2-T4) ---
        is_strong = ctx.service_area_id in ctx.strong_area_ids
        if is_strong:
            prev_week = ctx.weekly_assignments.get(ctx.slot_week_number - 1, [])
            if any(a["service_area_id"] in ctx.strong_area_ids for a in prev_week):
                penalty += PATTERN_PENALTY_CONSECUTIVE_STRONG
                warnings.append("Pattern: servicios fuertes en semanas consecutivas")

            next_week = ctx.weekly_assignments.get(ctx.slot_week_number + 1, [])
            if any(a["service_area_id"] in ctx.strong_area_ids for a in next_week):
                penalty += PATTERN_PENALTY_CONSECUTIVE_STRONG
                warnings.append("Pattern: servicios fuertes en semanas consecutivas")

        # --- Constraint 3: weekly cadence by tier ---
        if tier == 2:
            penalty += self._check_t2_cadence(ctx)

        elif tier == 3:
            penalty += self._check_t3_cadence(ctx)

        elif tier >= 4:
            penalty += self._check_t4_cadence(ctx)

        # --- Fairness tracker: prefer doctors with fewer prior violations ---
        if ctx.pattern_violations_count > 0:
            penalty += ctx.pattern_violations_count * PATTERN_PENALTY_PER_PRIOR_VIOLATION
            if ctx.pattern_violations_count > 0:
                warnings.append(
                    f"Pattern: {ctx.pattern_violations_count} violación(es) previa(s) en el mes"
                )

        return RuleResult(
            rule_name=self.name,
            score_delta=-penalty if penalty else 0.0,
            warnings=warnings,
            extra={"tier": tier, "pattern_penalty": penalty},
        )

    # ------------------------------------------------------------------
    # Tier helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_tier(ctx: RuleContext) -> int:
        target = ctx.monthly_service_target
        if target >= 4:
            return 4
        if target < 1:
            return 1
        return target

    def _check_t2_cadence(self, ctx: RuleContext) -> float:
        """T2: assignments on alternating weeks (gap every other week).

        Penalty if the slot would create a 2-week-in-a-row pattern.
        """
        current = ctx.slot_week_number
        assigned_weeks = set(ctx.weekly_assignments.keys())

        # Check immediate neighbours
        for neighbour in (current - 1, current + 1):
            if neighbour in assigned_weeks:
                # Also check if the other neighbour is empty → it's ok
                other = current + (current - neighbour)  # 1 away from neighbour
                if other not in assigned_weeks and neighbour not in (current, other):
                    # Two in a row with a gap beyond → ok
                    continue
                # If this creates 3+ in 4 weeks or back-to-back, penalise
                expected_2_week_gap = any(
                    w not in assigned_weeks
                    for w in range(1, 5)
                    if w != current and w != neighbour
                )
                if not expected_2_week_gap:
                    return PATTERN_PENALTY_TIER_MISMATCH
        return 0.0

    def _check_t3_cadence(self, ctx: RuleContext) -> float:
        """T3: exactly 3 assignments in 4 weeks with a rest after strong.

        Penalty if:
        - All 4 weeks would be filled (no rest week)
        - This strong service has another strong in the same gap-separated
          position without a rest between them.
        """
        assigned_weeks = set(ctx.weekly_assignments.keys())
        current = ctx.slot_week_number
        # Simulate adding this slot
        simulated = set(assigned_weeks)
        simulated.add(current)
        simulated_count = len(simulated)

        if simulated_count >= 4:
            return PATTERN_PENALTY_TIER_MISMATCH  # no rest week

        # Check: a rest week should follow a strong service
        if ctx.service_area_id in ctx.strong_area_ids:
            # If next week has any assignment, it MUST NOT be another strong
            next_assignments = ctx.weekly_assignments.get(current + 1, [])
            if any(a["service_area_id"] in ctx.strong_area_ids for a in next_assignments):
                return PATTERN_PENALTY_CONSECUTIVE_STRONG

        return 0.0

    def _check_t4_cadence(self, ctx: RuleContext) -> float:
        """T4: exactly 4 assignments in 4 weeks, no consecutive strong.

        Penalty if any week would be empty (simulated count < 4) OR
        there are already 4 assignments and this would be a 5th.
        """
        assigned_weeks = set(ctx.weekly_assignments.keys())
        current = ctx.slot_week_number
        simulated = set(assigned_weeks)
        simulated.add(current)
        simulated_count = len(simulated)

        total_services = sum(len(v) for v in ctx.weekly_assignments.values())

        if simulated_count < 4 and current not in assigned_weeks:
            # This fills a previously empty week — good, no penalty
            pass
        elif simulated_count == 4 and current in assigned_weeks:
            # Every week already filled → this is a 5th (overfill) or duplicate
            if total_services >= 4:
                return PATTERN_PENALTY_SAME_WEEK * 2

        # Check if this slot would create a gap week that should be filled
        if current not in assigned_weeks:
            # This slot fills the current week — check if any OTHER week would
            # still be empty after adding this one
            empty_weeks = [w for w in range(1, 5) if w not in simulated]
            if empty_weeks and total_services + 1 >= 4:
                # We'd miss a week → penalise proportional to how many empty
                return PATTERN_PENALTY_TIER_MISMATCH * len(empty_weeks)

        return 0.0
