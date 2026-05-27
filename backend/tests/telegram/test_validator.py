"""Tests for SQLValidator — programmatic guardrails."""

from __future__ import annotations

import pytest

from backend.app.application.telegram.sql_agent.validator import SQLValidator


@pytest.fixture
def validator() -> SQLValidator:
    return SQLValidator()


class TestBasicValidation:
    def test_allows_simple_select(self, validator: SQLValidator) -> None:
        result = validator.validate("SELECT * FROM doctors LIMIT 10")
        assert result.ok is True

    def test_blocks_insert(self, validator: SQLValidator) -> None:
        result = validator.validate("INSERT INTO doctors (name) VALUES ('x')")
        assert result.ok is False
        assert result.rule == "not_select"

    def test_blocks_update(self, validator: SQLValidator) -> None:
        result = validator.validate("UPDATE doctors SET name='x'")
        assert result.ok is False
        assert result.rule == "not_select"

    def test_blocks_delete(self, validator: SQLValidator) -> None:
        result = validator.validate("DELETE FROM doctors")
        assert result.ok is False
        assert result.rule == "not_select"

    def test_blocks_drop(self, validator: SQLValidator) -> None:
        result = validator.validate("DROP TABLE doctors")
        assert result.ok is False
        assert result.rule == "not_select"


class TestForbiddenFunctions:
    def test_blocks_pg_sleep(self, validator: SQLValidator) -> None:
        result = validator.validate("SELECT pg_sleep(10) FROM doctors LIMIT 1")
        assert result.ok is False
        assert result.rule == "forbidden_function"

    def test_blocks_pg_cancel_backend(self, validator: SQLValidator) -> None:
        result = validator.validate("SELECT pg_cancel_backend(1) LIMIT 1")
        assert result.ok is False
        assert result.rule == "forbidden_function"


class TestDangerousPatterns:
    def test_blocks_multiple_statements(self, validator: SQLValidator) -> None:
        result = validator.validate("SELECT 1; SELECT 2")
        assert result.ok is False
        assert result.rule == "multiple_statements"

    def test_blocks_line_comments(self, validator: SQLValidator) -> None:
        result = validator.validate("SELECT 1 -- drop table")
        assert result.ok is False
        assert result.rule == "line_comment"

    def test_blocks_block_comments(self, validator: SQLValidator) -> None:
        result = validator.validate("SELECT /* drop */ 1")
        assert result.ok is False
        assert result.rule == "block_comment"

    def test_blocks_union(self, validator: SQLValidator) -> None:
        result = validator.validate("SELECT name FROM doctors UNION SELECT name FROM doctors")
        assert result.ok is False
        assert result.rule == "union_injection"

    def test_blocks_stacked_queries(self, validator: SQLValidator) -> None:
        result = validator.validate("SELECT 1; DROP TABLE doctors")
        assert result.ok is False
        assert result.rule == "multiple_statements"


class TestSchemaValidation:
    def test_blocks_unknown_table(self, validator: SQLValidator) -> None:
        result = validator.validate("SELECT * FROM nonexistent_table LIMIT 1")
        assert result.ok is False
        assert result.rule == "unknown_table"

    def test_allows_known_table(self, validator: SQLValidator) -> None:
        result = validator.validate("SELECT * FROM doctors LIMIT 1")
        assert result.ok is True

    def test_blocks_excluded_table(self, validator: SQLValidator) -> None:
        result = validator.validate("SELECT * FROM users LIMIT 1")
        assert result.ok is False
        assert result.rule == "excluded_table"


class TestLimitValidation:
    def test_blocks_select_without_limit(self, validator: SQLValidator) -> None:
        result = validator.validate("SELECT * FROM doctors")
        assert result.ok is False
        assert result.rule == "missing_limit"

    def test_allows_aggregate_without_limit(self, validator: SQLValidator) -> None:
        result = validator.validate("SELECT COUNT(*) FROM doctors")
        assert result.ok is True

    def test_allows_select_with_limit(self, validator: SQLValidator) -> None:
        result = validator.validate("SELECT * FROM doctors LIMIT 100")
        assert result.ok is True


class TestLengthValidation:
    def test_blocks_overly_long_query(self) -> None:
        v = SQLValidator(max_query_length=30)
        result = v.validate("SELECT * FROM doctors LIMIT 100")
        assert result.ok is False
        assert result.rule == "max_length"

    def test_allows_query_within_limit(self, validator: SQLValidator) -> None:
        result = validator.validate("SELECT * FROM doctors LIMIT 10")
        assert result.ok is True


class TestComplexQueries:
    def test_allows_join_with_limit(self, validator: SQLValidator) -> None:
        result = validator.validate(
            "SELECT d.name, r.name AS rank FROM doctors d "
            "JOIN ranks r ON d.rank_id = r.id LIMIT 10"
        )
        assert result.ok is True

    def test_allows_subquery_with_limit(self, validator: SQLValidator) -> None:
        result = validator.validate(
            "SELECT * FROM doctors WHERE id IN (SELECT doctor_id FROM calendar_assignments) LIMIT 10"
        )
        assert result.ok is True

    def test_blocks_file_write(self, validator: SQLValidator) -> None:
        result = validator.validate(
            "SELECT * INTO OUTFILE '/tmp/data.csv' FROM doctors LIMIT 1"
        )
        assert result.ok is False
        assert result.rule == "file_write"
