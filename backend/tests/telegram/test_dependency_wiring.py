"""Dependency wiring tests for the Telegram bot runtime."""

from backend.app.api.routes.telegram import get_orchestrator
from backend.app.application.telegram.doctor_query_service import DoctorQueryService
from backend.app.application.telegram.entity_resolver import EntityResolver
from backend.app.application.telegram.memory import SessionStore
from backend.app.core.config import settings


def test_get_orchestrator_wires_entity_resolver(db_session, monkeypatch) -> None:
    """The production dependency factory must enable entity pre-processing."""
    monkeypatch.setattr(settings, "telegram_bot_token", None)
    monkeypatch.setattr(settings, "deepseek_api_key", None)

    orchestrator = get_orchestrator(db_session)

    assert isinstance(orchestrator._agent._entity_resolver, EntityResolver)
    assert isinstance(orchestrator._agent._doctor_query_service, DoctorQueryService)
    assert isinstance(orchestrator._agent._session_store, SessionStore)
