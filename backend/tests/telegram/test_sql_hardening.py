"""SQL Agent hardening tests — security validation for fallback queries."""

import pytest

from backend.app.application.telegram.sql_agent.security import (
    validate_sql,
    _EXCLUDE_TABLES,
    _FORBIDDEN_KEYWORDS,
)
from backend.app.application.telegram.sql_agent.validator import SQLValidator


validator = SQLValidator()


class TestSecurityValidateSQL:
    """Direct security.py validation tests."""

    @pytest.mark.parametrize(
        "sql",
        [
            "SELECT * FROM doctors",
            "SELECT name, rank FROM doctors LIMIT 10",
            "SELECT COUNT(*) FROM doctors WHERE sex = 'male'",
        ],
    )
    def test_valid_select_passes(self, sql):
        assert validate_sql(sql) is True, f"Expected valid: {sql}"

    @pytest.mark.parametrize(
        "sql",
        [
            "DELETE FROM doctors",
            "DROP TABLE doctors",
            "INSERT INTO doctors (name) VALUES ('test')",
            "UPDATE doctors SET name='test' WHERE id=1",
            "ALTER TABLE doctors ADD COLUMN test TEXT",
            "TRUNCATE doctors",
        ],
    )
    def test_destructive_sql_rejected(self, sql):
        assert validate_sql(sql) is False, f"Expected rejected: {sql}"

    @pytest.mark.parametrize(
        "sql",
        [
            "SELECT * FROM users",
            "SELECT * FROM telegram_user_links",
            "SELECT * FROM audit_logs",
        ],
    )
    def test_excluded_tables_rejected(self, sql):
        assert validate_sql(sql) is False

    def test_select_with_cte_dml_rejected(self):
        sql = "WITH deleted AS (DELETE FROM doctors) SELECT * FROM deleted"
        assert validate_sql(sql) is False

    def test_multiple_statements_rejected(self):
        sql = "SELECT * FROM doctors; SELECT * FROM calendars"
        assert validate_sql(sql) is False


class TestSQLValidatorHardening:
    """Programmatic SQLValidator tests."""

    @pytest.mark.parametrize(
        "sql",
        [
            "SELECT * FROM doctors LIMIT 100",
            "SELECT name FROM doctors LIMIT 5",
            "SELECT COUNT(*) FROM doctors WHERE rank_id = 'CABO'",
        ],
    )
    def test_valid_queries_pass(self, sql):
        result = validator.validate(sql)
        assert result.ok is True, f"Expected OK: {sql}"

    @pytest.mark.parametrize(
        "sql",
        [
            "DROP TABLE doctors",
            "INSERT INTO doctors (name) VALUES ('x')",
            "UPDATE doctors SET name='x'",
            "DELETE FROM doctors",
            "TRUNCATE doctors",
            "ALTER TABLE doctors DROP COLUMN name",
            "CREATE TABLE hack (id int)",
            "REPLACE INTO doctors (id) VALUES (1)",
        ],
    )
    def test_dml_rejected(self, sql):
        result = validator.validate(sql)
        assert result.ok is False, f"Expected rejected: {sql}"
        assert result.rule == "dml_detected"

    @pytest.mark.parametrize(
        "sql",
        [
            "SELECT * FROM doctors WHERE pg_sleep(10)=1",
            "SELECT pg_cancel_backend(42)",
            "SELECT lo_import('/etc/passwd')",
        ],
    )
    def test_forbidden_functions_rejected(self, sql):
        result = validator.validate(sql)
        assert result.ok is False

    def test_excluded_table_rejected(self):
        result = validator.validate("SELECT * FROM users")
        assert result.ok is False
        assert result.rule == "excluded_table"

    def test_missing_limit_rejected_for_large_select(self):
        result = validator.validate("SELECT * FROM doctors")
        assert result.ok is False
        assert result.rule == "missing_limit"

    def test_query_too_long_rejected(self):
        long_sql = "SELECT * FROM doctors WHERE 1=1 " + "AND 1=1 " * 300
        result = validator.validate(long_sql)
        assert result.ok is False
        assert result.rule == "max_length"

    def test_excluded_tables_list(self):
        """Verify the exclude list covers sensitive tables."""
        excluded = set(t.lower() for t in _EXCLUDE_TABLES)
        assert "users" in excluded
        assert "audit_logs" in excluded
        assert "telegram_interactions" in excluded
        assert "telegram_user_links" in excluded
        assert "telegram_link_tokens" in excluded
        assert "alembic_version" in excluded

    def test_forbidden_keywords_includes_all_dml(self):
        """Verify forbidden keywords cover all DML/DQL variants."""
        keywords = set(k.upper() for k in _FORBIDDEN_KEYWORDS)
        for kw in ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE",
                    "CREATE", "EXEC", "GRANT", "REVOKE"]:
            assert kw in keywords, f"Missing forbidden keyword: {kw}"
