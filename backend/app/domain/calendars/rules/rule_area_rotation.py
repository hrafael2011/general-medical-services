from backend.app.domain.calendars.rules.interface import Rule, RuleContext, RuleResult

AREA_PENALTY = 3.0

# Multiplier per area_rotation_mode relative to AREA_PENALTY
_MODE_MULTIPLIER = {
    "fixed": 0.0,    # no penalty — stays in their area
    "auto": 1.0,     # default — -3.0
    "rotate": 2.0,   # double penalty — -6.0
}


class AreaRotationRule(Rule):
    """Soft rule: penalty for assigning the same area as the last assignment.

    The penalty magnitude depends on the doctor's ``area_rotation_mode``:
    - "fixed": 0 penalty (the doctor stays in their area)
    - "auto": -3.0 penalty (default)
    - "rotate": -6.0 penalty (double, encourages rotation)
    """

    def __init__(self):
        super().__init__(name="area_rotation", is_hard=False, weight=1.0)

    def evaluate(self, ctx: RuleContext) -> RuleResult:
        all_assignments = ctx.monthly_assignments + ctx.historical_assignments
        my_assignments = [a for a in all_assignments if a["doctor_id"] == ctx.doctor_id]

        if not my_assignments:
            return RuleResult(rule_name=self.name)

        multiplier = _MODE_MULTIPLIER.get(ctx.area_rotation_mode, 1.0)
        last = max(my_assignments, key=lambda a: a["service_date"])
        penalty = -(AREA_PENALTY * multiplier) if last["service_area_id"] == ctx.service_area_id else 0.0

        return RuleResult(rule_name=self.name, score_delta=penalty)
