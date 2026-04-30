from datetime import date, datetime

from pydantic import BaseModel, Field


class SetWeeklyAvailabilityRequest(BaseModel):
    days_of_week: list[int] = Field(min_length=1, description="Weekdays 0=Monday to 6=Sunday")
    effective_from: date | None = None
    effective_to: date | None = None


class SetMonthlyAvailabilityRequest(BaseModel):
    year: int = Field(ge=2020, le=2100)
    month: int = Field(ge=1, le=12)
    available_dates: list[int] = Field(min_length=1, description="Day-of-month numbers 1–31")


class AddRestrictionRequest(BaseModel):
    restriction_type: str = Field(pattern="^(license|restriction)$")
    severity: str = Field(pattern="^(hard_block|warn|informational)$")
    starts_at: date
    ends_at: date | None = None
    description: str | None = Field(default=None, max_length=500)
    reason_id: str | None = None


class AvailabilityRead(BaseModel):
    id: str
    doctor_id: str
    availability_type: str
    days_of_week: list[int] | None
    available_dates: list[int] | None
    weekday: int | None
    week_number: int | None
    year: int | None
    month: int | None
    submitted_at: datetime | None
    effective_from: date | None
    effective_to: date | None
    source: str
    review_status: str

    model_config = {"from_attributes": True}


class RestrictionRead(BaseModel):
    id: str
    doctor_id: str
    reason_id: str | None
    restriction_type: str
    severity: str
    description: str | None
    starts_at: date
    ends_at: date | None
    source: str
    review_status: str
    lifted_at: datetime | None
    lifted_by: str | None

    model_config = {"from_attributes": True}


class PendingAvailabilityItem(BaseModel):
    doctor_id: str
    doctor_name: str
    availability_mode: str


class PendingAvailabilityResponse(BaseModel):
    year: int
    month: int
    pending: list[PendingAvailabilityItem]
    total: int
