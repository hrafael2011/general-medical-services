from backend.app.domain.calendars.rules.interface import Rule, RuleContext, RuleResult


class CoverageRule(Rule):
    """Soft rule: penalize leaving gaps (used by CP-SAT objective as high-weight penalty).

    In greedy/scoring mode this is a no-op (the engine handles gaps separately).
    In CP-SAT mode this adds a high penalty for unfilled slots.
    """

    def __init__(self):
        super().__init__(name="coverage", is_hard=False, weight=100.0)

    def evaluate(self, ctx: RuleContext) -> RuleResult:
        # No-op in scoring pipeline — coverage is enforced by the engine
        return RuleResult(rule_name=self.name)
