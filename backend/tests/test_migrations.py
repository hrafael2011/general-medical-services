from alembic.config import Config
from alembic.script import ScriptDirectory


def test_alembic_has_single_head():
    script = ScriptDirectory.from_config(Config("alembic.ini"))

    assert script.get_heads() == ["20260521_0031"]
