"""Small semantic planner for Telegram conversations.

The planner is intentionally deterministic. It decides the broad operational
domain before memory or SQL execution can pull the message into the wrong path.
"""

import re
from dataclasses import dataclass, field
from typing import Any

from backend.app.application.telegram.conversation_contract import TERM_PRIORITY_RULES
from backend.app.application.telegram.entity_resolver import normalize_user_message
from backend.app.application.telegram.memory import SessionState


@dataclass(frozen=True)
class ConversationPlan:
    domain: str
    action: str
    entities: dict[str, Any] = field(default_factory=dict)
    period: dict[str, Any] | None = None
    output_format: str | None = None
    is_followup: bool = False
    memory_policy: str = "none"
    route: str = "direct_reply"
    confidence: float = 0.0
    clarification_question: str | None = None


_MONTH_RE = re.compile(
    r"\b(enero|febrero|marzo|abril|mayo|junio|julio|agosto|"
    r"septiembre|octubre|noviembre|diciembre)\b"
)

_COUNT_RE = re.compile(r"\b(cuantos?|cuantas?|cauantos?|cauantas?|total)\b|\b\d+\s+o\s+\d+\b")
_LIST_RE = re.compile(r"\b(cuales|quienes|lista|listado|dame|muestra|muestrame|top)\b")
_EXPORT_RE = re.compile(
    r"\b(exporta|exportar|exportalo|exportalos|exportarlo|exportarlos|"
    r"esporta|esportar|esportalo|esportalos|"
    r"reporte|pdf|excel|xlsx|xls)\b"
)
_SHORT_FOLLOWUP_RE = re.compile(
    r"^\s*(y\s+)?(el|la|los|las|de|del|en|a)?\s*"
    r"(enero|febrero|marzo|abril|mayo|junio|julio|agosto|"
    r"septiembre|octubre|noviembre|diciembre|masculinos?|femeninos?|feminios?|"
    r"femenios?|pdf|excel|"
    r"listado|lista|exportalo|exportalos|exportarlo|exportarlos|"
    r"esportalo|esportalos)"
    r"\??\s*$"
)


def _action_from_text(text: str) -> str:
    if _EXPORT_RE.search(text):
        return "exportar"
    if _COUNT_RE.search(text):
        return "contar"
    if re.search(r"\b(no\s+han|pendientes?|sin)\s+confirm", text):
        return "listar"
    if _LIST_RE.search(text):
        return "listar"
    if re.search(r"\b(resumen|resume|resumir)\b", text):
        return "resumir"
    if re.search(r"\b(busca|buscar|detalle|historial)\b", text):
        return "buscar"
    if re.search(r"\b(compara|comparar|diferencia)\b", text):
        return "comparar"
    return "explicar"


def _route_for_domain(domain: str) -> str:
    if domain in {"medicos", "calendario", "misiones"}:
        return "deterministic_service"
    if domain in {"ranking_misiones", "confirmaciones", "auditoria"}:
        return "registry_query"
    if domain == "reportes":
        return "deterministic_service"
    return "direct_reply"


def _domain_candidates(text: str) -> set[str]:
    candidates: set[str] = set()
    doctor_service_status = bool(
        re.search(r"\b(?:in)?activos?\s+para\s+servicio\b|\bdisponibles?\b", text)
        and re.search(r"\b(medicos?|doctores?)\b", text)
    )

    if "ranking" in text and re.search(r"\bmision(?:es)?\b", text):
        candidates.add("ranking_misiones")
    if re.search(r"\b(confirmad[oa]s?|confirmar|recibido|pendientes?)\b", text):
        candidates.add("confirmaciones")
    if re.search(r"\b(aprobo|aprobó|auditoria|auditoría|cambios?|modifico|modificó)\b", text):
        candidates.add("auditoria")
    if re.search(r"\b(mision|misiones)\b", text):
        candidates.add("misiones")
    if not doctor_service_status and re.search(
        r"\b(calendario|servicio|servicios|turno|turnos|asignad[oa]s?|"
        r"incluid[oa]s?|primera semana|primea semana|segunda semana|seguna semana|"
        r"tercera semana|cuarta semana)\b",
        text,
    ):
        candidates.add("calendario")
    if re.search(r"\b(reporte|pdf|excel|xlsx|xls)\b", text):
        candidates.add("reportes")
    if re.search(
        r"\b(medicos?|doctores?|cabos?|pasantes?|sargentos?|masculinos?|"
        r"femeninos?|hombres?|mujeres?|disponibles?|activo para servicio)\b",
        text,
    ):
        candidates.add("medicos")

    if "reportes" in candidates and len(candidates) > 1:
        candidates.remove("reportes")

    return candidates


