from datetime import datetime

from pydantic import BaseModel, field_validator

# --- Notification Event ---

class NotificationEventRead(BaseModel):
    id: str
    notification_type: str
    recipient_doctor_id: str | None
    recipient_phone: str | None
    assignment_id: str | None
    mission_id: str | None
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

    @field_validator("payload", mode="before")
    @classmethod
    def redact_sensitive_payload(cls, value: dict | None) -> dict | None:
        if not value:
            return value
        redacted = dict(value)
        message = redacted.get("message")
        if isinstance(message, str):
            redacted["message"] = _redact_confirmation_commands(message)
        redacted.pop("confirmation_request_id", None)
        return redacted

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


def _redact_confirmation_commands(message: str) -> str:
    lines = []
    for line in message.splitlines():
        stripped = line.strip().lower()
        if "/confirmar " in stripped or "/recibido " in stripped or "/rechazar " in stripped:
            continue
        lines.append(line)
    return "\n".join(lines).strip()
