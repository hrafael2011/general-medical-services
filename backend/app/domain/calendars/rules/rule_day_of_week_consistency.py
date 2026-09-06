"""DayOfWeekConsistencyRule — enforce weekday consistency per doctor.

The encargado (human scheduler) almost always assigns a given doctor on the
same day of the week.  For example, SGT. MORRILLO works 20/20 times on
Wednesdays, and CABO NUÑEZ works 19/19 times on Mondays.

This SOFT rule penalises assigning a doctor to a day that differs from their
primary weekday (the one they are "titular" of).  It also penalises dispersion:
the more distinct weekdays a doctor ends up with, the larger the penalty.

The rule is parameterised so that doctors with a declared ``day_priority`` of
``mandatory`` or ``primary`` receive stronger penalties for day mismatch,
while doctors with ``available`` (no declared preference) are unaffected.

Design notes
------------
- This is a SOFT rule: it never blocks an assignment, only adjusts scores.
- The penalty is tuned to be meaningful (20-80 points) compared to
  BASE_SCORE=100, so it influences the greedy scoring step.
- In the CP-SAT solver, ``mandatory`` days are enforced via a hard constraint
  and ``primary`` days via a variable displacement penalty (5000).  This rule
  exists primarily for the greedy-scoring path and for the manual evaluation UI.
"""
from backend.app.domain.calendars.rules.interface import Rule, RuleContext, RuleResult

# Penalty when the slot's weekday differs from the doctor's primary weekday.
PRIMARY_MISMATCH_PENALTY = 40.0
# Penalty when the slot introduces a *new* weekday (increases dispersion).
DISPERSION_PER_WEEKDAY_PENALTY = 20.0
# Extra penalty when the doctor has a "primary" day priority.
PRIMARY_PRIORITY_EXTRA = -30.0
# Extra penalty when the doctor has a "mandatory" day priority.
MANDATORY_EXTRA = -60.0


class DayOfWeekConsistencyRule(Rule):
    """Soft rule: penalise assigning a doctor to a non-primary weekday."""

    def __init__(self):
        super().__init__(name="day_of_week_consistency", is_hard=False, weight=1.0)

    def evaluate(self, ctx: RuleContext) -> RuleResult:
        warnings: list[str] = []
        penalty = 0.0
        slot_wd = ctx.slot_date.weekday()

        # --- 1. Primary-weekday mismatch ---
        if ctx.primary_weekday is not None and slot_wd != ctx.primary_weekday:
            penalty += PRIMARY_MISMATCH_PENALTY
            warnings.append(
                f"Día {_wd_name(slot_wd)} no es el día primario "
                f"({_wd_name(ctx.primary_weekday)})"
            )

        # --- 2. Day-priority extra penalties ---
        priority = ctx.day_priorities.get(slot_wd, "available")
        if priority == "mandatory":
            penalty += -MANDATORY_EXTRA  # +60 effective penalty
            warnings.append("Día marcado como obligatorio — preferencia muy alta")
        elif priority == "primary":
            penalty += -PRIMARY_PRIORITY_EXTRA  # +30 effective penalty
            warnings.append("Día marcado como primario — preferencia alta")

        # --- 3. Dispersion penalty ---
        # Collect all weekdays already assigned to this doctor in the month.
        assigned_weekdays: set[int] = set()
        for a in ctx.monthly_assignments:
            if a["doctor_id"] == ctx.doctor_id:
                assigned_weekdays.add(a["service_date"].weekday())

        if slot_wd not in assigned_weekdays:
            # This slot introduces a *new* weekday for this doctor.
            new_dispersion = len(assigned_weekdays) + 1
            if len(assigned_weekdays) > 0:
                disp_penalty = DISPERSION_PER_WEEKDAY_PENALTY * new_dispersion
                penalty += disp_penalty
                warnings.append(
                    f"Nuevo día de semana (#{new_dispersion}) — "
                    f"penalización por dispersión {disp_penalty:.0f}"
                )

        return RuleResult(
            rule_name=self.name,
            score_delta=-penalty if penalty else 0.0,
            warnings=warnings,
            extra={
                "slot_weekday": slot_wd,
                "primary_weekday": ctx.primary_weekday,
                "assigned_weekdays": len(assigned_weekdays),
                "day_priority": priority,
            },
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_WD_NAMES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def _wd_name(wd: int) -> str:
    return _WD_NAMES[wd] if 0 <= wd <= 6 else f"día-{wd}"
