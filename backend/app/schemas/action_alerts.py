from datetime import datetime

from pydantic import BaseModel, Field


class ActionAlertRead(BaseModel):
    id: str
    alert_type: str
    section: str
    severity: str
    status: str
    title: str
    message: str
    entity_type: str | None
    entity_id: str | None
    action_url: str | None
    alert_metadata: dict | None = Field(alias="alert_metadata", default=None)
    created_by: str | None
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None
    resolved_by: str | None
    dismissed_at: datetime | None
    dismissed_by: str | None

    model_config = {"from_attributes": True}


class ActionAlertListResponse(BaseModel):
    items: list[ActionAlertRead]
    total: int


class ActionAlertSummaryResponse(BaseModel):
    total_open: int
    by_section: dict[str, int]
