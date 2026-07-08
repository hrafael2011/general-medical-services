# backend/app/domain/calendars/rules/__init__.py
from backend.app.domain.calendars.rules.interface import Rule, RuleContext, RuleResult
from backend.app.domain.calendars.rules.rule_active_status import ActiveStatusRule
from backend.app.domain.calendars.rules.rule_area_allowed import AreaAllowedRule
from backend.app.domain.calendars.rules.rule_hard_block import HardBlockRule
from backend.app.domain.calendars.rules.rule_availability import AvailabilityRule
from backend.app.domain.calendars.rules.rule_monthly_limit import MonthlyLimitRule
from backend.app.domain.calendars.rules.rule_spacing import SpacingRule
from backend.app.domain.calendars.rules.rule_load_balancing import LoadBalancingRule
from backend.app.domain.calendars.rules.rule_area_rotation import AreaRotationRule
from backend.app.domain.calendars.rules.rule_mission_priority import MissionPriorityRule
from backend.app.domain.calendars.rules.rule_pattern import PatternRule
from backend.app.domain.calendars.rules.rule_availability_priority import AvailabilityPriorityRule

__all__ = [
    "Rule", "RuleContext", "RuleResult",
    "ActiveStatusRule", "AreaAllowedRule", "HardBlockRule", "AvailabilityRule",
    "MonthlyLimitRule", "SpacingRule", "LoadBalancingRule", "AreaRotationRule",
    "MissionPriorityRule", "PatternRule", "AvailabilityPriorityRule",
]


def build_pipeline(hard_rules_only: bool = False) -> list[Rule]:
    """Build the default rule evaluation pipeline.

    Args:
        hard_rules_only: If True, only return hard rules (for eligibility checks).
    """
    rules: list[Rule] = [
        ActiveStatusRule(),
        AreaAllowedRule(),
        HardBlockRule(),
        AvailabilityRule(),
        MonthlyLimitRule(),
    ]
    if not hard_rules_only:
        rules += [
            SpacingRule(),
            LoadBalancingRule(),
            AreaRotationRule(),
            MissionPriorityRule(),
            PatternRule(),
            AvailabilityPriorityRule(),
        ]
    return rules
