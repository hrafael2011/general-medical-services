"""Alcance declarado del bot: qué consultas contesta y cuáles rechaza.

El bot sirve un conjunto **verificado** de capacidades. Cuando el NLU pide
algo fuera de ese conjunto —o pide un filtro que los servicios determinísticos
no saben aplicar— la respuesta correcta no es la lista completa de médicos:
es decir que la consulta no es parte del sistema.

Por qué existe este módulo: el NLU no era el problema. Clasifica bien
(«Que hora es?» → `reply/out_of_scope`). El problema era que el enrutado
ignoraba esa clasificación y caía a un `domain="medicos"` por defecto, así que
el servicio de médicos —cuyo filtro vacío nunca devuelve `None`— contestaba
CUALQUIER pregunta con los 41 médicos. Medido sobre el corpus: 52 turnos.

Las listas de abajo salen de medir el corpus, no de suponer:

- `SUPPORTED_TOOLS`: tools que produjeron aciertos y **cero** volcados.
- `UNHONORED_DOCTOR_PARAMS`: parámetros que el NLU completa y
  `DoctorQueryService` descarta en silencio. Verificado: 15 turnos
  («Dame un resumen por rango» → 41 médicos en vez de un desglose).

Deliberadamente NO está acá `workload_ranking` pese a tener un acierto: ese
acierto se resuelve en la capa semántica, que corre ANTES de este gate, y lo
que llega hasta acá con esa tool es siempre un volcado.

El chequeo de parámetros se aplica SÓLO a `DOCTOR_TOOLS`. Aplicarlo a todo
rompía «Quienes estan en Pista en julio?»: `service_area` sí lo honra el
servicio de calendario.

```
    from backend.app.application.telegram.scope_gate import check_scope

    motivo = check_scope(tool, params)   # None = adelante, str = rechazar
```
"""

from __future__ import annotations

from typing import Any

# Tools que resuelve el servicio de médicos. Es una lista aparte porque el
# chequeo de parámetros de abajo SÓLO vale para ellas: `service_area`, por
# ejemplo, sí lo aplica el servicio de calendario, y rechazarlo en todas partes
# rompía «Quienes estan en Pista en julio?».
DOCTOR_TOOLS: frozenset[str] = frozenset(
    {
        "list_doctors",
        "count_doctors",
        "doctors_by_sex",
        "doctors_by_rank",
        "doctors_by_department",
        "doctor_info",
    }
)

# Tools que los servicios determinísticos SÍ saben responder.
OTHER_SUPPORTED_TOOLS: frozenset[str] = frozenset(
    {
        "calendar_status",
        "calendar_assignments",
        "mission_list",
        "confirmation_status",
        "generate_report",
    }
)

SUPPORTED_TOOLS: frozenset[str] = DOCTOR_TOOLS | OTHER_SUPPORTED_TOOLS

# El NLU completa estos parámetros y `DoctorQueryService` no los mira: los
# descarta y devuelve TODOS los médicos, así que la respuesta parece válida
# y es falsa. Rechazar es más honesto que responder cualquier cosa.
UNHONORED_DOCTOR_PARAMS: frozenset[str] = frozenset(
    {
        "group_by",
        "service_active",
        "pool_active",
        "service_area",
        "no_assignments_in",
        "participa_misiones",
    }
)

# Tool conversacional: no consulta datos. Se deja pasar para que lo conteste
# el agente, que tiene la respuesta adecuada (saludo, ayuda, fuera de alcance).
CONVERSATIONAL_TOOLS: frozenset[str] = frozenset({"reply"})

SCOPE_REFUSAL = (
    "Esa consulta no forma parte de las funciones de este asistente. "
    "Puedo consultar médicos, calendario y guardias, misiones y confirmaciones."
)


def check_scope(tool: str | None, params: dict[str, Any] | None) -> str | None:
    """Devuelve el motivo del rechazo, o `None` si la consulta está en alcance.

    `tool is None` (camino sin NLU) no se juzga: sin clasificación no hay nada
    que comparar contra el alcance, y rechazar a ciegas rompería el camino
    legacy.
    """
    if tool is None or tool in CONVERSATIONAL_TOOLS:
        return None
    if tool not in SUPPORTED_TOOLS:
        return "tool_fuera_de_alcance"
    if tool in DOCTOR_TOOLS and UNHONORED_DOCTOR_PARAMS & set(params or {}):
        return "filtro_no_soportado"
    return None
