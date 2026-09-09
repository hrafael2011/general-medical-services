"""Runner de una sola pasada para los jobs del scheduler.

El servicio API ya no necesita el APScheduler in-process en producción
(cuando RUN_IN_PROCESS_SCHEDULER=false): Railway ejecuta este módulo cada
30 minutos vía Cron Schedule en el servicio "worker", con el mismo
Dockerfile del proyecto.

Uso:
    python -m backend.app.application.scheduler.run_once

Cada job abre y cierra su propia sesión de BD (ver jobs.py), así que este
runner solo los invoca en orden y reporta el resultado.
"""

import logging
import sys

from backend.app.application.scheduler import jobs

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("scheduler.run_once")

# Orden importa poco (cada job es idempotente por estado), pero se mantiene
# el mismo orden en que corría APScheduler in-process.
_TASKS: list[tuple[str, object]] = [
    ("process_notification_queue", jobs.process_notification_queue),
    ("send_pre_service_reminders", jobs.send_pre_service_reminders),
    ("check_unconfirmed_escalamiento", jobs.check_unconfirmed_escalamiento),
    ("process_overdue_confirmations", jobs.process_overdue_confirmations),
]


def main() -> int:
    failed = False
    for name, fn in _TASKS:
        try:
            result = fn()  # type: ignore[operator]
        except Exception:
            failed = True
            logger.exception("Job %s terminó con error", name)
            continue
        logger.info("Job %s -> %s", name, result)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
