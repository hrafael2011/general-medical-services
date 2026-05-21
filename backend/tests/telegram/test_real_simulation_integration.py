"""Full simulation — real DeepSeek + PostgreSQL across all 39 queries.

Skipped by default. Run with: pytest -m integration backend/tests/telegram/test_real_simulation_integration.py -v -s
"""

import uuid
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.application.telegram.agent import ConversationalAgent
from backend.app.application.telegram.entity_resolver import EntityResolver
from backend.app.application.telegram.intent_router import IntentRouter
from backend.app.application.telegram.llm import DeepSeekProvider
from backend.app.application.telegram.query_executor import QueryExecutor
from backend.app.application.telegram.types import AgentResult
from backend.app.core.config import settings
from backend.app.infrastructure.db.base import Base


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture(scope="module")
def real_db_session():
    """Real PostgreSQL session — module-scoped, reused across all queries."""
    engine = create_engine(settings.database_url)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(
        bind=engine, autocommit=False, autoflush=False, expire_on_commit=False,
    )
    with SessionLocal() as session:
        yield session


@pytest.fixture(scope="module")
def deepseek_agent(real_db_session):
    """Agent wired with DeepSeekProvider + real PostgreSQL."""
    llm = DeepSeekProvider()
    router = IntentRouter()
    router.set_session(real_db_session)
    query_exec = QueryExecutor(real_db_session, llm)
    entity_resolver = EntityResolver(session=real_db_session)
    agent = ConversationalAgent(
        llm=llm, router=router,
        query_executor=query_exec, entity_resolver=entity_resolver,
    )
    return agent


# ═══════════════════════════════════════════════════════════════════════════════
# Simulation runner (adapted for non-deterministic DeepSeek)
# ═══════════════════════════════════════════════════════════════════════════════


class _Sim:
    """Simulation runner with flexible assertions for non-deterministic LLM."""

    VALID_ACTIONS = {"query", "query_db", "reply", "direct", "export", "ambiguous", "validation_error"}

    def __init__(self, agent: ConversationalAgent):
        self.agent = agent
        self.results: list[dict] = []

    def ask(self, user_message: str, category: str, description: str,
            expectations: dict | None = None) -> dict:
        result = self.agent.process(
            user_message, telegram_user_id="sim-user-001",
            user_info={"name": "Encargado", "role": "admin"},
        )
        outcome, reason = self._eval(result, expectations)
        entry = {
            "category": category, "description": description,
            "user_message": user_message, "action": result.agent_action,
            "response": result.response_text[:200] if result.response_text else "",
            "outcome": outcome,
            "fail_reason": reason,
            "has_document": result.document_bytes is not None,
            "document_name": result.document_filename,
        }
        self.results.append(entry)
        return entry

    def _eval(self, result: AgentResult, expectations: dict | None) -> tuple[str, str | None]:
        if expectations is None:
            return "PASS", None

        # Check no API errors
        if result.response_text:
            for err in ("Error de configuración", "no pude conectarme", "temporalmente sobrecargado", "error inesperado"):
                if err in result.response_text.lower():
                    return "FAIL", f"API error: {err} in response"

        # Check action matches if specified
        if "action" in expectations:
            expected_actions = expectations["action"]
            if not isinstance(expected_actions, (list, tuple)):
                expected_actions = [expected_actions]
            if result.agent_action not in expected_actions:
                return "FAIL", f"Expected action in {expected_actions}, got '{result.agent_action}'"

        # Check response_contains (soft — just verify response is non-empty)
        if "response_contains" in expectations:
            if not result.response_text:
                return "FAIL", "Response is empty"

        # Check has_document
        if "has_document" in expectations:
            if bool(result.document_bytes) != expectations["has_document"]:
                return "FAIL", f"document_bytes expected={expectations['has_document']}, got={bool(result.document_bytes)}"

        # Check document_type
        if "document_type" in expectations:
            if not result.document_filename or not result.document_filename.endswith(expectations["document_type"]):
                return "FAIL", f"Expected .{expectations['document_type']} file, got: {result.document_filename}"

        return "PASS", None

    def report(self) -> None:
        total = len(self.results)
        passed = sum(1 for r in self.results if r["outcome"] == "PASS")
        failed = total - passed
        print(f"\n{'='*70}")
        print(f"  SIMULACIÓN REAL — DeepSeek + PostgreSQL")
        print(f"{'='*70}")
        print(f"  Total: {total}  |  ✅ PASS: {passed}  |  ❌ FAIL: {failed}")
        print(f"{'='*70}\n")

        by_category: dict[str, list] = {}
        for r in self.results:
            by_category.setdefault(r["category"], []).append(r)

        for cat, entries in by_category.items():
            cat_pass = sum(1 for e in entries if e["outcome"] == "PASS")
            cat_fail = len(entries) - cat_pass
            print(f"── {cat.upper()} ({len(entries)} tests, {cat_pass} ✅, {cat_fail} ❌) ──")
            for e in entries:
                icon = "✅" if e["outcome"] == "PASS" else "❌"
                print(f"  {icon} {e['description']}")
                if e["outcome"] == "FAIL":
                    print(f"     🔴 FAIL: {e['fail_reason']}")
                print(f"     📝 \"{e['user_message']}\"")
                print(f"     🏷️  action={e['action']}")
                print(f"     💬 {e['response'][:200]}")
                if e["has_document"]:
                    print(f"     📎 Documento: {e['document_name']}")
            print()

        print(f"{'='*70}")
        print(f"  RESUMEN FINAL:")
        print(f"  ✅ Funciona: {passed}")
        print(f"  ❌ Falló:    {failed}")
        print(f"{'='*70}")


