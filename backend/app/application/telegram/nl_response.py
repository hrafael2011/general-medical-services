"""Natural language response generation — primary response path.

Replaces the old tabular format_rows() as the default output formatter.
Uses DeepSeek to convert structured tool output into conversational Spanish.
"""

from __future__ import annotations

import json
from typing import Any

from backend.app.application.telegram.llm import LLMProvider

_NL_SYSTEM_PROMPT = """Eres un asistente médico-militar conciso que responde consultas sobre turnos y guardias.

Reglas:
- Usa SOLO los datos proporcionados abajo. NO inventes información.
- Si los datos están vacíos o no existen, explica la causa probable:
  * Sin doctores que coincidan → "No encontré doctores con ese criterio."
  * Sin calendario → "No hay un calendario creado para ese mes. ¿Quieres crear uno?"
  * Sin asignaciones → "Ese calendario existe pero no tiene guardias asignadas todavía."
- Para conteos: responde en una frase. Ej: "Hay 22 doctoras activas en el servicio."
- Para listas (≤10 items): usa viñetas con nombre, rango y departamento.
- Para listas (>10 items): da un resumen numérico y ofrece detallar si el usuario quiere.
- Sé conversacional pero profesional. Si algo es ambiguo, pide clarificación.
- Si el usuario pregunta algo que el sistema no puede responder, sé honesto y sugiere alternativas."""

_NL_EMPTY_PROMPT = """Eres un asistente médico-militar. El usuario hizo una consulta pero el sistema no encontró datos.

Genera una respuesta natural en español que:
1. Reconozca la consulta del usuario
2. Explique por qué no hay datos (sin calendario, sin doctores con ese criterio, etc.)
3. Sugiera una acción o alternativa

Contexto de la herramienta usada: {tool_name}
Resultado: {tool_result}

Responde solo con el texto de la respuesta."""


def generate_response(
    llm: LLMProvider,
    user_message: str,
    tool_name: str,
    tool_result: dict[str, Any] | None,
    conversation_history: list[dict[str, str]] | None = None,
) -> str:
    """Generate a natural language response from tool output.

    Args:
        llm: LLM provider (DeepSeek or fake for tests).
        user_message: Original user text.
        tool_name: Name of the tool that was invoked.
        tool_result: Structured output from the tool execution.
        conversation_history: Previous messages in this conversation.

    Returns:
        Natural Spanish response text.
    """
    if tool_result is None:
        return _generate_error_response(llm, user_message, tool_name)

    # Extract the meaningful data from the tool result
    data = _extract_data(tool_result)

    # If data is empty, generate contextual empty response
    if _is_empty(data):
        return _generate_empty_response(llm, user_message, tool_name, tool_result)

    # Build a compact context with the data
    data_context = _build_data_context(tool_name, data)

    # Build messages for the LLM
    messages: list[dict[str, str]] = [{"role": "system", "content": _NL_SYSTEM_PROMPT}]

    if conversation_history:
        messages.extend(conversation_history[-6:])  # Last 3 exchanges

    messages.append({
        "role": "user",
        "content": f"Usuario preguntó: \"{user_message}\"\n\nDatos del sistema:\n{data_context}\n\nGenera una respuesta natural y útil.",
    })

    try:
        response = llm.chat_complete(messages, temperature=0.3)
        return response.strip()
    except Exception:
        # Fallback: format the data simply
        return _format_fallback(tool_name, data)


def _extract_data(result: dict[str, Any]) -> Any:
    """Extract the meaningful payload from a tool result dict."""
    # AgentResult-like: has response_text
    if "response_text" in result:
        return result.get("tool_result", result)
    # Direct data payload
    if "data" in result:
        return result["data"]
    if "rows" in result:
        return result["rows"]
    if "items" in result:
        return result["items"]
    return result


def _is_empty(data: Any) -> bool:
    """Check if the extracted data is effectively empty."""
    if data is None:
        return True
    if isinstance(data, (list, dict)) and len(data) == 0:
        return True
    if isinstance(data, dict):
        # Check common count patterns
        total = data.get("total", data.get("count", data.get("row_count")))
        if total is not None and total == 0:
            return True
        # Check if it's a result dict with only metadata
        if "rows" in data and len(data.get("rows", [])) == 0:
            return True
    return False


def _build_data_context(tool_name: str, data: Any) -> str:
    """Build a compact text representation of the tool output."""
    if isinstance(data, list):
        if len(data) <= 30:
            return f"Herramienta: {tool_name}\nResultados ({len(data)}):\n" + json.dumps(
                data, ensure_ascii=False, default=str, indent=2
            )
        else:
            return f"Herramienta: {tool_name}\nResultados ({len(data)}):\n" + json.dumps(
                data[:30], ensure_ascii=False, default=str, indent=2
            ) + f"\n... y {len(data) - 30} resultados más."
    return f"Herramienta: {tool_name}\nResultado:\n" + json.dumps(
        data, ensure_ascii=False, default=str, indent=2
    )


def _generate_empty_response(
    llm: LLMProvider,
    user_message: str,
    tool_name: str,
    tool_result: dict[str, Any] | None,
) -> str:
    """Generate a helpful response when no data was found."""
    prompt = _NL_EMPTY_PROMPT.format(
        tool_name=tool_name,
        tool_result=json.dumps(tool_result, ensure_ascii=False, default=str),
    )
    try:
        response = llm.complete(system="", user=f"Usuario preguntó: \"{user_message}\"\n\n{prompt}", temperature=0.3)
        return response.strip()
    except Exception:
        return f"No encontré datos sobre \"{user_message}\". ¿Puedes darme más detalles?"


def _generate_error_response(llm: LLMProvider, user_message: str, tool_name: str) -> str:
    """Generate a helpful error response."""
    try:
        response = llm.complete(
            system="Eres un asistente médico-militar. Responde en una frase.",
            user=f"El usuario preguntó '{user_message}' pero hubo un error al consultar la herramienta '{tool_name}'. Discúlpate brevemente y sugiere intentar de otra forma.",
            temperature=0.3,
        )
        return response.strip()
    except Exception:
        return "Hubo un error al procesar tu consulta. ¿Podrías intentarlo de otra forma?"


def _format_fallback(tool_name: str, data: Any) -> str:
    """Simple text formatting when the LLM is unavailable."""
    if isinstance(data, list):
        if len(data) == 0:
            return "No se encontraron resultados."
        if len(data) == 1 and isinstance(data[0], dict):
            parts = [f"{k}: {v}" for k, v in data[0].items() if v is not None]
            return "Resultado: " + " | ".join(parts)
        return f"Se encontraron {len(data)} resultados."
    if isinstance(data, dict):
        total = data.get("total", data.get("count", ""))
        if total:
            return f"Total: {total}"
    return str(data)
