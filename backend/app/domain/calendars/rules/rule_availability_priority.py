"""AvailabilityPriorityRule — soft bonus for doctors who submitted availability.

Doctors who proactively submit their availability dates for the month should
be preferred during calendar generation and manual assignment. This gives a
small scoring bonus to those doctors, making them appear higher in the
candidate list for their declared dates.

The bonus is moderate — it makes the solver prefer a doctor with submitted
availability over one without, but does NOT block doctors who didn't submit.
"""
from backend.app.domain.calendars.rules.interface import Rule, RuleContext, RuleResult

AVAILABILITY_SUBMITTED_BONUS = 5.0


class AvailabilityPriorityRule(Rule):
    """Soft rule: bonus for doctors who submitted their availability."""

    def __init__(self):
        super().__init__(name="availability_priority", is_hard=False, weight=1.0)

    def evaluate(self, ctx: RuleContext) -> RuleResult:
        if not ctx.submitted_availability:
            return RuleResult(rule_name=self.name)

        return RuleResult(
            rule_name=self.name,
            score_delta=AVAILABILITY_SUBMITTED_BONUS,
            extra={"submitted_availability": True},
        )
