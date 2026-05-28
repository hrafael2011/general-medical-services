"""IntentClassifier — LLM-based intent classification for Telegram messages.

Replaces the deterministic keyword-matching pipeline (ConversationPlanner +
intent matchers) with a single focused LLM call that maps natural language
to structured intent. The LLM receives:
- User text
- Pre-resolved entities (doctors, dates, areas, ranks from EntityResolver)
- Available domains and their metrics
- Conversation history summary

Returns a ClassifiedIntent that routes directly to the existing execution layer.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from backend.app.application.telegram.llm import LLMProvider

logger = logging.getLogger(__name__)


@dataclass
class ClassifiedIntent:
    """Structured intent produced by the LLM classifier."""
    domain: str
    action: str  # "query", "export", "reply", "ambiguous"
    metric: str | None = None  # semantic layer metric name, e.g. "doctors_by_sex"
    query_type: str | None = None  # IntentRouter query_type, e.g. "list_doctors_by_rank"
    params: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    response_text: str | None = None
    format: str | None = None  # "pdf" or "excel" for exports


# Domains and their available metrics — single source of truth.
# When new metrics are added to the Semantic Layer or IntentRouter,
# they must be registered here so the LLM knows about them.

AVAILABLE_DOMAINS: dict[str, dict] = {
    "medicos": {
        "description": "Informacion sobre doctores, personal medico",
        "metrics": {
            "total_doctors": "Cantidad total de doctores",
            "doctors_by_sex": "Doctores agrupados por sexo (male/female)",
            "doctors_by_rank": "Doctores agrupados por rango",
            "doctors_by_department": "Doctores agrupados por departamento",
            "duplicate_doctor_names": "Doctores con nombres duplicados",
            "last_service_by_doctor": "Ultimo servicio realizado por cada doctor",
            "doctor_service_load": "Carga de servicios por doctor (historial)",
            "unassigned_doctors": "Doctores sin asignar a servicio",
        },
        "query_types": {
            "list_doctors": "Listado de doctores",
            "list_doctors_by_rank": "Doctores filtrados por rango",
            "list_doctors_by_department": "Doctores filtrados por departamento",
            "list_doctors_by_sex": "Doctores filtrados por sexo",
            "count_doctors": "Conteo de doctores",
            "count_doctors_by_sex": "Conteo de doctores por sexo",
            "count_doctors_by_rank": "Conteo de doctores por rango",
        },
    },
    "calendario": {
        "description": "Calendario de servicios, turnos, asignaciones",
        "metrics": {
            "calendar_status": "Estado actual del calendario (aprobado/borrador)",
            "total_services": "Total de servicios asignados",
            "assigned_doctors_count": "Cantidad de doctores asignados",
            "unresolved_gaps": "Huecos sin cubrir en el calendario",
            "pending_confirmations": "Confirmaciones de servicio pendientes",
        },
        "query_types": {
            "list_calendar_assignments": "Asignaciones del calendario",
            "list_services_by_area": "Servicios por area",
            "count_assigned_doctors_by_month": "Doctores asignados por mes",
        },
    },
    "misiones": {
        "description": "Misiones medicas, ranking, participantes",
        "metrics": {
            "active_missions": "Misiones activas o programadas",
            "mission_ranking": "Ranking de doctores para misiones",
            "pending_confirmations": "Confirmaciones de mision pendientes",
        },
        "query_types": {
            "active_missions": "Lista de misiones activas",
            "mission_ranking": "Ranking de candidatos para misiones",
        },
    },
    "general": {
        "description": "Consultas generales, ayuda, conversacion",
    },
}


SYSTEM_PROMPT = """\
Eres un clasificador de intenciones para un sistema de turnos medicos.
Traduce el mensaje del usuario a una intencion estructurada.

DOMINIOS DISPONIBLES:
{domains}

ENTIDADES DETECTADAS (pre-procesadas del mensaje):
{entity_hints}

