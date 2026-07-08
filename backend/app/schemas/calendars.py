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
    force_warnings: list[str] | None = Field(default=None)


class ReplaceAssignmentRequest(BaseModel):
    doctor_id: str
    override_justification: str | None = Field(default=None, max_length=500)
    force_warnings: list[str] | None = Field(default=None)


# --- Eligible Doctors ---

class EligibleDoctorRead(BaseModel):
    id: str
    full_name: str
    specialty: str | None = None
    rank_name: str | None = None
    altera_orden: bool | None = None  # None = sin patrón, False = respeta, True = altera

    model_config = {"from_attributes": True}


class EligibleDoctorsResponse(BaseModel):
    doctors: list[EligibleDoctorRead]


# --- Slot Evaluation ---

class HardBlockItem(BaseModel):
    code: str
    description: str


class WarningItem(BaseModel):
    code: str
    description: str


class EvaluationRequest(BaseModel):
    doctor_id: str
    service_date: date
    service_area_id: str


class EvaluationResponse(BaseModel):
    hard_blocks: list[HardBlockItem]
    warnings: list[WarningItem]


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


# --- Calendar Week ---

class DoctorAssignmentCountRead(BaseModel):
    doctor_id: str
    doctor_name: str
    count: int


class WeekRead(BaseModel):
    id: str
    week_number: int
    label: str
    start_date: str
    end_date: str
    status: str
    assignment_count: int = 0
    doctor_assignment_counts: list[DoctorAssignmentCountRead] = Field(default_factory=list)
    approved_by: str | None = None
    approved_at: str | None = None

    model_config = {"from_attributes": True}


class ApproveWeekRequest(BaseModel):
    notes: str | None = None


# --- Equilibrio / Pattern tracking ---


class EquilibrioItem(BaseModel):
    doctor_id: str
    nombre_medico: str
    servicios_asignados: int
    servicios_esperados: int
    alteraciones_al_orden: int


class EquilibrioResponse(BaseModel):
    mes: int
    ano: int
    items: list[EquilibrioItem]
