from backend.app.domain.calendars.rules.interface import Rule, RuleContext, RuleResult

AREA_PENALTY = 3.0


class AreaRotationRule(Rule):
    """Soft rule: penalty for assigning the same area as the last assignment."""

    def __init__(self):
        super().__init__(name="area_rotation", is_hard=False, weight=1.0)

    def evaluate(self, ctx: RuleContext) -> RuleResult:
        all_assignments = ctx.monthly_assignments + ctx.historical_assignments
        my_assignments = [a for a in all_assignments if a["doctor_id"] == ctx.doctor_id]

        if not my_assignments:
            return RuleResult(rule_name=self.name)

        last = max(my_assignments, key=lambda a: a["service_date"])
        penalty = -AREA_PENALTY if last["service_area_id"] == ctx.service_area_id else 0.0

        return RuleResult(rule_name=self.name, score_delta=penalty)
