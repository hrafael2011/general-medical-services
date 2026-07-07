from backend.app.domain.calendars.rules.interface import Rule, RuleContext, RuleResult


class MonthlyLimitRule(Rule):
    """Hard block (when at max) + target bonus (soft)."""

    def __init__(self):
        super().__init__(name="monthly_limit", is_hard=True, weight=2.0)

    def evaluate(self, ctx: RuleContext) -> RuleResult:
        # Hard check: monthly max reached
        if ctx.monthly_count >= ctx.monthly_service_max:
            return RuleResult(
                rule_name=self.name,
                score_delta=-999.0,
                is_blocking=True,
                extra={"reason": "monthly_max_exceeded"},
            )

        # Soft bonus: reward doctors below their target
        below_target = max(0, ctx.monthly_service_target - ctx.monthly_count)
        bonus = float(below_target * 2)
        return RuleResult(rule_name=self.name, score_delta=bonus)
