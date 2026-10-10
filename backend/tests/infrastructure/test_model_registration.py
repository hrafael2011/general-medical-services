"""The session module must register every model on its own.

The scheduler is a bare entrypoint: it imports no routes, so a model nobody imported is
absent from the SQLAlchemy metadata and any foreign key pointing at it raises
`NoReferencedTableError`. That is what broke the notification queue for a month while
the runner reported zeros, as if there had been nothing to send.

The check runs in a **fresh process** on purpose. In this test process the conftest
already imports every model, so asserting on `Base.metadata` here would pass even with
the bug in place — it would be measuring the conftest, not the worker.
"""

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

# Tables the scheduler jobs reach through foreign keys.
REQUIRED_TABLES = (
    "mission_assignments",
    "calendar_assignments",
    "confirmation_requests",
    "notification_events",
    "doctor_restrictions",
    "doctor_availability",
    "users",
    "audit_events",
    "action_alerts",
    "telegram_link_tokens",
    "system_settings",
    "deactivation_reasons",
)


def _tables_known_by_a_fresh_process() -> set[str]:
    """Ask a bare interpreter which tables it knows after importing only the session."""
    code = (
        "import json;"
        "from backend.app.infrastructure.db.base import Base;"
        "import backend.app.infrastructure.db.session;"  # the sole application import
        "print(json.dumps(sorted(Base.metadata.tables)))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    return set(json.loads(result.stdout))


def test_session_alone_registers_every_table() -> None:
    known = _tables_known_by_a_fresh_process()

    missing = [table for table in REQUIRED_TABLES if table not in known]
    assert not missing, (
        "un proceso que solo importa la sesión no conoce estas tablas "
        f"(los jobs del scheduler fallarían): {missing}"
    )


def test_the_registry_lists_every_model_class() -> None:
    """`models/__init__` is the registry; a new model has to be added to it."""
    import backend.app.infrastructure.db.models as models
    from backend.app.infrastructure.db.base import Base

    exported = {getattr(models, name) for name in models.__all__}
    declared = {mapper.class_ for mapper in Base.registry.mappers}

    assert declared <= exported, (
        "hay modelos declarados fuera de models.__all__: "
        f"{sorted(c.__name__ for c in declared - exported)}"
    )
