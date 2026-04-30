from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.app.infrastructure.db.models.audit import AuditEventModel


class AuditRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, event: AuditEventModel) -> AuditEventModel:
        self.session.add(event)
        self.session.flush()
        return event

    def list(
        self,
        *,
        actor_id: str | None = None,
        action_type: str | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        from_dt: datetime | None = None,
        to_dt: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditEventModel]:
        stmt = select(AuditEventModel)
        if actor_id is not None:
            stmt = stmt.where(AuditEventModel.actor_id == actor_id)
        if action_type is not None:
            stmt = stmt.where(AuditEventModel.action_type == action_type)
        if entity_type is not None:
            stmt = stmt.where(AuditEventModel.entity_type == entity_type)
        if entity_id is not None:
            stmt = stmt.where(AuditEventModel.entity_id == entity_id)
        if from_dt is not None:
            stmt = stmt.where(AuditEventModel.occurred_at >= from_dt)
        if to_dt is not None:
            stmt = stmt.where(AuditEventModel.occurred_at <= to_dt)
        stmt = stmt.order_by(AuditEventModel.occurred_at.desc()).limit(limit).offset(offset)
        return list(self.session.scalars(stmt))

    def count(
        self,
        *,
        actor_id: str | None = None,
        action_type: str | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        from_dt: datetime | None = None,
        to_dt: datetime | None = None,
    ) -> int:
        from sqlalchemy import func
        stmt = select(func.count()).select_from(AuditEventModel)
        if actor_id is not None:
            stmt = stmt.where(AuditEventModel.actor_id == actor_id)
        if action_type is not None:
            stmt = stmt.where(AuditEventModel.action_type == action_type)
        if entity_type is not None:
            stmt = stmt.where(AuditEventModel.entity_type == entity_type)
        if entity_id is not None:
            stmt = stmt.where(AuditEventModel.entity_id == entity_id)
        if from_dt is not None:
            stmt = stmt.where(AuditEventModel.occurred_at >= from_dt)
        if to_dt is not None:
            stmt = stmt.where(AuditEventModel.occurred_at <= to_dt)
        return self.session.scalar(stmt) or 0
