from backend.app.domain.calendars.rules.interface import Rule, RuleContext, RuleResult


class AvailabilityRule(Rule):
    """Hard block: doctor must have availability for the slot date."""

    def __init__(self):
        super().__init__(name="availability", is_hard=True)

    def evaluate(self, ctx: RuleContext) -> RuleResult:
        if not ctx.has_availability:
            return RuleResult(
                rule_name=self.name,
                score_delta=-999.0,
                is_blocking=True,
                extra={"reason": "no_availability"},
            )
        return RuleResult(rule_name=self.name)
