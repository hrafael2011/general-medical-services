from datetime import datetime

from pydantic import BaseModel, Field


class AuditEventRead(BaseModel):
    id: str
    actor_id: str | None
    action_type: str
    entity_type: str
    entity_id: str | None
    occurred_at: datetime
    request_id: str | None
    before_snapshot: dict | None
    after_snapshot: dict | None
    metadata_: dict | None = Field(alias="metadata_", default=None)

    model_config = {"from_attributes": True}


class AuditListResponse(BaseModel):
    items: list[AuditEventRead]
    total: int
    limit: int
    offset: int
