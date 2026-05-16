"""Shared conversational contract for Telegram system questions.

This module keeps business-language meanings in one place so the agent,
deterministic routes, and tests can agree on what operational terms mean.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ConversationConcept:
    canonical: str
    terms: tuple[str, ...]
    meaning: str
    response_rule: str


CONVERSATION_CONTRACT: tuple[ConversationConcept, ...] = (
    ConversationConcept(
        canonical="doctor_available_for_service",
        terms=("disponible", "disponibles", "activo para servicio", "activos para servicio"),
        meaning="Medicos con doctors.active = TRUE y doctors.service_active = TRUE.",
        response_rule="Responder solo con medicos activos para servicio.",
    ),
    ConversationConcept(
        canonical="calendar_assignment",
        terms=("de servicio", "en servicio", "servicio", "turno", "turnos"),
        meaning="Asignaciones registradas en calendar_assignments para una fecha o periodo.",
        response_rule="Consultar asignaciones reales del calendario; no inferir disponibilidad.",
    ),
    ConversationConcept(
        canonical="calendar_participant",
        terms=("incluido en calendario", "incluidos en calendario", "asignado en calendario"),
        meaning="Medico distinto que tiene al menos una asignacion en un calendario del periodo.",
        response_rule="Contar medicos distintos asignados al calendario solicitado.",
    ),
    ConversationConcept(
        canonical="approved_calendar",
        terms=("aprobado", "calendario aprobado", "oficial"),
        meaning="Calendario y version con estado approved.",
        response_rule="Cuando se pregunte por informacion oficial, usar solo calendarios aprobados.",
    ),
    ConversationConcept(
        canonical="draft_calendar",
        terms=("borrador", "draft", "pendiente", "pendiente de aprobacion"),
        meaning="Calendario o version todavia no aprobado.",
        response_rule="Si solo hay borrador, decir que no hay calendario oficial aprobado y mencionar el borrador.",
    ),
    ConversationConcept(
        canonical="mission_ranking",
        terms=("ranking", "ranking de misiones", "candidatos para misiones"),
        meaning="Orden mensual de candidatos a misiones calculado para un calendario aprobado.",
        response_rule="Mostrar ranking del mes solicitado solo si existe para el calendario aprobado.",
    ),
)


def resolve_system_concept(term: str) -> ConversationConcept:
    """Resolve a user-facing term to a known system concept."""
    normalized = term.strip().lower()
    for concept in CONVERSATION_CONTRACT:
        if normalized in concept.terms:
            return concept
    raise KeyError(term)


def format_contract_for_prompt() -> str:
    """Return a compact prompt section with the system language contract."""
    lines = [
        "CONTRATO CONVERSACIONAL DEL SISTEMA:",
        "- No inventes conteos, nombres, listados, rankings ni estados.",
        "- Si una respuesta requiere datos, debe salir de query/export o de una consulta validada.",
    ]
    for concept in CONVERSATION_CONTRACT:
        terms = ", ".join(concept.terms)
        lines.append(
            f"- {concept.canonical}: terminos [{terms}]. "
            f"Significa: {concept.meaning} Regla: {concept.response_rule}"
        )
    return "\n".join(lines)
