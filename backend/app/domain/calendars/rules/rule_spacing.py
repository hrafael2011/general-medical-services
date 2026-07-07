from datetime import date
from backend.app.domain.calendars.rules.interface import Rule, RuleContext, RuleResult

MIN_SPACING_STRONG = 14
MIN_SPACING_DISPONIBLE_AFTER_STRONG = 7
MIN_SPACING_AFTER_MISSION_STRONG = 7
MIN_SPACING_AFTER_MISSION_DISPONIBLE = 5
MAX_REST_DAYS = 30
REST_BONUS_ANY = 0.5
REST_BONUS_STRONG = 0.3
WARNING_PENALTY = 5.0


class SpacingRule(Rule):
    """Soft rule: spacing between services + rest bonus."""

    def __init__(self):
        super().__init__(name="spacing", is_hard=False, weight=1.0)

    def evaluate(self, ctx: RuleContext) -> RuleResult:
        warnings: list[str] = []
        extra: dict = {}

        # Calculate days since last services
        all_dates = [
            a["service_date"] for a in ctx.monthly_assignments + ctx.historical_assignments
        ]
        strong_dates = [
            a["service_date"] for a in ctx.monthly_assignments + ctx.historical_assignments
            if a["service_area_id"] in ctx.strong_area_ids
        ]

        days_since_last = 0
        if all_dates:
            days_since_last = max(0, (ctx.slot_date - max(all_dates)).days)

        days_since_strong = 0
        if strong_dates:
            days_since_strong = max(0, (ctx.slot_date - max(strong_dates)).days)

        extra["days_since_last"] = days_since_last
        extra["days_since_strong"] = days_since_strong

        # Spacing warnings (only if there are prior strong services to measure from)
        if strong_dates:
            if ctx.service_area_id in ctx.strong_area_ids:
                if days_since_strong < MIN_SPACING_STRONG:
                    warnings.append(f"spacing < 14 días desde último turno fuerte")
            elif ctx.service_area_id == "disponible":
                if days_since_strong < MIN_SPACING_DISPONIBLE_AFTER_STRONG:
                    warnings.append(f"spacing < 7 días desde turno fuerte")

        # Mission spacing
        mission_dates = [m["mission_date"] for m in ctx.mission_assignments]
        if mission_dates:
            days_since_mission = max(0, (ctx.slot_date - max(mission_dates)).days)
            if ctx.service_area_id in ctx.strong_area_ids and days_since_mission < MIN_SPACING_AFTER_MISSION_STRONG:
                warnings.append("spacing < 7 días desde misión")
            elif ctx.service_area_id == "disponible" and days_since_mission < MIN_SPACING_AFTER_MISSION_DISPONIBLE:
                warnings.append("spacing < 5 días desde misión")

        # Score deltas
        rest_bonus = min(days_since_last, MAX_REST_DAYS) * REST_BONUS_ANY
        strong_bonus = min(days_since_strong, MAX_REST_DAYS) * REST_BONUS_STRONG
        warning_penalty = len(warnings) * WARNING_PENALTY

        score_delta = rest_bonus + strong_bonus - warning_penalty

        return RuleResult(
            rule_name=self.name,
            score_delta=score_delta,
            warnings=warnings,
            extra=extra,
        )
