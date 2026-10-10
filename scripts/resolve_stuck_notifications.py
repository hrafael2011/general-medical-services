#!/usr/bin/env python
"""Cierra los avisos y confirmaciones que quedaron atascados antes del arreglo.

Contexto: los jobs del scheduler reventaban con `NoReferencedTableError` y reportaban
ceros, así que la cola nunca se drenó y quedaron filas `pending` de septiembre. Con el
canal ya reparado, esas filas viejas **no se reenvían**: avisar hoy de una licencia o un
turno de hace un mes sería peor que no avisar. Se cierran con un estado que lo explica.

Dos cosas que hace:

1. `notification_events` en `pending` anteriores al corte → `skipped`, con
   `error_code = "stale_never_delivered"`.
2. `confirmation_requests` en `pending`/`received` anteriores al corte → `expired`.
   **Importa hacerlo**: el job de escalación busca justo esos dos estados, así que si se
   dejan, el primer día que el canal funcione mandaría un mensaje consolidado con los
   médicos de septiembre.

Es idempotente y acepta `--dry-run`.

Uso:
    python scripts/resolve_stuck_notifications.py --dry-run
    python scripts/resolve_stuck_notifications.py --days 7
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import select  # noqa: E402

from backend.app.infrastructure.db.models.confirmations import (  # noqa: E402
    ConfirmationRequestModel,
)
from backend.app.infrastructure.db.models.notifications import (  # noqa: E402
    NotificationEventModel,
)
from backend.app.infrastructure.db.session import SessionLocal  # noqa: E402

DEFAULT_DAYS = 7


def resolve(*, days: int, dry_run: bool) -> dict[str, int]:
    cutoff = datetime.now(UTC) - timedelta(days=days)
    session = SessionLocal()
    try:
        stale_events = list(
            session.scalars(
                select(NotificationEventModel).where(
                    NotificationEventModel.status == "pending",
                    NotificationEventModel.created_at < cutoff,
                )
            )
        )
        stale_confirmations = list(
            session.scalars(
                select(ConfirmationRequestModel).where(
                    ConfirmationRequestModel.status.in_(["pending", "received"]),
                    ConfirmationRequestModel.created_at < cutoff,
                )
            )
        )

        now = datetime.now(UTC)
        for event in stale_events:
            event.status = "skipped"
            event.error_code = "stale_never_delivered"
            event.sent_at = now
            event.updated_at = now

        for request in stale_confirmations:
            request.status = "expired"
            request.updated_at = now

        if dry_run:
            session.rollback()
            print(
                f"[DRY RUN] {len(stale_events)} aviso(s) y "
                f"{len(stale_confirmations)} confirmación(es) se cerrarían. Nada se guardó."
            )
        else:
            session.commit()
            print(
                f"Cerrados: {len(stale_events)} aviso(s) y "
                f"{len(stale_confirmations)} confirmación(es)."
            )
            if stale_events:
                print("  Los avisos NO se reenviaron a propósito: son de hace más de "
                      f"{days} días y enviarlos hoy sería peor que no enviarlos.")
        return {"events": len(stale_events), "confirmations": len(stale_confirmations)}
    finally:
        session.close()


if __name__ == "__main__":
    days = DEFAULT_DAYS
    if "--days" in sys.argv:
        days = int(sys.argv[sys.argv.index("--days") + 1])
    resolve(days=days, dry_run="--dry-run" in sys.argv)
