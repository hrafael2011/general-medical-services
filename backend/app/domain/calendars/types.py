from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class SlotRequest:
    """One slot that needs to be filled: a date + area."""

    date: date
    service_area_id: str
    area_weight: float  # emergencia=3, pista=2, disponible=1


@dataclass
class CandidateScore:
    """Score computed for one doctor for one slot."""

    doctor_id: str
    score: float  # higher = better candidate
    monthly_load: float  # weighted load this month so far
    historical_load: float  # weighted load last 60 days
    days_since_last: int  # days since last service of any type
    days_since_strong: int  # days since last emergencia/pista
    monthly_count: int  # assignments this month so far
    warnings: list[str]  # soft-rule warnings, e.g. "spacing < 14 days"
    is_spacing_violation: bool  # True if hard spacing would block (reserved for future hard mode)


@dataclass
class SlotResult:
    """Result of attempting to fill one slot."""

    slot: SlotRequest
    assigned_doctor_id: str | None  # None = gap
    score: CandidateScore | None
    rationale: dict  # structured dict to store as CalendarAssignment.rationale


@dataclass
class GenerationSummary:
    """High-level result of a full month generation."""

    version_id: str
    calendar_id: str
    month: int
    year: int
    total_slots: int
    assigned_count: int
    gap_count: int
    slot_results: list[SlotResult]
