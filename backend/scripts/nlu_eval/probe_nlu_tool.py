#!/usr/bin/env python
"""Sonda: qué tool elige el NLU para un puñado de frases, sin correr el bot.

Sirve para decidir dónde poner un gate de alcance: si una frase fuera de
dominio se clasifica como un tool de la lista blanca, un gate por nombre de
tool NO la atrapa y hay que bloquear en otro lado.

Uso:
    DATABASE_URL=... DEEPSEEK_API_KEY=... TELEGRAM_BOT_TOKEN=dummy \\
        ./.venv/bin/python -m backend.scripts.nlu_eval.probe_nlu_tool "Que hora es?"
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

DEFAULT_TEXTS = [
    # Fuera de dominio — hoy responden con los 41 médicos
    "Que hora es?",
    "Quien es el presidente?",
    "Cuentame un chiste",
    # Ambigüedad que también cae en el cluster
    "Como esta el sistema?",
    "Que me recomiendas?",
    "Licencias Medicass",
    # Control: ésta SÍ debe funcionar
    "Dame los medicos.",
]


def main() -> int:
    args = sys.argv[1:]
    if args and args[0] == "--file":
        texts = [
            line.strip()
            for line in Path(args[1]).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    else:
        texts = args or DEFAULT_TEXTS
    engine = create_engine(
        os.environ.get(
            "DATABASE_URL",
            "postgresql+psycopg://postgres:postgres@127.0.0.1:5433/medical_shifts",
        )
    )
    from backend.app.api.routes.telegram import get_orchestrator

    with Session(engine) as session:
        orchestrator = get_orchestrator(session)
        nlu = orchestrator._nlu_engine
        if nlu is None:
            raise SystemExit("NLU real NO activo: falta TELEGRAM_BOT_TOKEN")
        print(f"{'tool':<24} {'params':<38} frase")
        print("-" * 100)
        for text in texts:
            result = nlu.classify(text)
            params = str(result.params)
            if len(params) > 36:
                params = params[:33] + "..."
            print(
                f"{str(result.tool):<24} {params:<38} {text}"
                f"{'   [clarify]' if result.needs_clarification else ''}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
