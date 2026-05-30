"""Tool registry: exposes deterministic execution layer as LLM-callable tools."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema for params
    handler: Callable[..., Any] | None = None

    @property
    def json_schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


# ---------------------------------------------------------------------------
# Tool definitions (schemas only — handlers are wired at runtime)
# ---------------------------------------------------------------------------

DOCTOR_TOOLS: list[dict[str, Any]] = [
    {
        "name": "list_doctors",
        "description": (
            "Lista doctores activos con filtros opcionales. "
            "Usar para preguntas como 'qué doctores hay en cirugía', "
            "'muéstrame las doctoras', 'doctores con rango capitán'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "sex": {"type": "string", "enum": ["F", "M"], "description": "F para femenino, M para masculino"},
                "rank": {"type": "string", "description": "Nombre del rango militar (ej: capitán, mayor, teniente coronel)"},
                "department": {"type": "string", "description": "Nombre del departamento (ej: cirugía, pediatría, medicina general)"},
                "service_active": {"type": "boolean", "description": "Filtrar solo activos para servicio (default true)"},
            },
        },
    },
    {
        "name": "count_doctors",
        "description": (
            "Cuenta doctores con filtros opcionales. "
            "Usar para 'cuántos médicos hay', 'cuántas doctoras en cardiología', "
            "'cantidad de capitanes disponibles'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "sex": {"type": "string", "enum": ["F", "M"]},
                "rank": {"type": "string"},
                "department": {"type": "string"},
                "service_active": {"type": "boolean"},
            },
        },
    },
    {
        "name": "doctors_by_sex",
        "description": "Agrupa doctores por sexo (F/M). Usar para 'cuántos hombres y mujeres hay en el servicio'.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "doctors_by_rank",
        "description": "Agrupa doctores por rango militar. Usar para 'cuántos doctores hay por cada rango'.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "doctors_by_department",
        "description": "Agrupa doctores por departamento. Usar para 'cuántos doctores hay en cada departamento'.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "doctor_last_service",
        "description": (
            "Último servicio registrado de un doctor específico. "
            "Usar para 'cuándo fue la última guardia de la Dra. Rodríguez'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "doctor_name": {"type": "string", "description": "Nombre o apellido del doctor"},
            },
            "required": ["doctor_name"],
        },
    },
    {
        "name": "doctor_service_load",
        "description": (
            "Carga de servicios de doctores en un período. "
            "Usar para 'cuántas guardias ha hecho el Dr. Pérez este mes'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "doctor_name": {"type": "string"},
                "month": {"type": "integer", "description": "Mes (1-12)"},
                "year": {"type": "integer", "description": "Año (ej: 2026)"},
            },
        },
    },
    {
        "name": "unassigned_doctors",
        "description": (
            "Doctores sin asignar en un mes específico. "
            "Usar para 'qué doctores no tienen guardia este mes'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "month": {"type": "integer"},
                "year": {"type": "integer"},
            },
            "required": ["month", "year"],
        },
    },
]

CALENDAR_TOOLS: list[dict[str, Any]] = [
    {
        "name": "calendar_assignments",
        "description": (
            "Asignaciones de guardia en un rango de fechas. "
            "Usar para 'qué doctores están de servicio el lunes 1 de junio', "
            "'muéstrame las guardias de esta semana'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "start_date": {"type": "string", "description": "Fecha inicio YYYY-MM-DD"},
                "end_date": {"type": "string", "description": "Fecha fin YYYY-MM-DD"},
                "service_area": {"type": "string", "description": "Área de servicio (emergencia, pista, disponible)"},
            },
            "required": ["start_date", "end_date"],
        },
    },
    {
        "name": "calendar_assigned_count",
        "description": (
            "Conteo de doctores asignados en un mes. "
            "Usar para 'cuántos doctores tienen guardia en junio'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "month": {"type": "integer"},
                "year": {"type": "integer"},
            },
            "required": ["month", "year"],
        },
    },
    {
        "name": "calendar_status",
        "description": (
            "Estado de calendarios (draft, approved). "
            "Usar para 'qué calendarios están aprobados', 'hay calendario para junio'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "month": {"type": "integer"},
                "year": {"type": "integer"},
                "status": {"type": "string", "enum": ["draft", "approved"]},
            },
        },
    },
]

MISSION_TOOLS: list[dict[str, Any]] = [
    {
        "name": "mission_list",
        "description": "Lista misiones médicas. Usar para 'qué misiones hay', 'muéstrame las misiones activas'.",
        "parameters": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "description": "Estado: active, completed, cancelled"},
                "month": {"type": "integer"},
                "year": {"type": "integer"},
            },
        },
    },
    {
        "name": "mission_status",
        "description": "Estado detallado de misiones con participantes. Usar para 'cómo va la misión X'.",
        "parameters": {
            "type": "object",
            "properties": {
                "mission_name": {"type": "string", "description": "Nombre o parte del nombre de la misión"},
            },
        },
    },
]

GENERAL_TOOLS: list[dict[str, Any]] = [
    {
        "name": "sql_query",
        "description": (
            "Consulta SQL genérica para preguntas que no calzan en las herramientas anteriores. "
            "El sistema genera SQL automáticamente a partir de lenguaje natural. "
            "Usar como último recurso cuando ninguna otra herramienta sirve."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "La pregunta exacta del usuario en lenguaje natural"},
            },
            "required": ["question"],
        },
    },
    {
        "name": "reply",
        "description": (
            "Responder directamente sin consultar datos. "
            "Usar para saludos ('hola'), agradecimientos ('gracias'), "
            "o preguntas conversacionales que no requieren datos del sistema."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "response_type": {
                    "type": "string",
                    "enum": ["greeting", "help", "farewell", "unknown"],
                    "description": "Tipo de respuesta conversacional",
                },
            },
        },
    },
]

ALL_TOOLS = DOCTOR_TOOLS + CALENDAR_TOOLS + MISSION_TOOLS + GENERAL_TOOLS


def build_tools_prompt() -> str:
    """Generate the tools section for the NLU system prompt."""
    lines = ["## Herramientas Disponibles\n"]
    for tool in ALL_TOOLS:
        lines.append(f"### {tool['name']}")
        lines.append(f"Descripción: {tool['description']}")
        params = tool.get("parameters", {})
        required = params.get("required", [])
        props = params.get("properties", {})
        if props:
            lines.append("Parámetros:")
            for pname, pinfo in props.items():
                req = " (requerido)" if pname in required else ""
                lines.append(f"  - {pname}: {pinfo.get('description', pinfo.get('type', ''))}{req}")
        lines.append("")
    return "\n".join(lines)


class ToolRegistry:
    """Registry of tools the LLM can invoke at runtime."""

    def __init__(self) -> None:
        self._tools: dict[str, Callable[..., Any]] = {}

    def register(self, name: str, handler: Callable[..., Any]) -> None:
        self._tools[name] = handler

    def get(self, name: str) -> Callable[..., Any] | None:
        return self._tools.get(name)

    def execute(self, tool_name: str, params: dict[str, Any]) -> Any:
        handler = self._tools.get(tool_name)
        if handler is None:
            raise ValueError(f"Herramienta desconocida: {tool_name}")
        return handler(**params)
