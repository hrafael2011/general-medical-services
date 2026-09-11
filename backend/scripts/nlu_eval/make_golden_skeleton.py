#!/usr/bin/env python
"""Genera golden_set.json a partir del corpus de 243 casos.

Cada turno queda con "expected": null y matcher "any". El humano (o Claude)
anota la respuesta esperada: un número, un nombre, un patrón regex, o deja
"any" cuando cualquier respuesta no degradada es válida (p. ej. una
clarificación legítima).

Regla de oro al anotar: **una expectativa sólo si es defendible contra la BD
local**. Si no se puede verificar, se deja "any" y se anota el motivo en
"note". No anotar de memoria.

Uso:
    ./.venv/bin/python -m backend.scripts.nlu_eval.make_golden_skeleton
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from backend.scripts.nlu_eval.regression_243 import parse_corpus  # noqa: E402

OUT = Path(__file__).resolve().parent / "golden_set.json"
CORPUS = ROOT / "docs" / "telegram_220_casos_prueba.md"


def main() -> int:
    corpus = parse_corpus(CORPUS)
    golden = {
        "generated_at": datetime.now(UTC).isoformat(),
        "source": str(CORPUS.relative_to(ROOT)),
        "cases": [
            {
                "id": case["id"],
                "category": case["category"],
                "turns": [
                    {"text": segment, "expected": None, "matcher": "any", "note": None}
                    for segment in case["segments"]
                ],
            }
            for case in corpus
        ],
    }
    OUT.write_text(json.dumps(golden, ensure_ascii=False, indent=2), encoding="utf-8")
    turns = sum(len(c["turns"]) for c in golden["cases"])
    print(f"Escrito: {OUT} ({len(golden['cases'])} casos, {turns} turnos por anotar)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
