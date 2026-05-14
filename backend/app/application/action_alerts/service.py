from datetime import UTC, datetime
from uuid import uuid4

from backend.app.infrastructure.db.models.action_alerts import ActionAlertModel
from backend.app.infrastructure.repositories.action_alerts import ActionAlertRepository


class ActionAlertError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class ActionAlertService:
    def __init__(self, repo: ActionAlertRepository) -> None:
        self.repo = repo

    def create_alert(
        self,
        *,
        alert_type: str,
        section: str,
        title: str,
        message: str,
        severity: str = "warning",
        entity_type: str | None = None,
        entity_id: str | None = None,
        action_url: str | None = None,
        alert_metadata: dict | None = None,
        created_by: str | None = None,
    ) -> ActionAlertModel:
        now = datetime.now(UTC)
        alert = ActionAlertModel(
            id=str(uuid4()),
            alert_type=alert_type,
            section=section,
            severity=severity,
            status="open",
            title=title,
            message=message,
            entity_type=entity_type,
            entity_id=entity_id,
            action_url=action_url,
            alert_metadata=alert_metadata,
            created_by=created_by,
            created_at=now,
            updated_at=now,
        )
        return self.repo.add(alert)

    def create_if_missing(
        self,
        *,
        alert_type: str,
        section: str,
        title: str,
        message: str,
        entity_type: str,
        entity_id: str,
        severity: str = "warning",
        action_url: str | None = None,
        alert_metadata: dict | None = None,
        created_by: str | None = None,
    ) -> ActionAlertModel:
        existing = self.repo.get_open_for_entity(
            alert_type=alert_type,
            entity_type=entity_type,
            entity_id=entity_id,
        )
        if existing is not None:
            return existing
        return self.create_alert(
            alert_type=alert_type,
            section=section,
            severity=severity,
            title=title,
            message=message,
            entity_type=entity_type,
            entity_id=entity_id,
            action_url=action_url,
            alert_metadata=alert_metadata,
            created_by=created_by,
        )

    def resolve(self, alert_id: str, *, actor_id: str) -> ActionAlertModel:
        alert = self.repo.get_by_id(alert_id)
        if alert is None:
            raise ActionAlertError("alert_not_found", "La alerta no existe.")
        if alert.status != "open":
            return alert
        return self.repo.mark_resolved(alert, actor_id=actor_id)

    def dismiss(self, alert_id: str, *, actor_id: str) -> ActionAlertModel:
        alert = self.repo.get_by_id(alert_id)
        if alert is None:
            raise ActionAlertError("alert_not_found", "La alerta no existe.")
        if alert.status != "open":
            return alert
        return self.repo.mark_dismissed(alert, actor_id=actor_id)
