from backend.app.domain.calendars.rules.interface import Rule, RuleContext, RuleResult


class ActiveStatusRule(Rule):
    """Hard block: doctor must be active and service_active."""

    def __init__(self):
        super().__init__(name="active_status", is_hard=True)

    def evaluate(self, ctx: RuleContext) -> RuleResult:
        if not ctx.is_active:
            return RuleResult(
                rule_name=self.name,
                score_delta=-999.0,
                is_blocking=True,
                extra={"reason": "doctor_inactive"},
            )
        if not ctx.is_service_active:
            return RuleResult(
                rule_name=self.name,
                score_delta=-999.0,
                is_blocking=True,
                extra={"reason": "service_inactive"},
            )
        return RuleResult(rule_name=self.name)
