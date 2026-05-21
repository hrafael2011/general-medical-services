from alembic.config import Config
from alembic.script import ScriptDirectory


def test_alembic_has_single_head():
    script = ScriptDirectory.from_config(Config("alembic.ini"))

    assert script.get_heads() == ["20260521_0033"]


def test_set_password_tokens_table_has_migration():
    script = ScriptDirectory.from_config(Config("alembic.ini"))

    migration_sources = "\n".join(
        revision.module.__doc__ or "" for revision in script.walk_revisions()
    )
    migration_sources += "\n".join(
        revision.module.upgrade.__code__.co_consts.__repr__()
        for revision in script.walk_revisions()
    )

    assert "set_password_tokens" in migration_sources
