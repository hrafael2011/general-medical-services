# ADR-003: Greedy Scoring over OR-Tools CP-SAT

- **Status:** Accepted
- **Date:** 2026-06-26
- **Decided by:** Hendrick Rafael

## Context

The system must generate monthly medical shift calendars by assigning doctors to slots (service area + day + time) while respecting availability, eligibility, and fairness in workload distribution.

Domain requirements include:

- Respect each doctor's individual availability per month
- Apply eligibility rules (rank, permitted area, active restrictions)
- Maximize fairness in workload distribution across doctors
- Resolve minimum coverage gaps per area
- Generate visible rationale for each assignment

Two main approaches existed for the scheduling algorithm.

## Decision

We chose **Greedy Constraint-Based + Scoring Pipeline** for the MVP, with a documented migration path to OR-Tools if scale requires it.

## Alternatives considered

### OR-Tools CP-SAT (discarded for MVP)

**Advantages:**

- Guarantees global optimality (mathematically minimizes unfairness)
- Natively handles complex constraints (cumulative constraints, sequences, etc.)
- Widely used in real production scheduling

**Disadvantages:**

- High learning curve — modeling hospital scheduling in CP-SAT requires specialization
- Complex debugging — the model is mathematical, not imperative code
- Institutional rules change frequently — each change requires re-modeling
- Overkill for current scale (20–50 doctors, ~100–200 slots/month)

### Greedy Constraint-Based + Scoring (chosen)

**Advantages:**

- Pure Python implementation, readable and maintainable
- Scoring function is transparent and auditable — each assignment documents why a doctor was chosen
- Easy to adjust weights and rules based on real operator feedback
- Sufficiently good results for current institutional scale

**Disadvantages:**

- No global optimality guarantee — an early suboptimal assignment can force a poor late assignment
- The algorithm does not scale to hundreds of doctors without review

## Consequences

- **Positive:** Reduced development time (estimated 2 weeks vs 6+ weeks for OR-Tools)
- **Positive:** Traceable scoring — `compute_candidate_score()` captures rationale in a data structure, not a mathematical objective function
- **Positive:** Easy to adjust with real user feedback — only weights change, not the model
- **Negative:** If the institution grows to 100+ doctors, migration to OR-Tools will be necessary (estimated 3–4 weeks)
- **Negative:** The algorithm may produce suboptimal assignments in months with many simultaneous constraints

## Notes

- See [TD-101](../technical-debt.md) for tracking the OR-Tools migration technical debt
- Current scoring formula: `100 - monthly_load*10 - historical_load*3 + days_since_last*0.5 + days_since_heavy*0.3 - warnings*5 + goal_bonus - area_penalty`
- Area weights: Emergency=3.0, Runway=2.0, On-Call=1.0
