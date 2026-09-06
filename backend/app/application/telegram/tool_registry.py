"""Tool registry: exposes deterministic execution layer as LLM-callable tools.

Catálogo consolidado estilo MCP (2026-09-05): una tool por capacidad; las
variantes son parámetros, no tools separadas. Cada tool tiene una pregunta
canónica (en `description`) para eliminar ambigüedad en la selección del LLM.

Contrato:
- El LLM interpreta la intención y elige UNA tool del catálogo.
- El backend ejecuta el handler (services de `application/` o capas de query
  autorizadas). Nunca SQL del modelo.
- `sql_query` NO está en el catálogo ni en el prompt. El SQL Agent queda como
  fallback interno silencioso del path enrutado, nunca elegible por el modelo.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

# Roles con acceso al bot de consultas (gate en orchestrator).
QUERY_ROLES = ("admin", "encargado")


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
# Preguntas canónicas (una por tool — usadas en description y en el test de
# contrato del catálogo).
# ---------------------------------------------------------------------------

CANONICAL_QUESTIONS: dict[str, str] = {
    "list_doctors": "¿Cuántos/cuáles médicos hay con estas características?",
    "doctor_info": "Ficha completa de un médico específico",
    "doctor_availability": "¿Qué días está disponible este médico?",
    "doctor_restrictions": "¿Qué licencias o restricciones tiene este médico o hay activas?",
    "doctor_service_history": "¿Cuántas guardias lleva este médico o cuándo fue su última?",
    "workload_ranking": "¿Quién lleva más o menos carga, o va corto de su meta mensual?",
    "calendar_assignments": "¿Qué guardias hay en estas fechas?",
    "calendar_status": "¿Cómo va el calendario del mes?",
    "slot_recommendation": "¿Quién puede cubrir este día y área?",
    "slot_explanation": "¿Por qué este médico está o no está asignado a este día y área?",
    "doctors_available_on": "¿Quiénes reportaron disponibilidad para este día?",
    "availability_report_status": "¿Quiénes ya reportaron disponibilidad este mes y quiénes no?",
    "mission_list": "¿Qué misiones hay?",
    "mission_status": "¿Cómo va esta misión?",
    "mission_candidates": "¿Quiénes son candidatos para una misión?",
    "confirmation_status": "¿Quiénes confirmaron o faltan por confirmar?",
    "notification_status": "¿Cómo van los envíos de notificaciones?",
    "action_alerts": "¿Qué tengo pendiente por atender?",
    "audit_history": "¿Quién cambió qué y cuándo?",
    "system_config": "¿Qué reglas, áreas con pesos y límites están activos?",
    "generate_report": "Envíame el reporte del mes o de la semana",
    "reply": "Hola, gracias, no entiendo o petición fuera de alcance",
}

_SEX_ENUM = ["M", "F"]
_AREA_HINT = "Área de servicio: Emergencia, Pista o Disponible"


def _p(name: str, canonical: str, *, extra: str = "") -> str:
    """Description de tool: pregunta canónica explícita + detalle."""
    base = f"Pregunta típica: «{canonical}»."
    return f"{base} {extra}".strip()


# ---------------------------------------------------------------------------
# Tool definitions (schemas only — handlers wired at runtime)
# ---------------------------------------------------------------------------

DOCTOR_TOOLS: list[dict[str, Any]] = [
    {
        "name": "list_doctors",
        "description": _p(
            "list_doctors",
            CANONICAL_QUESTIONS["list_doctors"],
            extra=(
                "Lista o cuenta médicos con los filtros indicados. Usa `count: true` "
                "cuando el usuario solo quiere el número. Usa `group_by` cuando pide "
                "conteos agrupados (por sexo, rango o departamento)."
            ),
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "sex": {"type": "string", "enum": _SEX_ENUM, "description": "M (masculino) o F (femenino)"},
                "rank": {"type": "string", "description": "Rango militar exacto (ej: Capitán, Mayor)"},
                "department": {"type": "string", "description": "Departamento (ej: cirugía, pediatría)"},
                "area": {"type": "string", "description": _AREA_HINT},
                "service_active": {"type": "boolean", "description": "Solo médicos con servicio activo (default true)"},
                "pool_active": {"type": "boolean", "description": "Solo médicos activos en el pool de turnos (default true)"},
                "participa_misiones": {"type": "boolean", "description": "Filtrar por participación en misiones"},
                "group_by": {"type": "string", "enum": ["sex", "rank", "department"], "description": "Agrupar conteo por este criterio"},
                "count": {"type": "boolean", "description": "true → devolver solo el número total"},
                "no_assignments_in": {
                    "type": "object",
                    "properties": {
                        "month": {"type": "integer", "description": "Mes (1-12)"},
                        "year": {"type": "integer", "description": "Año (ej: 2026)"},
                    },
                    "required": ["month", "year"],
                    "description": "Médicos sin guardias asignadas en ese mes/año",
                },
            },
        },
    },
    {
        "name": "doctor_info",
        "description": _p(
            "doctor_info",
            CANONICAL_QUESTIONS["doctor_info"],
            extra=(
                "Devuelve rango, departamento, áreas permitidas, límites mensuales, "
                "estado y motivo de inactividad si aplica."
            ),
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "doctor_name": {"type": "string", "description": "Nombre o apellido del médico"},
            },
            "required": ["doctor_name"],
        },
    },
    {
        "name": "doctor_availability",
        "description": _p(
            "doctor_availability",
            CANONICAL_QUESTIONS["doctor_availability"],
            extra="Días del mes, patrón semanal, día preferido y si reportó disponibilidad.",
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "doctor_name": {"type": "string", "description": "Nombre o apellido del médico"},
                "month": {"type": "integer", "description": "Mes (1-12); default: mes actual"},
                "year": {"type": "integer", "description": "Año (ej: 2026); default: año actual"},
            },
            "required": ["doctor_name"],
        },
    },
    {
        "name": "doctor_restrictions",
        "description": _p(
            "doctor_restrictions",
            CANONICAL_QUESTIONS["doctor_restrictions"],
            extra="Sin doctor_name devuelve todas las restricciones activas del período.",
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "doctor_name": {"type": "string", "description": "Nombre o apellido del médico (opcional: todas las activas)"},
                "month": {"type": "integer", "description": "Mes (1-12)"},
                "year": {"type": "integer", "description": "Año (ej: 2026)"},
            },
        },
    },
    {
        "name": "doctor_service_history",
        "description": _p(
            "doctor_service_history",
            CANONICAL_QUESTIONS["doctor_service_history"],
            extra="Total del período, última guardia y áreas cubiertas.",
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "doctor_name": {"type": "string", "description": "Nombre o apellido del médico"},
                "month": {"type": "integer", "description": "Mes (1-12)"},
                "year": {"type": "integer", "description": "Año (ej: 2026)"},
            },
            "required": ["doctor_name"],
        },
    },
    {
        "name": "workload_ranking",
        "description": _p(
            "workload_ranking",
            CANONICAL_QUESTIONS["workload_ranking"],
            extra="Ranking de carga mensual: `load` = servicios asignados; `target_gap` = faltante vs meta.",
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "month": {"type": "integer", "description": "Mes (1-12)"},
                "year": {"type": "integer", "description": "Año (ej: 2026)"},
                "criterion": {
                    "type": "string",
                    "enum": ["load", "target_gap"],
                    "description": "load = más servicios; target_gap = más corto de su meta",
                },
            },
            "required": ["month", "year"],
        },
    },
]

CALENDAR_TOOLS: list[dict[str, Any]] = [
    {
        "name": "calendar_assignments",
        "description": _p(
            "calendar_assignments",
            CANONICAL_QUESTIONS["calendar_assignments"],
            extra="Rango de fechas YYYY-MM-DD. Para un solo día usa la misma fecha en start y end.",
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "start_date": {"type": "string", "description": "Fecha inicio YYYY-MM-DD"},
                "end_date": {"type": "string", "description": "Fecha fin YYYY-MM-DD (igual a start para un día)"},
                "service_area": {"type": "string", "description": _AREA_HINT},
                "doctor_name": {"type": "string", "description": "Filtrar por médico"},
                "source": {"type": "string", "enum": ["manual", "generated"], "description": "Origen de la asignación"},
            },
            "required": ["start_date", "end_date"],
        },
    },
    {
        "name": "calendar_status",
        "description": _p(
            "calendar_status",
            CANONICAL_QUESTIONS["calendar_status"],
            extra="Estado, semanas aprobadas/en borrador, asignaciones por área y huecos sin cubrir.",
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "month": {"type": "integer", "description": "Mes (1-12)"},
                "year": {"type": "integer", "description": "Año (ej: 2026)"},
            },
            "required": ["month", "year"],
        },
    },
    {
        "name": "slot_recommendation",
        "description": _p(
            "slot_recommendation",
            CANONICAL_QUESTIONS["slot_recommendation"],
            extra="Candidatos con razón y advertencias usando la evaluación del backend.",
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Fecha YYYY-MM-DD"},
                "service_area": {"type": "string", "enum": ["Emergencia", "Pista", "Disponible"], "description": _AREA_HINT},
            },
            "required": ["date", "service_area"],
        },
    },
    {
        "name": "slot_explanation",
        "description": _p(
            "slot_explanation",
            CANONICAL_QUESTIONS["slot_explanation"],
            extra="Si está asignado usa el rationale guardado; si no, bloqueos y advertencias de su evaluación.",
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Fecha YYYY-MM-DD"},
                "service_area": {"type": "string", "enum": ["Emergencia", "Pista", "Disponible"], "description": _AREA_HINT},
                "doctor_name": {"type": "string", "description": "Nombre o apellido del médico"},
            },
            "required": ["date", "service_area", "doctor_name"],
        },
    },
]

AVAILABILITY_TOOLS: list[dict[str, Any]] = [
    {
        "name": "doctors_available_on",
        "description": _p(
            "doctors_available_on",
            CANONICAL_QUESTIONS["doctors_available_on"],
            extra="Listado crudo de quienes reportaron disponibilidad, sin evaluar reglas de calendario.",
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Fecha YYYY-MM-DD"},
            },
            "required": ["date"],
        },
    },
    {
        "name": "availability_report_status",
        "description": _p(
            "availability_report_status",
            CANONICAL_QUESTIONS["availability_report_status"],
            extra="Médicos que ya enviaron su disponibilidad mensual y los que faltan.",
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "month": {"type": "integer", "description": "Mes (1-12)"},
                "year": {"type": "integer", "description": "Año (ej: 2026)"},
            },
            "required": ["month", "year"],
        },
    },
]

MISSION_TOOLS: list[dict[str, Any]] = [
    {
        "name": "mission_list",
        "description": _p(
            "mission_list",
            CANONICAL_QUESTIONS["mission_list"],
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["draft", "active", "completed", "cancelled"], "description": "Estado de la misión"},
                "month": {"type": "integer", "description": "Mes (1-12)"},
                "year": {"type": "integer", "description": "Año (ej: 2026)"},
                "include_participants": {"type": "boolean", "description": "Incluir participantes en el listado"},
            },
        },
    },
    {
        "name": "mission_status",
        "description": _p(
            "mission_status",
            CANONICAL_QUESTIONS["mission_status"],
            extra="Participantes, ranking, score y confirmaciones de la misión.",
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "mission_name": {"type": "string", "description": "Nombre o parte del nombre de la misión"},
            },
            "required": ["mission_name"],
        },
    },
    {
        "name": "mission_candidates",
        "description": _p(
            "mission_candidates",
            CANONICAL_QUESTIONS["mission_candidates"],
            extra="Usa el ranking mensual guardado y filtra por la fecha de la misión.",
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "mission_date": {"type": "string", "description": "Fecha de la misión YYYY-MM-DD"},
                "count": {"type": "integer", "description": "Cantidad de candidatos pedida (default 3)"},
            },
            "required": ["mission_date"],
        },
    },
]

CONFIRMATION_TOOLS: list[dict[str, Any]] = [
    {
        "name": "confirmation_status",
        "description": _p(
            "confirmation_status",
            CANONICAL_QUESTIONS["confirmation_status"],
            extra="Solicitudes de confirmación con su estado (pendiente, confirmada, declinada, expirada).",
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "doctor_name": {"type": "string", "description": "Filtrar por médico"},
                "month": {"type": "integer", "description": "Mes (1-12)"},
                "year": {"type": "integer", "description": "Año (ej: 2026)"},
            },
        },
    },
]

NOTIFICATION_TOOLS: list[dict[str, Any]] = [
    {
        "name": "notification_status",
        "description": _p(
            "notification_status",
            CANONICAL_QUESTIONS["notification_status"],
            extra="Incluye fallidas con su error y programadas. Sin `status`, resume todas.",
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["pending", "sent", "failed"], "description": "Estado de las notificaciones"},
                "doctor_name": {"type": "string", "description": "Filtrar por médico destinatario"},
                "month": {"type": "integer", "description": "Mes (1-12); default: mes actual"},
                "year": {"type": "integer", "description": "Año (ej: 2026); default: año actual"},
            },
        },
    },
]

ALERT_TOOLS: list[dict[str, Any]] = [
    {
        "name": "action_alerts",
        "description": _p(
            "action_alerts",
            CANONICAL_QUESTIONS["action_alerts"],
            extra="Alertas de acción del sistema (confirmaciones vencidas, notificaciones fallidas, etc.).",
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["open", "resolved"], "description": "Solo abiertas o ya resueltas (default open)"},
                "severity": {"type": "string", "enum": ["warning", "critical"], "description": "Filtrar por severidad"},
                "section": {"type": "string", "description": "Sección del sistema (ej: confirmations, notifications)"},
            },
        },
    },
]

AUDIT_TOOLS: list[dict[str, Any]] = [
    {
        "name": "audit_history",
        "description": _p(
            "audit_history",
            CANONICAL_QUESTIONS["audit_history"],
            extra="Eventos de auditoría: actor, acción y cuándo.",
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "doctor_name": {"type": "string", "description": "Filtrar por médico afectado"},
                "action_type": {"type": "string", "description": "Tipo de acción (ej: assignment_added, calendar_approved)"},
                "start_date": {"type": "string", "description": "Fecha inicio YYYY-MM-DD"},
                "end_date": {"type": "string", "description": "Fecha fin YYYY-MM-DD"},
            },
        },
    },
]

CONFIG_TOOLS: list[dict[str, Any]] = [
    {
        "name": "system_config",
        "description": _p(
            "system_config",
            CANONICAL_QUESTIONS["system_config"],
            extra="Devuelve áreas de servicio con su peso, reglas activas y límites por defecto.",
        ),
        "parameters": {"type": "object", "properties": {}},
    },
]

REPORT_TOOLS: list[dict[str, Any]] = [
    {
        "name": "generate_report",
        "description": _p(
            "generate_report",
            CANONICAL_QUESTIONS["generate_report"],
            extra="Genera y envía el PDF del calendario mensual o de la lista semanal.",
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": ["monthly", "weekly"], "description": "monthly = calendario completo; weekly = lista semanal"},
                "month": {"type": "integer", "description": "Mes (1-12)"},
                "year": {"type": "integer", "description": "Año (ej: 2026)"},
                "week": {"type": "string", "description": "Para type=weekly: rango o semana (ej: '2026-05-04' o número)"},
            },
            "required": ["type", "month", "year"],
        },
    },
]

GENERAL_TOOLS: list[dict[str, Any]] = [
    {
        "name": "reply",
        "description": _p(
            "reply",
            CANONICAL_QUESTIONS["reply"],
            extra=(
                "Responder directamente SIN consultar datos: saludos, gracias, "
                "despedida, ayuda, petición que no se entiende o fuera de alcance. "
                "clarify = no entendí la petición; out_of_scope = petición fuera del "
                "sistema (ej. escribir, aprobar o modificar algo — eso se hace en el panel web)."
            ),
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "response_type": {
                    "type": "string",
                    "enum": ["greeting", "help", "farewell", "clarify", "out_of_scope"],
                    "description": "Tipo de respuesta conversacional",
                },
            },
        },
    },
]

ALL_TOOLS = (
    DOCTOR_TOOLS
    + CALENDAR_TOOLS
    + AVAILABILITY_TOOLS
    + MISSION_TOOLS
    + CONFIRMATION_TOOLS
    + NOTIFICATION_TOOLS
    + ALERT_TOOLS
    + AUDIT_TOOLS
    + CONFIG_TOOLS
    + REPORT_TOOLS
    + GENERAL_TOOLS
)


def build_tools_prompt() -> str:
    """Genera la sección de herramientas del system prompt del NLU.

    Incluye las 22 tools del catálogo con sus preguntas canónicas.
    `sql_query` NO aparece: el SQL Agent no es elegible por el modelo.
    """
    lines: list[str] = ["HERRAMIENTAS DISPONIBLES:"]
    for index, tool in enumerate(ALL_TOOLS, start=1):
        lines.append(f"\n{index}. {tool['name']}")
        lines.append(f"   {tool['description']}")
        properties = tool["parameters"].get("properties", {})
        if properties:
            param_parts: list[str] = []
            for pname, pschema in properties.items():
                ptype = pschema.get("type", "any")
                pdesc = pschema.get("description", "")
                penum = ""
                if pschema.get("enum"):
                    penum = f" ({'/'.join(str(e) for e in pschema['enum'])})"
                required = " (requerido)" if pname in tool["parameters"].get("required", []) else " (opcional)"
                param_parts.append(f"{pname}: {ptype}{penum}{required} — {pdesc}")
            lines.append("   Parámetros:")
            for part in param_parts:
                lines.append(f"   - {part}")
    return "\n".join(lines)


class ToolRegistry:
    """Registry of tools the LLM can invoke at runtime.

    Enforces per-tool permission checks — *admin* bypasses all checks,
    *encargado* needs explicit permissions for restricted tools.
    """

    # Tools that require specific permissions (admin always bypasses).
    # Vacío por ahora: el catálogo es solo lectura y el acceso ya está
    # restringido a admin/encargado (QUERY_ROLES).
    TOOL_PERMISSIONS: dict[str, list[str]] = {}

    def __init__(self) -> None:
        self._tools: dict[str, Callable[..., Any]] = {}

    def register(self, name: str, handler: Callable[..., Any]) -> None:
        self._tools[name] = handler

    def get(self, name: str) -> Callable[..., Any] | None:
        return self._tools.get(name)

    def execute(
        self,
        tool_name: str,
        params: dict[str, Any],
        user_role: str = "admin",
        user_permissions: list[str] | None = None,
    ) -> Any:
        handler = self._tools.get(tool_name)
        if handler is None:
            raise ValueError(f"Herramienta desconocida: {tool_name}")

        # ── Permission check ──────────────────────────────────────────
        if user_role != "admin":
            required = self.TOOL_PERMISSIONS.get(tool_name)
            if required is not None:
                user_perms = user_permissions or []
                if len(required) == 0:
                    # Empty list = admin-only
                    raise PermissionError(
                        f"La herramienta '{tool_name}' solo está disponible para administradores."
                    )
                if not all(p in user_perms for p in required):
                    missing = [p for p in required if p not in user_perms]
                    raise PermissionError(
                        f"No tienes los permisos necesarios: {', '.join(missing)}"
                    )

        return handler(**params)
