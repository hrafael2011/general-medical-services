from backend.app.domain.calendars.rules.interface import Rule, RuleContext, RuleResult

MISSION_PENALTY_DAYS = 14
MISSION_PENALTY_PER_DAY = 1.0


class MissionPriorityRule(Rule):
    """Soft rule: reduce priority for doctors with recent missions."""

    def __init__(self):
        super().__init__(name="mission_priority", is_hard=False, weight=0.5)

    def evaluate(self, ctx: RuleContext) -> RuleResult:
        my_missions = [m for m in ctx.mission_assignments if m["doctor_id"] == ctx.doctor_id]
        if not my_missions:
            return RuleResult(rule_name=self.name)

        last_mission = max(my_missions, key=lambda m: m["mission_date"])
        days_since = max(0, (ctx.slot_date - last_mission["mission_date"]).days)
        penalty = -max(0, MISSION_PENALTY_DAYS - days_since) * MISSION_PENALTY_PER_DAY

        return RuleResult(rule_name=self.name, score_delta=penalty)
