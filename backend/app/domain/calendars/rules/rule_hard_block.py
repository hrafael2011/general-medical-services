from backend.app.domain.calendars.rules.interface import Rule, RuleContext, RuleResult


class HardBlockRule(Rule):
    """Hard block: doctor has an active hard_block restriction."""

    def __init__(self):
        super().__init__(name="hard_block", is_hard=True)

    def evaluate(self, ctx: RuleContext) -> RuleResult:
        if ctx.hard_block_active:
            return RuleResult(
                rule_name=self.name,
                score_delta=-999.0,
                is_blocking=True,
                extra={"reason": "has_hard_block"},
            )
        return RuleResult(rule_name=self.name)
