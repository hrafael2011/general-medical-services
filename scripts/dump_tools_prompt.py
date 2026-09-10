#!/usr/bin/env python
"""Genera docs/telegram-tools-prompt.md — el catálogo literal que lee el NLU.

El `.md` NO se escribe a mano: se produce ejecutando `build_tools_prompt()`, así
que su bloque principal es byte a byte lo que entra al system prompt del modelo.

Uso:
    python scripts/dump_tools_prompt.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.application.telegram.tool_registry import (  # noqa: E402
    ALL_TOOLS,
    CANONICAL_QUESTIONS,
    build_tools_prompt,
)

OUT = ROOT / "docs" / "telegram-tools-prompt.md"

_SOURCE = "backend/app/application/telegram/tool_registry.py"

# Solapamientos detectados leyendo las descripciones (revisión manual, no
# calculada). Cada entrada: (tools, frase que las confunde, qué falta).
OVERLAPS: list[tuple[str, str, str]] = [
    (
        "`calendar_assignments` vs `list_doctors` vs `doctor_service_history`",
        "«qué médicos hicieron servicio el 3 de agosto»",
        "Ninguna pregunta canónica cubre «médicos que trabajaron en una fecha»: "
        "`calendar_assignments` habla de *guardias* (no de médicos), "
        "`list_doctors` habla de *médicos* (sin fechas) y "
        "`doctor_service_history` exige un médico concreto. Con fecha + médicos "
        "en la misma frase el modelo cae a `list_doctors`.",
    ),
    (
        "`list_doctors` vs `doctors_available_on` vs `availability_report_status`",
        "«quién está disponible»",
        "`list_doctors` filtra por `service_active`/`pool_active` (estado del "
        "sistema), `doctors_available_on` es disponibilidad *reportada para un "
        "día* y `availability_report_status` es *quién reportó el mes*. Las tres "
        "usan la palabra «disponible» con sentidos distintos.",
    ),
    (
        "`calendar_assignments` vs `calendar_status`",
        "«el calendario de agosto»",
        "`calendar_status` (mes/año) y `calendar_assignments` (rango de fechas) "
        "se solapan en el caso «mes completo»; nada dice cuál gana cuando no se "
        "pide estado ni huecos.",
    ),
    (
        "`doctors_available_on` vs `slot_recommendation` vs `slot_explanation`",
        "«quién puede cubrir el 3 de agosto en Emergencia»",
        "`doctors_available_on` es listado crudo sin evaluar reglas; "
        "`slot_recommendation` sí evalúa. La diferencia «reportó» vs «puede "
        "cubrir» no está explícita en la descripción.",
    ),
    (
        "`workload_ranking` vs `doctor_service_history` vs `mission_candidates`",
        "«cómo va la carga»",
        "`workload_ranking` es ranking de *servicio* mensual y `mission_candidates` "
        "usa el ranking guardado de *misiones*; `doctor_service_history` es el "
        "mismo dato pero de un médico. Tres «rankings» con fuentes distintas.",
    ),
    (
        "`confirmation_status` vs `notification_status` vs `action_alerts`",
        "«qué está pendiente»",
        "Las tres devuelven cosas «pendientes»: confirmaciones, envíos y alertas "
        "de acción. Sin la palabra clave de cada dominio el modelo puede elegir "
        "cualquiera.",
    ),
    (
        "`generate_report` vs `calendar_status` / `list_doctors`",
        "«mándame el reporte de agosto»",
        "`generate_report` produce un *documento* (PDF) y las otras devuelven "
        "datos en el chat. La palabra «reporte» aparece en varios sitios.",
    ),
]


def _tool_section(index: int, tool: dict) -> list[str]:
    name = tool["name"]
    description = tool["description"]
    canonical = CANONICAL_QUESTIONS.get(name, "")
    prefix = f"Pregunta típica: «{canonical}»."
    extra = description[len(prefix):].strip() if description.startswith(prefix) else description

    lines = [f"### {index}. `{name}`", "", f"**Pregunta típica:** «{canonical}»", ""]
    if extra:
        lines += [f"**Aclaración que el modelo lee:** {extra}", ""]

    properties = tool["parameters"].get("properties", {})
    required = set(tool["parameters"].get("required", []))
    if not properties:
        lines += ["**Parámetros:** ninguno.", ""]
        return lines

    lines += [
        "**Parámetros:**",
        "",
        "| parámetro | tipo | obligatorio | enum | qué dice la descripción |",
        "|---|---|---|---|---|",
    ]
    for pname, schema in properties.items():
        ptype = schema.get("type", "any")
        enum = "/".join(str(value) for value in schema.get("enum", [])) or "—"
        obligatorio = "sí" if pname in required else "no"
        pdesc = schema.get("description", "—").replace("|", "\\|")
        lines.append(f"| `{pname}` | {ptype} | {obligatorio} | {enum} | {pdesc} |")
    lines.append("")
    return lines


def build_markdown() -> str:
    lines: list[str] = [
        "# Tools del bot — lo que el modelo lee",
        "",
        f"> **Generado automáticamente** desde `{_SOURCE}` — no editar a mano.",
        "> Regenerar con: `python scripts/dump_tools_prompt.py`",
        "",
        "El modelo **no ve el código**: para elegir una tool solo lee el bloque de",
        "abajo (nombre + pregunta típica + aclaración + parámetros) y las reglas del",
        "system prompt. Mejorar una descripción es cambiar ese texto en el registro",
        "y regenerar este documento.",
        "",
        "---",
        "",
        "## 1. Bloque literal que entra al prompt",
        "",
        "Salida exacta de `build_tools_prompt()`:",
        "",
        "```text",
        build_tools_prompt(),
        "```",
        "",
        "---",
        "",
        f"## 2. Las {len(ALL_TOOLS)} tools, una por una",
        "",
        "| # | tool | pregunta típica |",
        "|---|---|---|",
    ]

    for index, tool in enumerate(ALL_TOOLS, start=1):
        canonical = CANONICAL_QUESTIONS.get(tool["name"], "")
        lines.append(f"| {index} | `{tool['name']}` | {canonical} |")

    lines += ["", "---", ""]
    for index, tool in enumerate(ALL_TOOLS, start=1):
        lines += _tool_section(index, tool)

    lines += [
        "---",
        "",
        "## 3. Dónde se pisan las descripciones",
        "",
        "Revisión manual de los choques que explican elecciones equivocadas de tool:",
        "",
    ]
    for tools, phrase, why in OVERLAPS:
        lines += [f"- **{tools}** — {phrase}", f"  - {why}"]
    lines.append("")

    lines += [
        "---",
        "",
        "## 4. Dónde se ajusta cada cosa",
        "",
        f"- Descripciones y parámetros de las tools: `{_SOURCE}`",
        "- Reglas de elección y contrato de comportamiento: "
        "`backend/app/application/telegram/intent_classifier.py` (`NLU_SYSTEM_PROMPT`)",
        "- Contexto de BD que acompaña al prompt (catálogos, reglas activas): "
        "`backend/app/application/telegram/system_context.py`",
        "- Plantillas SQL que ejecuta cada tool (no las ve el modelo): "
        "`backend/app/application/telegram/registry.py`",
        "",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    OUT.write_text(build_markdown(), encoding="utf-8")
    print(f"escrito: {OUT.relative_to(ROOT)} ({len(ALL_TOOLS)} tools)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
