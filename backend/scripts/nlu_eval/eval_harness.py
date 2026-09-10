#!/usr/bin/env python
"""Harness de evaluación del enrutado NLU del bot de Telegram.

Mide contra la API REAL de DeepSeek cuántas veces el modelo elige la tool
correcta en los 35 casos de `eval_set.json` (5 por cada una de las 7 colisiones
conocidas), y si los parámetros que extrae coinciden con el discriminador.

Uso:
    python backend/scripts/nlu_eval/eval_harness.py
    python backend/scripts/nlu_eval/eval_harness.py --verbose
    python backend/scripts/nlu_eval/eval_harness.py --only 4
    python backend/scripts/nlu_eval/eval_harness.py --min-tool-accuracy 0.95

Salida: accuracy de tool, accuracy de params, matriz de confusión de las
confusiones reales y el detalle de cada fallo.

Nota sobre la baseline: este script mide el código VIVO (importa `NLUEngine` y
`tool_registry`). Para comparar antes/después, correr con los cambios aplicados
y luego con `git stash` de los mismos archivos.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from backend.app.application.telegram.intent_classifier import NLUEngine  # noqa: E402
from backend.app.application.telegram.llm import DeepSeekProvider  # noqa: E402

EVAL_SET = Path(__file__).resolve().parent / "eval_set.json"

# Mensajes que `DeepSeekProvider` devuelve cuando la API falla. Si aparecen,
# el run NO es válido: sin esta guarda, cada fallo de red se contaría como
# "el modelo eligió mal" y reportaríamos un 0% falso.
_API_ERROR_MARKERS = (
    "Error de configuración del servicio de IA.",
    "El servicio de IA no está disponible en este momento.",
    "Lo siento, no pude conectarme con el servicio de IA.",
    "El servicio de IA está temporalmente sobrecargado.",
    "El servicio de IA respondió con un error.",
)


def _resolve_sentinel(value: str, today: date) -> str:
    """Resuelve los centinelas de fecha del eval set."""
    if value == "@today":
        return today.isoformat()
    if value == "@tomorrow":
        return (today + timedelta(days=1)).isoformat()
    if value == "@month_start":
        return today.replace(day=1).isoformat()
    if value == "@month_end":
        next_month = (today.replace(day=28) + timedelta(days=4)).replace(day=1)
        return (next_month - timedelta(days=1)).isoformat()
    return value


def _resolve_params(params: dict, today: date) -> dict:
    """Resuelve centinelas comparando el VALOR, no la clave.

    `{"month": "@current_month"}` — el centinela es el valor; comparar contra
    la clave dejaba el literal sin resolver y contaba como fallo del modelo un
    parámetro que en realidad había acertado.
    """
    resolved: dict = {}
    for key, value in params.items():
        if value == "@current_month":
            resolved[key] = today.month
        elif value == "@current_year":
            resolved[key] = today.year
        elif isinstance(value, str):
            resolved[key] = _resolve_sentinel(value, today)
        else:
            resolved[key] = value
    return resolved


def preflight(engine: NLUEngine) -> str | None:
    """Comprueba que la API responde antes de medir.

    Devuelve None si todo está bien, o el motivo del fallo. Sin esto, una key
    inválida produce 35 fallos de parseo y un "0% de accuracy" que parece un
    resultado del modelo cuando en realidad es un problema de credenciales.
    """
    probe = engine._llm.chat_complete(
        [{"role": "user", "content": "Responde solo: OK"}], temperature=0.0
    )
    for marker in _API_ERROR_MARKERS:
        if marker in probe:
            return probe.strip()
    return None


def _param_mismatches(expected: dict, actual: dict) -> list[str]:
    """Params declarados que el modelo no produjo igual."""
    problems: list[str] = []
    for key, want in expected.items():
        got = actual.get(key)
        if got is None:
            problems.append(f"falta {key}={want!r}")
        elif str(got).lower() != str(want).lower():
            problems.append(f"{key}: esperado {want!r}, vino {got!r}")
    return problems


def run(cases: list[dict], engine: NLUEngine, *, verbose: bool) -> int:
    today = date.today()
    rows: list[dict] = []

    for case in cases:
        result = engine.classify(case["user_input"])
        expected_tool = case["expected_tool"]
        expected_params = _resolve_params(case["expected_params"], today)

        tool_ok = result.tool == expected_tool
        problems = _param_mismatches(expected_params, result.params) if tool_ok else []
        rows.append(
            {
                "case": case,
                "got_tool": result.tool,
                "tool_ok": tool_ok,
                "problems": problems,
            }
        )

        if verbose:
            mark = "OK  " if tool_ok and not problems else "FALLA"
            print(f"[{mark}] {case['id']} {case['user_input'][:58]}")
            if not tool_ok:
                print(f"         esperado: {expected_tool} | vino: {result.tool}")

    total = len(rows)
    tool_hits = sum(1 for r in rows if r["tool_ok"])
    param_clean = sum(1 for r in rows if r["tool_ok"] and not r["problems"])

    print()
    print("=" * 72)
    print(f"TOOL ACCURACY:  {tool_hits}/{total}  ({tool_hits / total:.1%})")
    print(f"PARAM CLEAN:    {param_clean}/{total}  ({param_clean / total:.1%})")
    print("=" * 72)

    failures = [r for r in rows if not r["tool_ok"] or r["problems"]]
    if failures:
        print(f"\nFALLOS ({len(failures)}):")
        for r in failures:
            case = r["case"]
            print(f"\n  {case['id']} (colisión {case['collision']}) — «{case['user_input']}»")
            if not r["tool_ok"]:
                print(f"    tool: esperado {case['expected_tool']} | vino {r['got_tool']}")
                alt = ", ".join(case["wrong_alternatives"])
                print(f"    confundida con: {alt}")
            for p in r["problems"]:
                print(f"    param: {p}")
            print(f"    por qué importa: {case['reasoning']}")

    # Matriz de confusión: solo las confusiones reales (esperado != obtenido).
    confusion = Counter(
        (r["case"]["expected_tool"], r["got_tool"]) for r in rows if not r["tool_ok"]
    )
    if confusion:
        print("\nMATRIZ DE CONFUSIÓN (esperado → obtenido):")
        for (want, got), n in confusion.most_common():
            print(f"  {want:28} → {got:28} x{n}")

    # Cobertura por colisión: la señal de si el bloque de desambiguación sirvió.
    print("\nPOR COLISIÓN:")
    for collision in sorted({r["case"]["collision"] for r in rows}):
        group = [r for r in rows if r["case"]["collision"] == collision]
        hits = sum(1 for r in group if r["tool_ok"])
        bar = "█" * hits + "·" * (len(group) - hits)
        print(f"  colisión {collision}: {hits}/{len(group)}  {bar}")

    return tool_hits, total


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verbose", "-v", action="store_true", help="un renglón por caso")
    parser.add_argument("--only", type=int, help="evaluar solo una colisión (1-7)")
    parser.add_argument(
        "--min-tool-accuracy",
        type=float,
        default=0.95,
        help="umbral para salir con código 0 (default 0.95)",
    )
    args = parser.parse_args()

    payload = json.loads(EVAL_SET.read_text(encoding="utf-8"))
    cases = payload["cases"]
    if args.only:
        cases = [c for c in cases if c["collision"] == args.only]
        if not cases:
            print(f"No hay casos para la colisión {args.only}", file=sys.stderr)
            return 2

    engine = NLUEngine(DeepSeekProvider())

    failure = preflight(engine)
    if failure:
        print("La API de DeepSeek no respondió correctamente:", file=sys.stderr)
        print(f"  {failure}", file=sys.stderr)
        print(
            "\nNo se midió nada: revisá DEEPSEEK_API_KEY antes de correr el eval.",
            file=sys.stderr,
        )
        return 3

    print(f"Evaluando {len(cases)} casos contra la API real de DeepSeek...")
    hits, total = run(cases, engine, verbose=args.verbose)

    accuracy = hits / total
    if accuracy < args.min_tool_accuracy:
        print(
            f"\nPor debajo del umbral: {accuracy:.1%} < {args.min_tool_accuracy:.0%}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
