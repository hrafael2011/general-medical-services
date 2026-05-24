from alembic.config import Config
from alembic.script import ScriptDirectory


def test_alembic_has_single_head():
    script = ScriptDirectory.from_config(Config("alembic.ini"))

    assert script.get_heads() == ["20260524_0038"]


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


def test_login_attempts_attempt_type_has_migration():
    script = ScriptDirectory.from_config(Config("alembic.ini"))

    migration_sources = "\n".join(
        revision.module.__doc__ or "" for revision in script.walk_revisions()
    )
    migration_sources += "\n".join(
        revision.module.upgrade.__code__.co_consts.__repr__()
        for revision in script.walk_revisions()
    )

    assert "attempt_type" in migration_sources


def test_doctor_name_parts_have_migration():
    script = ScriptDirectory.from_config(Config("alembic.ini"))

    migration_sources = "\n".join(
        revision.module.__doc__ or "" for revision in script.walk_revisions()
    )
    migration_sources += "\n".join(
        revision.module.upgrade.__code__.co_consts.__repr__()
        for revision in script.walk_revisions()
    )

    assert "first_name" in migration_sources
    assert "last_name" in migration_sources


def test_deactivation_reasons_deleted_at_has_migration():
    script = ScriptDirectory.from_config(Config("alembic.ini"))

    migration_sources = "\n".join(
        revision.module.__doc__ or "" for revision in script.walk_revisions()
    )
    migration_sources += "\n".join(
        revision.module.upgrade.__code__.co_consts.__repr__()
        for revision in script.walk_revisions()
    )

    assert "deactivation_reasons" in migration_sources
    assert "deleted_at" in migration_sources
