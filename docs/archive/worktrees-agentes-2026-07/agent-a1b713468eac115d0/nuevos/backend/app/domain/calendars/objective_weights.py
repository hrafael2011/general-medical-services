"""
Shared objective weights for calendar generation.

Single source of truth for all penalty/bonus weights used by both the
CP-SAT solver (OrToolsEngine) and the scoring pipeline (RulePipeline).

All weights are documented with their purpose and relative magnitude so
that changes can be reasoned about holistically.

Weight hierarchy (highest → lowest):
  10000  GAP_PENALTY                    Coverage first — never leave a hole
   6000  MAX_EXCESS_PENALTY             Monthly-max excess (warn_only)
   5000  MIN_ASSIGN_PENALTY             Zero-assignment penalty
   5000  PRIMARY_DISPLACEMENT_PENALTY   Titular displaced from primary day
    200  CONSECUTIVE_DAY_PENALTY        Consecutive calendar days
     60  MANDATORY_EXTRA                Day-of-week mandatory priority
     40  PRIMARY_MISMATCH_PENALTY       Day-of-week primary mismatch
     30  PRIMARY_PRIORITY_EXTRA         Day-of-week primary priority
    200  PATTERN_PENALTY_SAME_WEEK      >1 service in same week
    300  PATTERN_PENALTY_CONSECUTIVE_STRONG  Strong weeks back-to-back
    150  PATTERN_PENALTY_TIER_MISMATCH  Weekly cadence violation
      5  PATTERN_PENALTY_PER_PRIOR_VIOLATION  Fairness tracker
     20  DISPERSION_PER_WEEKDAY_PENALTY Weekday dispersion
      5  WARNING_PENALTY                Per-warning deduction in spacing rule
      5  AVAILABILITY_BONUS             Bonus for submitting availability
      3  AREA_REPEAT_PENALTY            Same area consecutively
     10  MONTHLY_LOAD_FACTOR            Greedy-scoring monthly load weight
      3  HISTORICAL_LOAD_FACTOR         Greedy-scoring historical load weight
      2  TARGET_BONUS_FACTOR            Bonus per below-target service
"""

# ── Gap / coverage ───────────────────────────────────────────────────────
GAP_PENALTY = 10000

# ── Monthly load limits ──────────────────────────────────────────────────
MAX_EXCESS_PENALTY = 6000          # warn_only → penalise excess
MIN_ASSIGN_PENALTY = 5000          # zero-assignment penalty

# ── Day-of-week priority (titulares) ─────────────────────────────────────
PRIMARY_DISPLACEMENT_PENALTY = 5000  # CP-SAT soft constraint weight
MANDATORY_EXTRA = -60.0              # Soft-rule extra for mandatory day
PRIMARY_MISMATCH_PENALTY = 40.0      # Soft-rule primary-weekday mismatch
PRIMARY_PRIORITY_EXTRA = -30.0       # Soft-rule extra for primary day
DISPERSION_PER_WEEKDAY_PENALTY = 20.0  # Soft-rule dispersion penalty

# ── Spacing / consecutive days ───────────────────────────────────────────
CONSECUTIVE_DAY_PENALTY = 200        # CP-SAT consecutive-day penalty

# ── Pattern (T2-T4 weekly cadence) ──────────────────────────────────────
PATTERN_PENALTY_SAME_WEEK = 200.0
PATTERN_PENALTY_CONSECUTIVE_STRONG = 300.0
PATTERN_PENALTY_TIER_MISMATCH = 150.0
PATTERN_PENALTY_PER_PRIOR_VIOLATION = 5.0

# ── Fairness mode ────────────────────────────────────────────────────────────
FAIRNESS_MODE_STRICT = "strict"
FAIRNESS_MODE_HYBRID = "hybrid"
FAIRNESS_MODE_LENIENT = "lenient"

# ── Scoring helpers ─────────────────────────────────────────────────────
WARNING_PENALTY = 5.0
AVAILABILITY_BONUS = 5.0          # bonus for submitting availability
AREA_REPEAT_PENALTY = 3.0          # same area consecutively

# ── Load-balancing coefficients (greedy scoring) ────────────────────────
MONTHLY_LOAD_FACTOR = 10.0
HISTORICAL_LOAD_FACTOR = 3.0
TARGET_BONUS_FACTOR = 2.0

# ── Area weights ──────────────────────────────────────────────────────────
AREA_WEIGHTS: dict[str, float] = {
    "emergencia": 3.0,
    "pista": 2.0,
    "disponible": 1.0,
}

MISSION_WEIGHT = 0.5
STRONG_AREAS = {"emergencia", "pista"}