Responde UNICAMENTE con JSON en este formato exacto:
{{"domain": "<dominio>", "action": "<accion>", "metric": "<metrica o null>", "query_type": "<query_type o null>", "params": {{...}}, "confidence": <0.0-1.0>, "response_text": "<respuesta o null>", "format": "<pdf|excel o null>"}}

REGLAS:
- domain: elige el dominio mas adecuado de la lista.
- action: "query" para consultas de datos, "export" para exportar a PDF/Excel, "reply" para saludos, "ambiguous" si no entendes.
- metric: si el dominio tiene metrics, elige la mas adecuada. Si no, null.
- query_type: si el dominio tiene query_types, elige el mas adecuado. Si no, null.
- params: parametros extraidos del mensaje (mes, año, sexo, rango, etc). Usa los valores EXACTOS de entidades detectadas.
- confidence: que tan seguro estas de la clasificacion (0.0-1.0).
- response_text: solo para action="reply" o "ambiguous".
- format: "pdf" o "excel" si el usuario pide exportar, null si no.

IMPORTANTE:
- NUNCA inventes nombres, cantidades ni datos que no esten en el mensaje o entidades.
- Si el mensaje es un saludo o conversacion casual, usa action="reply".
- Si no entendes, usa action="ambiguous" con confidence < 0.5.
- Responde en el MISMO IDIOMA del usuario.
Sin explicaciones ni markdown."""


def _build_domains_text() -> str:
    """Format available domains for the LLM prompt."""
    lines: list[str] = []
    for domain_name, domain_info in AVAILABLE_DOMAINS.items():
        lines.append(f"\n[{domain_name}] {domain_info.get('description', '')}")
        metrics = domain_info.get("metrics", {})
        if metrics:
            lines.append("  Metrics:")
            for metric_name, metric_desc in metrics.items():
                lines.append(f"    - {metric_name}: {metric_desc}")
        query_types = domain_info.get("query_types", {})
        if query_types:
            lines.append("  Query Types:")
            for qt_name, qt_desc in query_types.items():
                lines.append(f"    - {qt_name}: {qt_desc}")
    return "\n".join(lines)


class IntentClassifier:
    """Classifies user messages into structured intents using an LLM."""

    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm
        self._domains_text = _build_domains_text()

    def classify(
        self,
        user_text: str,
        *,
        entity_hints: str = "",
        resolved_entities: dict[str, Any] | None = None,
    ) -> ClassifiedIntent:
        """Classify a user message into a structured intent.

        Args:
            user_text: Raw user message.
            entity_hints: Pre-resolved entity hints from EntityResolver.
            resolved_entities: Full resolved entities dict.

        Returns:
            ClassifiedIntent ready to route to the execution layer.
        """
        system_prompt = SYSTEM_PROMPT.format(
            domains=self._domains_text,
            entity_hints=entity_hints or "(ninguna)",
        )

        messages: list[dict] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ]

        response = self._llm.chat_complete(messages, temperature=0.0, json_mode=True)
        response = response.strip()

        parsed = self._parse_response(response)
        if parsed is None:
            # Retry without json_mode
            response = self._llm.chat_complete(messages, temperature=0.0, json_mode=False)
            response = response.strip()
            parsed = self._parse_response(response)

        if parsed is None:
            return ClassifiedIntent(
                domain="general",
                action="ambiguous",
                confidence=0.0,
                response_text="No pude procesar tu consulta. Intenta de nuevo.",
            )

        return ClassifiedIntent(
            domain=parsed.get("domain", "general"),
            action=parsed.get("action", "ambiguous"),
            metric=parsed.get("metric"),
            query_type=parsed.get("query_type"),
            params=parsed.get("params", {}),
            confidence=float(parsed.get("confidence", 0.5)),
            response_text=parsed.get("response_text"),
            format=parsed.get("format"),
        )

    def _parse_response(self, response: str) -> dict | None:
        """Extract JSON from LLM response. Returns None on failure."""
        if not response:
            return None
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code blocks
            import re
            match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    pass
        return None