def _choose_domain(candidates: set[str], session_state: SessionState | None) -> str:
    if candidates:
        return min(candidates, key=lambda d: TERM_PRIORITY_RULES.get(d, 999))
    if session_state is not None and session_state.last_domain == "calendar_assignments":
        return "calendario"
    if session_state is not None and session_state.last_domain:
        if session_state.last_domain == "doctors":
            return "medicos"
        if session_state.last_domain == "mission_ranking":
            return "ranking_misiones"
    return "reportes"


def _is_short_followup(text: str) -> bool:
    if _SHORT_FOLLOWUP_RE.match(text):
        return True
    words = text.replace("?", "").split()
    if len(words) <= 5 and bool(_MONTH_RE.search(text)):
        return True
    if len(words) <= 6 and re.search(
        r"\b(masculinos?|femeninos?|feminios?|femenios?)\b|\b\d+\s+o\s+\d+\b",
        text,
    ):
        return True
    if len(words) <= 5 and re.search(
        r"\b(exportalo|exportalos|exportarlo|exportarlos|esportalo|esportalos|"
        r"pdf|excel|xlsx)\b",
        text,
    ):
        return True
    return False


def _memory_policy(
    text: str,
    domain: str,
    action: str,
    session_state: SessionState | None,
    explicit_candidates: set[str],
) -> tuple[bool, str]:
    if session_state is None:
        return False, "none"
    if not _is_short_followup(text):
        return False, "none"
    if action == "exportar":
        return True, "reuse_last_result_for_export"
    if explicit_candidates and domain not in {"calendario", "medicos"}:
        return False, "none"
    if domain == "calendario" and _MONTH_RE.search(text):
        return True, "reuse_last_period"
    if domain == "medicos":
        return True, "reuse_last_filters"
    return True, "same_domain_only"


def build_conversation_plan(
    user_text: str,
    *,
    resolved_entities: dict[str, Any] | None = None,
    session_state: SessionState | None = None,
) -> ConversationPlan:
    """Return the semantic execution plan for a Telegram message."""
    text = normalize_user_message(user_text)
    entities = dict(resolved_entities or {})
    action = _action_from_text(text)
    candidates = _domain_candidates(text)
    domain = _choose_domain(candidates, session_state)
    if (
        action == "explicar"
        and _is_short_followup(text)
        and session_state is not None
        and session_state.last_query_type
    ):
        if session_state.last_query_type.startswith("count_"):
            action = "contar"
        elif session_state.last_query_type.startswith("list_"):
            action = "listar"
    is_followup, memory_policy = _memory_policy(
        text,
        domain,
        action,
        session_state,
        candidates,
    )
    confidence = 0.9 if candidates or is_followup else 0.5
    route = _route_for_domain(domain)
    clarification_question = None
    if confidence < 0.6 and action in {"contar", "listar", "exportar"}:
        route = "clarification"
        clarification_question = (
            "Necesito que me indiques sobre que informacion del sistema quieres consultar."
        )

    return ConversationPlan(
        domain=domain,
        action=action,
        entities=entities,
        period=entities.get("date") if isinstance(entities.get("date"), dict) else None,
        output_format=entities.get("format") if isinstance(entities.get("format"), str) else None,
        is_followup=is_followup,
        memory_policy=memory_policy,
        route=route,
        confidence=confidence,
        clarification_question=clarification_question,
    )
