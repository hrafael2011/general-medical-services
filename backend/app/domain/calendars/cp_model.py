"""CP-SAT calendar generation engine using OR-Tools.

Replaces CalendarEngine's greedy algorithm with a global optimization model.
Same interface: GenerationContext → GenerationSummary.
"""
from datetime import date, timedelta

from ortools.sat.python import cp_model

from backend.app.domain.calendars.engine import GenerationContext
from backend.app.domain.calendars.types import GenerationSummary, SlotRequest, SlotResult
from backend.app.domain.calendars.weeks import compute_weeks

GAP_PENALTY = 10000


class OrToolsEngine:
    """Calendar generation engine using CP-SAT for global optimization."""

    def solve(self, ctx: GenerationContext) -> GenerationSummary:
        # 1. Build date set for the calendar month
        weeks = compute_weeks(ctx.year, ctx.month)
        date_set: set[date] = set()
        for w in weeks:
            _, _, sy, sm, sd, ey, em, ed = w
            d = date(sy, sm, sd)
            end = date(ey, em, ed)
            while d <= end:
                date_set.add(d)
                d += timedelta(days=1)
        sorted_dates = sorted(date_set)

        # 2. Pre-filter eligibility per slot (hard rules)
        eligible_map: dict[tuple[str, date, str], bool] = {}
        for day in sorted_dates:
            for area in ctx.required_areas:
                slot = SlotRequest(
                    date=day,
                    service_area_id=area,
                    area_weight=ctx.area_weights.get(area, 1.0),
                )
                eligible_ids = {d.id for d in ctx.doctors if self._is_eligible(d, slot, ctx)}
                for doc in ctx.doctors:
                    eligible_map[(doc.id, day, area)] = doc.id in eligible_ids

        # 3. Create model
        model = cp_model.CpModel()

        # 4. Decision variables
        x: dict[tuple[str, date, str], cp_model.IntVar] = {}
        gap: dict[tuple[date, str], cp_model.IntVar] = {}

        for day in sorted_dates:
            for area in ctx.required_areas:
                gap[(day, area)] = model.new_bool_var(f"gap_{day}_{area}")
                doctor_vars = []
                for doc in ctx.doctors:
                    if eligible_map.get((doc.id, day, area), False):
                        var_name = f"x_{doc.id}_{day}_{area}"
                        x[(doc.id, day, area)] = model.new_bool_var(var_name)
                        doctor_vars.append(x[(doc.id, day, area)])
                model.add(sum(doctor_vars) + gap[(day, area)] == 1)

        # 5. Max 1 assignment per doctor per day
        for doc in ctx.doctors:
            for day in sorted_dates:
                doc_day_vars = [
                    x[(doc.id, day, area)]
                    for area in ctx.required_areas
                    if (doc.id, day, area) in x
                ]
                if doc_day_vars:
                    model.add(sum(doc_day_vars) <= 1)

        # 6. Monthly max per doctor
        for doc in ctx.doctors:
            monthly_max = (
                ctx.monthly_service_maxes.get(doc.id, 3)
                if ctx.monthly_service_maxes
                else 3
            )
            doc_vars = [var for (d_id, _, _), var in x.items() if d_id == doc.id]
            if doc_vars:
                model.add(sum(doc_vars) <= monthly_max)

        # 7. Objective: minimize gaps + soft penalties
        objective_terms = []

        # Gap penalty (high weight)
        for day in sorted_dates:
            for area in ctx.required_areas:
                objective_terms.append(gap[(day, area)] * GAP_PENALTY)

        # Soft: load balancing (penalize assigning doctors with existing load)
        for doc in ctx.doctors:
            base_load = 0.0
            for a in ctx.historical_assignments:
                if a["doctor_id"] == doc.id:
                    base_load += ctx.area_weights.get(a["service_area_id"], 1.0) * 3
            weight_per_assign = (
                max(10, int(base_load * 10 / max(len(sorted_dates), 1)) + 10)
            )

            doc_vars = [var for (d_id, _, _), var in x.items() if d_id == doc.id]
            for var in doc_vars:
                objective_terms.append(var * weight_per_assign)

        # Soft: spacing penalty (consecutive days)
        for doc in ctx.doctors:
            for i in range(len(sorted_dates) - 1):
                day1 = sorted_dates[i]
                day2 = sorted_dates[i + 1]
                d1_vars = [
                    x[(doc.id, day1, a)]
                    for a in ctx.required_areas
                    if (doc.id, day1, a) in x
                ]
                d2_vars = [
                    x[(doc.id, day2, a)]
                    for a in ctx.required_areas
                    if (doc.id, day2, a) in x
                ]
                if d1_vars and d2_vars:
                    both = model.new_bool_var(f"consec_{doc.id}_{day1}_{day2}")
                    model.add(sum(d1_vars) + sum(d2_vars) - 1 <= 2 * both)
                    model.add(both <= sum(d1_vars))
                    model.add(both <= sum(d2_vars))
                    objective_terms.append(both * 50)

        model.minimize(sum(objective_terms))

        # 8. Solve
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 30.0
        status = solver.solve(model)

        # 9. Extract solution
        slot_results: list[SlotResult] = []
        assigned_count = 0

        for day in sorted_dates:
            for area in ctx.required_areas:
                assigned_doctor = None
                if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
                    if solver.value(gap[(day, area)]) == 0:
                        for doc in ctx.doctors:
                            if (
                                (doc.id, day, area) in x
                                and solver.value(x[(doc.id, day, area)]) == 1
                            ):
                                assigned_doctor = doc.id
                                assigned_count += 1
                                break

                slot_results.append(
                    SlotResult(
                        slot=SlotRequest(
                            date=day,
                            service_area_id=area,
                            area_weight=ctx.area_weights.get(area, 1.0),
                        ),
                        assigned_doctor_id=assigned_doctor,
                        score=None,
                        rationale={
                            "source": "cp_sat",
                            "status": solver.StatusName(status),
                        },
                    )
                )

        return GenerationSummary(
            version_id="",
            calendar_id="",
            month=ctx.month,
            year=ctx.year,
            total_slots=len(slot_results),
            assigned_count=assigned_count,
            gap_count=len(slot_results) - assigned_count,
            slot_results=slot_results,
        )

    def _is_eligible(self, doctor, slot: SlotRequest, ctx: GenerationContext) -> bool:
        """Check hard eligibility (mirrors CalendarEngine.get_eligible_doctors).

        Does NOT import CalendarEngine to avoid circular dependency.
        """
        if not doctor.active or not doctor.service_active:
            return False
        allowed = ctx.allowed_areas.get(doctor.id, [])
        if slot.service_area_id not in allowed:
            return False
        restrictions = ctx.restrictions.get(doctor.id, [])
        for r in restrictions:
            if r.severity == "hard_block":
                starts = r.starts_at
                if hasattr(starts, "date"):
                    starts = starts.date()
                if slot.date >= starts:
                    if r.ends_at is None:
                        return False
                    ends = r.ends_at
                    if hasattr(ends, "date"):
                        ends = ends.date()
                    if slot.date <= ends:
                        return False
        records = ctx.availability.get(doctor.id, [])
        if not records:
            return True
        for record in records:
            atype = record.availability_type
            if atype == "monthly_variable":
                rm = getattr(record, "month", None)
                ry = getattr(record, "year", None)
                if rm != slot.date.month or ry != slot.date.year:
                    continue
                ad = (
                    getattr(record, "available_days", None)
                    or getattr(record, "available_dates", None)
                    or []
                )
                if slot.date.day in ad:
                    return True
            elif atype == "weekly_fixed":
                dow = getattr(record, "days_of_week", None) or []
                if slot.date.weekday() in dow:
                    return True
            elif atype == "recurring":
                from backend.app.domain.availability_rules import (
                    matches_recurring_monthly_rule,
                )

                if matches_recurring_monthly_rule(
                    slot.date,
                    getattr(record, "weekday", None),
                    getattr(record, "week_number", None),
                ):
                    return True
        return False
