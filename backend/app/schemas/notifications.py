from datetime import datetime

from pydantic import BaseModel

# --- Notification Event ---

class NotificationEventRead(BaseModel):
    id: str
    notification_type: str
    recipient_doctor_id: str | None
    recipient_phone: str | None
    assignment_id: str | None
    mission_id: str | None
    idempotency_key: str
    scheduled_for: datetime | None
    sent_at: datetime | None
    status: str
    provider: str | None
    provider_message_id: str | None
    error_code: str | None
    error_message: str | None
    retry_count: int
    payload: dict | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class NotificationListResponse(BaseModel):
    items: list[NotificationEventRead]
    total: int


# --- Scheduled Job ---

class ScheduledJobRead(BaseModel):
    id: str
    job_type: str
    status: str
    scheduled_for: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    retry_count: int
    payload: dict | None
    result: dict | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- Process Notifications Response ---

class ProcessNotificationsResponse(BaseModel):
    """Result of processing the notification queue."""
    sent: int
    failed: int
    skipped: int
