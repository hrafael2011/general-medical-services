#!/usr/bin/env python
"""Juez del golden set: produce el porcentaje de acierto REAL.

Dos cifras, a propósito:

  * **Sobre lo anotado** — sólo los turnos con expectativa verificable contra la
    BD. Es la señal de verdad; una muestra chica pero sin relleno.
  * **Global** — sobre los 253 turnos, contando los `any` como válidos. Sirve de
    contexto, pero se infla solo: un `any` pasa con cualquier respuesta no
    degradada, así que NO debe citarse como "el acierto del bot".

Un turno con respuesta degradada de la API nunca cuenta como acierto.

Uso:
    DATABASE_URL=postgresql+psycopg://postgres:postgres@127.0.0.1:5433/medical_shifts \\
    DEEPSEEK_API_KEY=... TELEGRAM_BOT_TOKEN=dummy \\
        ./.venv/bin/python -m backend.scripts.nlu_eval.judge_243 \\
        --golden golden_set.json --out judged.json

    # Juzgar una corrida ya hecha, sin gastar llamadas nuevas:
    ./.venv/bin/python -m backend.scripts.nlu_eval.judge_243 \\
        --from-run fase7_243.json --out judged.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

HERE = Path(__file__).resolve().parent

_API_ERROR_MARKERS = (
    "Error de configuración del servicio de IA.",
    "El servicio de IA no está disponible en este momento.",
    "Lo siento, no pude conectarme con el servicio de IA.",
    "El servicio de IA está temporalmente sobrecargado.",
    "El servicio de IA respondió con un error.",
)


def is_degraded(response: str) -> bool:
    """True si la respuesta es un fallo de API, no del bot."""
    return any(marker in response for marker in _API_ERROR_MARKERS)


def match(expected: dict, response: str) -> bool:
    """Un turno degradado por la API nunca cuenta como acierto."""
    if is_degraded(response):
        return False
    matcher = expected.get("matcher") or "any"
    want = expected.get("expected")
    if matcher == "any" or want is None:
        return True
    if matcher == "number":
        found = re.search(r"(\d+)", response)
        if found is not None:
            return int(found.group(1)) == int(want)
        # «No se encontraron resultados» ES la respuesta correcta cuando se
        # espera 0: la ausencia de número es el cero, no una evasiva.
        if int(want) == 0:
            return any(
                phrase in response.lower()
                for phrase in ("no se encontr", "no hay", "ningún", "ningun")
            )
        return False
    if matcher == "contains":
        return str(want).lower() in response.lower()
    if matcher == "regex":
        return re.search(str(want), response, re.IGNORECASE) is not None
    return True


def _load_payload(args: argparse.Namespace) -> dict:
    if args.from_run:
        return json.loads(Path(args.from_run).read_text(encoding="utf-8"))

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from backend.scripts.nlu_eval.regression_243 import parse_corpus, run

    engine = create_engine(
        os.environ.get(
            "DATABASE_URL",
            "postgresql+psycopg://postgres:postgres@127.0.0.1:5433/medical_shifts",
        )
    )
    from backend.app.api.routes.telegram import get_orchestrator

    with Session(engine) as session:
        if get_orchestrator(session)._nlu_engine is None:
            raise SystemExit(
                "NLU real NO activo: exportar TELEGRAM_BOT_TOKEN y DEEPSEEK_API_KEY"
            )

    corpus = parse_corpus(ROOT / "docs" / "telegram_220_casos_prueba.md")
    if args.only:
        corpus = [c for c in corpus if c["id"] == args.only]
    return run(corpus, lambda: Session(engine), verbose=False)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--golden", default=str(HERE / "golden_set.json"))
    parser.add_argument("--out", default=str(HERE / "judged.json"))
    parser.add_argument("--from-run", help="juzgar una corrida ya guardada")
    parser.add_argument("--only", type=int)
    args = parser.parse_args()

    golden = json.loads(Path(args.golden).read_text(encoding="utf-8"))
    golden_by_id = {c["id"]: c for c in golden["cases"]}
    payload = _load_payload(args)

    annotated_total = annotated_pass = 0
    all_total = all_pass = 0
    failures = []

    for case in payload["cases"]:
        golden_case = golden_by_id.get(case["id"])
        if golden_case is None:
            continue
        for index, turn in enumerate(case["turns"]):
            response = turn.get("response") or ""
            all_total += 1
            expected = {"matcher": "any"}
            if index < len(golden_case["turns"]):
                expected = golden_case["turns"][index]
            ok = match(expected, response)
            if ok:
                all_pass += 1
            is_annotated = (expected.get("matcher") or "any") != "any"
            if is_annotated:
                annotated_total += 1
                if ok:
                    annotated_pass += 1
                else:
                    failures.append(
                        {
                            "case": case["id"],
                            "category": case["category"],
                            "text": turn["text"],
                            "response": response[:160],
                            "expected": expected.get("expected"),
                            "matcher": expected.get("matcher"),
                            "note": expected.get("note"),
                            "route": turn.get("match_type"),
                        }
                    )

    result = {
        "judged_at": datetime.now(UTC).isoformat(),
        "source_run": args.from_run or "corrida nueva",
        "score_annotated": f"{annotated_pass}/{annotated_total}",
        "percent_annotated": (
            round(annotated_pass / annotated_total * 100, 1) if annotated_total else None
        ),
        "score_global": f"{all_pass}/{all_total}",
        "percent_global": round(all_pass / all_total * 100, 1) if all_total else None,
        "failures": failures,
    }
    Path(args.out).write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"ACIERTO sobre lo anotado: {result['score_annotated']} "
          f"({result['percent_annotated']}%)  <-- la señal real")
    print(f"ACIERTO global (con 'any'): {result['score_global']} "
          f"({result['percent_global']}%)  <-- se infla solo, no citar como acierto")
    print(f"Fallos escritos en {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
