#!/usr/bin/env python
"""Línea base / regresión sobre los 243 casos conversacionales reales.

Corre cada frase de `docs/telegram_220_casos_prueba.md` por el MISMO cableado
que usa producción (`get_orchestrator`), y guarda la respuesta de cada una.

El objetivo no es medir "cuántas están bien" — no hay respuesta esperada
anotada — sino tener una FOTO del comportamiento actual para poder comparar
antes/después de un cambio de enrutado. Lo que funcione antes y falle después
aparece con nombre y apellido.

Uso:
    DATABASE_URL=postgresql+psycopg://postgres:postgres@127.0.0.1:5433/medical_shifts \\
        ./.venv/bin/python -m backend.scripts.nlu_eval.regression_243 \\
        --out baseline.json

    # comparar dos corridas
    ... --compare baseline.json despues.json

Requiere DEEPSEEK_API_KEY válida Y TELEGRAM_BOT_TOKEN (usa el LLM real). Sin
cualquiera de las dos, aborta.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

CORPUS = ROOT / "docs" / "telegram_220_casos_prueba.md"

# Mensajes con los que `DeepSeekProvider` degrada cuando la API falla. Si
# aparecen, la corrida no vale: contaríamos errores de credencial como
# comportamiento del bot.
_API_ERROR_MARKERS = (
    "Error de configuración del servicio de IA.",
    "El servicio de IA no está disponible en este momento.",
    "Lo siento, no pude conectarme con el servicio de IA.",
    "El servicio de IA está temporalmente sobrecargado.",
    "El servicio de IA respondió con un error.",
)

# Cada caso usa su propio telegram_user_id para que la memoria conversacional
# de un caso no se filtre al siguiente.
_EVAL_TG_PREFIX = "eval243"


def parse_corpus(path: Path) -> list[dict]:
    """Devuelve [{id, category, segments}] desde el markdown del corpus.

    Las líneas son `N. frase` y las multi-turno usan `→` como separador.
    """
    cases: list[dict] = []
    category = "(sin categoría)"
    text = path.read_text(encoding="utf-8")

    for line in text.splitlines():
        if line.startswith("## "):
            category = line[3:].strip()
            continue
        match = re.match(r"^(\d+)\.\s+(.+)$", line.strip())
        if not match:
            continue
        number = int(match.group(1))
        segments = [s.strip() for s in match.group(2).split("→") if s.strip()]
        if segments:
            cases.append({"id": number, "category": category, "segments": segments})
    return cases


class _RouteCapture(logging.Handler):
    """Captura el `match_type` que el orquestador registra por interacción."""

    def __init__(self) -> None:
        super().__init__()
        self.last: dict | None = None

    def emit(self, record: logging.LogRecord) -> None:
        extra = getattr(record, "__dict__", {})
        if extra.get("telegram_event") == "route_completed":
            self.last = {
                "route": extra.get("route"),
                "match_type": extra.get("match_type"),
                "used_sql_agent": extra.get("used_sql_agent"),
                "used_sql": extra.get("used_sql"),
            }


def _ensure_link(session: Session, telegram_user_id: str, user_id: str) -> None:
    """Crea el vínculo Telegram→usuario si falta (idempotente)."""
    from backend.app.infrastructure.db.models.telegram import TelegramUserLinkModel

    existing = session.scalars(
        select(TelegramUserLinkModel).where(
            TelegramUserLinkModel.telegram_user_id == telegram_user_id
        )
    ).first()
    if existing is not None:
        return

    from uuid import uuid4

    session.add(
        TelegramUserLinkModel(
            id=str(uuid4()),
            telegram_user_id=telegram_user_id,
            telegram_username=telegram_user_id,
            user_id=user_id,
            active=True,
            linked_by=None,
            linked_at=datetime.now(UTC),
            last_used_at=None,
        )
    )
    session.commit()


def _admin_user_id(session: Session) -> str:
    from backend.app.infrastructure.db.models.user import UserModel

    user = session.scalars(
        select(UserModel).where(UserModel.role == "admin", UserModel.active.is_(True))
    ).first()
    if user is None:
        raise SystemExit("No hay un usuario admin activo en la base.")
    return user.id


def preflight(session: Session) -> None:
    """Aborta si el NLU no va a ser el real, o si la API no responde.

    El orden importa: primero la comprobación que no gasta nada.

    1. `use_real = settings.telegram_bot_token and settings.deepseek_api_key`
       (api/routes/telegram.py). Sin el token, el NLU queda en `None` y el
       agente cae EN SILENCIO al matcheo por palabras clave: la corrida
       terminaría, escribiría su JSON y mediría otra cosa sin un solo error.
       Se comprueba sobre el orquestador ya cableado —el mismo que usan los
       casos— en vez de repetir la condición acá, que es como se desincroniza.
    2. La sonda a DeepSeek, que sí cuesta una llamada.
    """
    from backend.app.api.routes.telegram import get_orchestrator

    if get_orchestrator(session)._nlu_engine is None:
        raise SystemExit(
            "El NLU real NO está activo: falta TELEGRAM_BOT_TOKEN (o "
            "DEEPSEEK_API_KEY).\n"
            "Sin él el agente responde por matcheo de palabras clave y la "
            "corrida mediría otra cosa, sin error visible.\n"
            "Exportá TELEGRAM_BOT_TOKEN antes de correr la línea base."
        )

    from backend.app.application.telegram.llm import DeepSeekProvider

    probe = DeepSeekProvider().chat_complete(
        [{"role": "user", "content": "Responde solo: OK"}], temperature=0.0
    )
    for marker in _API_ERROR_MARKERS:
        if marker in probe:
            raise SystemExit(
                f"La API de DeepSeek no respondió: {probe.strip()}\n"
                "Revisá DEEPSEEK_API_KEY antes de correr la línea base."
            )


def run(cases: list[dict], session_factory, *, verbose: bool) -> dict:
    from backend.app.api.routes.telegram import get_orchestrator

    capture = _RouteCapture()
    # El nivel del logger decide si el `logger.info(...)` del orquestador se
    # emite; sin subirlo a INFO el handler nunca ve el evento route_completed.
    route_logger = logging.getLogger("backend.app.application.telegram")
    route_logger.setLevel(logging.INFO)
    route_logger.addHandler(capture)

    results: list[dict] = []
    for case in cases:
        tg_id = f"{_EVAL_TG_PREFIX}-{case['id']}"
        session = session_factory()
        try:
            user_id = _admin_user_id(session)
            _ensure_link(session, tg_id, user_id)
            orchestrator = get_orchestrator(session)

            # `use_real` (y con él el NLU) depende de que TELEGRAM_BOT_TOKEN
            # esté puesto, pero eso también instancia el cliente REAL de
            # Telegram. Se cambia por el fake para que la corrida no intente
            # enviar 253 mensajes: se mide el NLU, no el transporte.
            from backend.app.application.telegram.bot_client import FakeBotClient

            orchestrator._bot_client = FakeBotClient()

            turns: list[dict] = []
            for segment in case["segments"]:
                capture.last = None
                try:
                    response = orchestrator.handle_message(
                        telegram_user_id=tg_id,
                        telegram_username=tg_id,
                        chat_id=case["id"],
                        text=segment,
                    )
                except Exception as exc:  # noqa: BLE001 — un caso no debe tumbar la corrida
                    # Un mensaje que revienta el pipeline aborta la transacción
                    # de Postgres y, sin rollback, todo lo que siga falla en
                    # cascada hasta matar la corrida entera.
                    session.rollback()
                    response = f"[ERROR] {type(exc).__name__}: {exc}"
                turns.append(
                    {
                        "text": segment,
                        "response": response,
                        "route": (capture.last or {}).get("route"),
                        "match_type": (capture.last or {}).get("match_type"),
                        "used_sql_agent": (capture.last or {}).get("used_sql_agent"),
                    }
                )
        finally:
            session.close()

        results.append({"id": case["id"], "category": case["category"], "turns": turns})
        if verbose:
            first = turns[0]
            print(
                f"[{case['id']:>3}] {first.get('match_type') or '-':<18} "
                f"{case['segments'][0][:56]}"
            )

    logging.getLogger("backend.app.application.telegram").removeHandler(capture)
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "cases": results,
    }


def compare(before: dict, after: dict) -> int:
    """Imprime las diferencias entre dos corridas. Devuelve el nº de cambios."""
    by_id = {c["id"]: c for c in before["cases"]}
    changed: list[tuple[int, str]] = []

    for case in after["cases"]:
        old = by_id.get(case["id"])
        if old is None:
            continue
        old_turns = [t.get("response") for t in old["turns"]]
        new_turns = [t.get("response") for t in case["turns"]]
        if old_turns != new_turns:
            first = case["turns"][0].get("text", "") if case["turns"] else ""
            changed.append((case["id"], first))

    if not changed:
        print("Sin diferencias: las 243 respuestas son idénticas.")
        return 0

    print(f"DIFERENCIAS: {len(changed)} casos cambiaron de respuesta\n")
    for case_id, phrase in changed:
        old = by_id[case_id]
        new = next(c for c in after["cases"] if c["id"] == case_id)
        print(f"  #{case_id} «{phrase[:60]}»")
        # Solo para mostrar: la detección de diferencias ya la hizo la
        # comparación de listas completa de arriba.
        for i, (o, n) in enumerate(zip(old["turns"], new["turns"], strict=False)):
            if o.get("response") != n.get("response"):
                print(f"    turno {i + 1}")
                print(f"      antes:  {(o.get('response') or '')[:110]}")
                print(f"      ahora:  {(n.get('response') or '')[:110]}")
                print(
                    f"      ruta:   {o.get('match_type')} -> {n.get('match_type')}"
                )
    return len(changed)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="baseline_243.json", help="archivo de resultados")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument(
        "--compare", nargs=2, metavar=("ANTES", "DESPUES"), help="comparar dos corridas"
    )
    parser.add_argument("--only", type=int, help="correr solo un caso (debug)")
    args = parser.parse_args()

    if args.compare:
        before = json.loads(Path(args.compare[0]).read_text(encoding="utf-8"))
        after = json.loads(Path(args.compare[1]).read_text(encoding="utf-8"))
        return 0 if compare(before, after) == 0 else 1

    if not os.environ.get("DEEPSEEK_API_KEY"):
        print("Falta DEEPSEEK_API_KEY.", file=sys.stderr)
        return 2

    url = os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@127.0.0.1:5433/medical_shifts",
    )
    engine = create_engine(url)

    # El motor se crea antes de la guarda porque comprobarla exige cablear el
    # orquestador, y eso necesita sesión.
    with Session(engine) as probe_session:
        preflight(probe_session)

    cases = parse_corpus(CORPUS)
    if args.only:
        cases = [c for c in cases if c["id"] == args.only]
    print(f"Corriendo {len(cases)} casos contra el cableado de producción...")

    payload = run(cases, lambda: Session(engine), verbose=args.verbose)
    Path(args.out).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nEscrito: {args.out} ({len(payload['cases'])} casos)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
