from datetime import datetime

from pydantic import BaseModel, Field


class ConfirmationRequestRead(BaseModel):
    id: str
    confirmation_type: str
    status: str
    doctor_id: str
    notification_id: str | None
    assignment_id: str | None
    mission_id: str | None
    due_at: datetime | None
    responded_at: datetime | None
    response_channel: str | None
    created_by: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConfirmationRequestListResponse(BaseModel):
    items: list[ConfirmationRequestRead]
    total: int


class ProcessOverdueConfirmationsResponse(BaseModel):
    expired: int
    alerts_created: int


class PublicConfirmationRead(BaseModel):
    confirmation_type: str
    status: str
    doctor_name: str | None
    due_at: datetime | None
    responded_at: datetime | None


class PublicConfirmationResponse(BaseModel):
    confirmation_type: str
    status: str
    doctor_name: str | None
    responded_at: datetime | None


class PublicConfirmationActionRequest(BaseModel):
    note: str | None = Field(default=None, max_length=500)