# ═══════════════════════════════════════════════════════════════════════════════
# Full simulation test
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.integration
def test_full_simulation_real(deepseek_agent):
    today = date.today()
    month_name = {
        1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo", 6: "junio",
        7: "julio", 8: "agosto", 9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre",
    }[today.month]

    sim = _Sim(deepseek_agent)

    # ═══════════════════════════════════════════════════════════════════
    # TEMPLATE CASES — 23 queries covering all DEFAULT_QUERY_TYPES
    # ═══════════════════════════════════════════════════════════════════

    sim.ask("¿cuántos médicos activos hay en total?", "template",
            "1. count_doctors_total", {"action": "query"})

    sim.ask("¿cuántos hombres hay en el servicio?", "template",
            "2. count_by_specific_sex (male)", {"action": "query"})

    sim.ask("¿cuántas mujeres hay en el servicio?", "template",
            "3. count_by_specific_sex (female)", {"action": "query"})

    sim.ask("¿cómo están distribuidos los médicos por sexo?", "template",
            "4. count_by_sex", {"action": "query"})

    sim.ask("dame la lista de médicos hombres", "template",
            "5. doctors_by_sex", {"action": "query"})

    sim.ask("¿cuántos médicos hay por rango?", "template",
            "6. count_by_rank", {"action": "query"})

    sim.ask("¿cuántos cabos hay en el sistema?", "template",
            "7. count_by_specific_rank (cabo)", {"action": "query"})

    sim.ask("¿cuántos sargentos hay?", "template",
            "8. count_by_specific_rank (sargento)", {"action": "query"})

    sim.ask("dame la lista de cabos", "template",
            "9. doctors_by_rank (cabo)", {"action": "query"})

    sim.ask("dame la lista de sargentos", "template",
            "10. doctors_by_rank (sargento)", {"action": "query"})

    sim.ask("muéstrame la lista de médicos activos", "template",
            "11. list_active_doctors", {"action": "query"})

    sim.ask("dame el detalle de Juan Pérez", "template",
            "12. doctor_detail", {"action": ["query", "ambiguous"]})

    sim.ask(f"¿qué médicos están sin disponibilidad en {month_name}?", "template",
            "13. doctors_pending_availability", {"action": ["query", "ambiguous"]})

    sim.ask(f"¿cuál es el estado del calendario de {month_name}?", "template",
            "14. calendar_status_month", {"action": "query"})

    sim.ask(f"¿qué médicos trabajan hoy {today.strftime('%Y-%m-%d')}?", "template",
            "15. doctors_working_date", {"action": "query"})

    sim.ask("¿cuántos servicios tuvo cada médico en el rango 2026-05-01 a 2026-05-31?", "template",
            "16. assignment_count_by_date_range", {"action": "query"})

    sim.ask(f"muéstrame el ranking de misiones de {today.year}-{today.month:02d}", "template",
            "17. mission_ranking", {"action": "query"})

    sim.ask(f"dame el resumen operativo de {month_name}", "template",
            "18. operational_summary", {"action": "query"})

    sim.ask(f"¿cuál es el historial del doctor con id {uuid.uuid4()} en los últimos 60 días?", "template",
            "19. doctor_history_60d", {"action": "query"})

    sim.ask("¿cuántos médicos hay por departamento?", "template",
            "20. count_doctors_by_department", {"action": "query"})

    sim.ask("dame el historial de García en los últimos 60 días", "template",
            "21. doctor_history_by_name", {"action": "query"})

    sim.ask("¿qué asignaciones en emergencia hay este mes?", "template",
            "22. assignments_by_area", {"action": ["query", "ambiguous"]})

    sim.ask(f"muéstrame los huecos sin asignar de {month_name}", "template",
            "23. unresolved_gaps_month", {"action": "query"})

    # ═══════════════════════════════════════════════════════════════════
    # OFF-TEMPLATE — 4 queries with NL-to-SQL fallback
    # ═══════════════════════════════════════════════════════════════════

    sim.ask("¿cuántos doctores que están de vacaciones esta semana?", "off_template",
            "24. Off-template: vacaciones", {"action": ["query", "query_db", "ambiguous"]})

    sim.ask("¿qué médico que tiene más servicios este año?", "off_template",
            "25. Off-template: más servicios", {"action": ["query", "query_db", "ambiguous"]})

    sim.ask("¿cuál es el promedio de servicios por médico?", "off_template",
            "26. Off-template: promedio servicios", {"action": ["query", "query_db", "ambiguous"]})

    sim.ask("muéstrame la tabla de turnos completa de este mes", "off_template",
            "27. Off-template: tabla completa", {"action": ["query", "query_db", "ambiguous"]})

    # ═══════════════════════════════════════════════════════════════════
    # CONVERSATIONAL — 3 queries
    # ═══════════════════════════════════════════════════════════════════

    sim.ask("hola", "conversational",
            "28. Saludo", {"action": ["reply", "direct"]})

    sim.ask("gracias por la ayuda", "conversational",
            "29. Agradecimiento", {"action": ["reply", "direct"]})

    sim.ask("¿qué puedes hacer?", "conversational",
            "30. Capacidades", {"action": ["reply", "direct"]})

    # ═══════════════════════════════════════════════════════════════════
    # EXPORTS — 5 queries
    # ═══════════════════════════════════════════════════════════════════

    sim.ask("exporta los médicos activos en excel", "export",
            "31. Export Excel: lista activos", {"action": "export"})

    sim.ask("exporta médicos por rango en pdf", "export",
            "32. Export PDF: médicos por rango", {"action": "export"})

    sim.ask("dame el reporte de resumen operativo de este mes en pdf", "export",
            "33. Export PDF: resumen operativo", {"action": "export"})

    sim.ask("exporta el ranking de misiones en excel", "export",
            "34. Export Excel: ranking misiones", {"action": "export"})

    sim.ask("genera un pdf de los huecos sin asignar del mes", "export",
            "35. Export PDF: huecos sin asignar", {"action": "export"})

    # ═══════════════════════════════════════════════════════════════════
    # EDGE CASES — 4 queries
    # ═══════════════════════════════════════════════════════════════════

    sim.ask("asigna a pérez en emergencia mañana", "edge",
            "36. Edge: asignación ambigua", {"action": ["ambiguous", "reply"]})

    sim.ask("dame información confidencial de usuarios del sistema", "edge",
            "37. Edge: fuera de dominio", {"action": ["reply", "ambiguous"]})

    sim.ask("¿cuál fue el resumen operativo de diciembre 2020?", "edge",
            "38. Edge: consulta histórica", {"action": "query"})

    sim.ask("dame el detalle de un médico con nombre que no existe zzz notfound", "edge",
            "39. Edge: médico no encontrado", {"action": "query"})

    # ═══════════════════════════════════════════════════════════════════
    # REPORT
    # ═══════════════════════════════════════════════════════════════════

    sim.report()

    # Count failures
    failures = [r for r in sim.results if r["outcome"] == "FAIL"]
    if failures:
        print(f"\n❌ {len(failures)} FALLAS:")
        for f in failures:
            print(f"   [{f['category']}] {f['description']} — {f['fail_reason']}")
            print(f"   💬 {f['response'][:120]}")
            print()

    passed = len(sim.results) - len(failures)
    print(f"\n✅ {passed}/{len(sim.results)} consultas procesadas correctamente")

    # Assert all pass
    assert len(failures) == 0, f"{len(failures)} failures in simulation"
