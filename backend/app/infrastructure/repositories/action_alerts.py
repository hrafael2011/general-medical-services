from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.infrastructure.db.models.action_alerts import ActionAlertModel


class ActionAlertRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, alert: ActionAlertModel) -> ActionAlertModel:
        self.session.add(alert)
        self.session.flush()
        return alert

    def get_by_id(self, alert_id: str) -> ActionAlertModel | None:
        return self.session.get(ActionAlertModel, alert_id)

    def get_open_for_entity(
        self,
        *,
        alert_type: str,
        entity_type: str,
        entity_id: str,
    ) -> ActionAlertModel | None:
        stmt = (
            select(ActionAlertModel)
            .where(ActionAlertModel.status == "open")
            .where(ActionAlertModel.alert_type == alert_type)
            .where(ActionAlertModel.entity_type == entity_type)
            .where(ActionAlertModel.entity_id == entity_id)
        )
        return self.session.scalars(stmt).first()

    def list_all(
        self,
        *,
        status: str | None = "open",
        section: str | None = None,
        severity: str | None = None,
        limit: int = 100,
    ) -> list[ActionAlertModel]:
        stmt = select(ActionAlertModel).order_by(ActionAlertModel.created_at.desc())
        if status:
            stmt = stmt.where(ActionAlertModel.status == status)
        if section:
            stmt = stmt.where(ActionAlertModel.section == section)
        if severity:
            stmt = stmt.where(ActionAlertModel.severity == severity)
        stmt = stmt.limit(limit)
        return list(self.session.scalars(stmt))

    def count_open_by_section(self) -> dict[str, int]:
        stmt = (
            select(ActionAlertModel.section, func.count())
            .where(ActionAlertModel.status == "open")
            .group_by(ActionAlertModel.section)
        )
        return {section: count for section, count in self.session.execute(stmt).all()}

    def mark_resolved(self, alert: ActionAlertModel, *, actor_id: str | None) -> ActionAlertModel:
        now = datetime.now(UTC)
        alert.status = "resolved"
        alert.resolved_at = now
        alert.resolved_by = actor_id
        alert.updated_at = now
        self.session.flush()
        return alert

    def mark_dismissed(self, alert: ActionAlertModel, *, actor_id: str | None) -> ActionAlertModel:
        now = datetime.now(UTC)
        alert.status = "dismissed"
        alert.dismissed_at = now
        alert.dismissed_by = actor_id
        alert.updated_at = now
        self.session.flush()
        return alert
