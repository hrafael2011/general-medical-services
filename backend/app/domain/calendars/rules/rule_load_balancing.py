from backend.app.domain.calendars.rules.interface import Rule, RuleContext, RuleResult
from backend.app.domain.calendars.scoring import AREA_WEIGHTS, MISSION_WEIGHT

MONTHLY_PENALTY_FACTOR = 10.0
HISTORICAL_PENALTY_FACTOR = 3.0


class LoadBalancingRule(Rule):
    """Soft rule: penalize weighted monthly and historical load."""

    def __init__(self):
        super().__init__(name="load_balancing", is_hard=False, weight=1.0)

    def evaluate(self, ctx: RuleContext) -> RuleResult:
        weights = ctx.area_weights or AREA_WEIGHTS

        monthly_load = sum(
            weights.get(a["service_area_id"], 1.0)
            for a in ctx.monthly_assignments
            if a["doctor_id"] == ctx.doctor_id
        )
        historical_load = sum(
            weights.get(a["service_area_id"], 1.0)
            for a in ctx.historical_assignments
            if a["doctor_id"] == ctx.doctor_id
        ) + len([m for m in ctx.mission_assignments if m["doctor_id"] == ctx.doctor_id]) * MISSION_WEIGHT

        score_delta = -(monthly_load * MONTHLY_PENALTY_FACTOR + historical_load * HISTORICAL_PENALTY_FACTOR)

        return RuleResult(
            rule_name=self.name,
            score_delta=score_delta,
            extra={
                "monthly_load": monthly_load,
                "historical_load": historical_load,
            },
        )
