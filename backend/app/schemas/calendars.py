from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

# --- Calendar ---

CalendarGenerationMode = Literal["manual", "assisted_auto", "scheduled_auto"]


class CalendarRead(BaseModel):
    id: str
    year: int
    month: int
    status: str
    generation_mode: CalendarGenerationMode
    created_by: str | None
    approved_by: str | None
    created_at: datetime
    updated_at: datetime
    approved_at: datetime | None

    model_config = {"from_attributes": True}


class CreateCalendarRequest(BaseModel):
    year: int = Field(ge=2020, le=2100)
    month: int = Field(ge=1, le=12)
    generation_mode: CalendarGenerationMode = "manual"


# --- Calendar Version ---

class CalendarVersionRead(BaseModel):
    id: str
    calendar_id: str
    version_number: int
    status: str
    created_by: str | None
    reason: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Calendar Assignment ---

class CalendarAssignmentRead(BaseModel):
    id: str
    calendar_version_id: str
    service_date: date
    service_start_at: datetime | None
    service_area_id: str
    doctor_id: str
    assignment_source: str
    rationale: dict | None
    override_justification: str | None
    created_by: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AssignDoctorRequest(BaseModel):
    service_date: date
    service_area_id: str
    doctor_id: str
    override_justification: str | None = Field(default=None, max_length=500)


class ReplaceAssignmentRequest(BaseModel):
    doctor_id: str
    override_justification: str | None = Field(default=None, max_length=500)


# --- Calendar View (grid for UI) ---

class DaySlot(BaseModel):
    service_date: date
    service_area_id: str
    assignment: CalendarAssignmentRead | None
    has_warning: bool = False
    warning_message: str | None = None


class CalendarGridResponse(BaseModel):
    calendar: CalendarRead
    version: CalendarVersionRead
    slots: list[DaySlot]
    gaps: list[dict]


class CalendarAutoGenerationRunResponse(BaseModel):
    status: str
    reason: str | None
    calendar_id: str | None
    month: int | None
    year: int | None
    assigned_count: int
    gap_count: int


# --- Approval ---

class ApproveCalendarRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class UnresolvedGapRead(BaseModel):
    id: str
    calendar_version_id: str
    service_date: date
    service_area_id: str
    reason_code: str
    description: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
