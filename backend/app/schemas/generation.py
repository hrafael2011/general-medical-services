from datetime import date

from pydantic import BaseModel


class GenerationSlotResult(BaseModel):
    """Result for one day+area slot."""
    service_date: date
    service_area_id: str
    assigned_doctor_id: str | None  # None means gap
    warnings: list[str]
    score: float | None


class GenerationResponse(BaseModel):
    """Response body for POST /calendars/{id}/generate."""
    version_id: str
    calendar_id: str
    month: int
    year: int
    total_slots: int
    assigned_count: int
    gap_count: int
    slots: list[GenerationSlotResult]
