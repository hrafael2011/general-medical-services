from dataclasses import dataclass, field

from backend.app.domain.calendars.rules.interface import Rule, RuleContext, RuleResult

BASE_SCORE = 100.0


@dataclass
class PipelineResult:
    """Resultado de evaluar todas las reglas para un doctor+slot."""
    total_score: float
    is_eligible: bool
    results: list[RuleResult] = field(default_factory=list)
    all_warnings: list[str] = field(default_factory=list)

    @property
    def monthly_load(self) -> float:
        for r in self.results:
            if "monthly_load" in r.extra:
                return r.extra["monthly_load"]
        return 0.0

    @property
    def historical_load(self) -> float:
        for r in self.results:
            if "historical_load" in r.extra:
                return r.extra["historical_load"]
        return 0.0

    @property
    def days_since_last(self) -> int:
        for r in self.results:
            if "days_since_last" in r.extra:
                return r.extra["days_since_last"]
        return 999

    @property
    def days_since_strong(self) -> int:
        for r in self.results:
            if "days_since_strong" in r.extra:
                return r.extra["days_since_strong"]
        return 999


class RulePipeline:
    """Evalúa todas las reglas y produce un resultado agregado."""

    def __init__(self, rules: list[Rule]):
        self.rules = rules

    def evaluate(self, ctx: RuleContext) -> PipelineResult:
        results: list[RuleResult] = []
        all_warnings: list[str] = []
        total_score = BASE_SCORE

        for rule in self.rules:
            rule_result = rule.evaluate(ctx)
            results.append(rule_result)
            all_warnings.extend(rule_result.warnings)

            if rule_result.is_blocking:
                return PipelineResult(
                    total_score=-999.0,
                    is_eligible=False,
                    results=results,
                    all_warnings=all_warnings,
                )

            total_score += rule_result.score_delta

        return PipelineResult(
            total_score=total_score,
            is_eligible=True,
            results=results,
            all_warnings=all_warnings,
        )
