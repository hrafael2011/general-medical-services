from backend.app.domain.calendars.rules.interface import Rule, RuleContext, RuleResult


class AreaAllowedRule(Rule):
    """Hard block: service area must be in doctor's allowed list."""

    def __init__(self):
        super().__init__(name="area_allowed", is_hard=True)

    def evaluate(self, ctx: RuleContext) -> RuleResult:
        if ctx.service_area_id not in ctx.allowed_area_ids:
            return RuleResult(
                rule_name=self.name,
                score_delta=-999.0,
                is_blocking=True,
                extra={"reason": "area_not_allowed"},
            )
        return RuleResult(rule_name=self.name)
