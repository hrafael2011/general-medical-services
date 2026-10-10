"""Tests for the single password policy.

Both password flows used to duplicate these rules with different messages; every
cause must now be reported exactly.
"""

import pytest

from backend.app.core.security import (
    PASSWORD_MIN_LENGTH,
    PasswordProblem,
    check_password_strength,
    hash_password,
    password_error_detail,
)


def test_policy_minimum_is_eight() -> None:
    assert PASSWORD_MIN_LENGTH == 8


@pytest.mark.parametrize(
    ("password", "expected"),
    [
        ("Ab1!efg", PasswordProblem.TOO_SHORT),  # 7 chars
        ("ab1!efgh", PasswordProblem.NO_UPPERCASE),
        ("AB1!EFGH", PasswordProblem.NO_LOWERCASE),
        ("Abc!efgh", PasswordProblem.NO_DIGIT),
        ("Abc1efgh", PasswordProblem.NO_SPECIAL),
    ],
)
def test_each_rule_reports_its_own_cause(password: str, expected: PasswordProblem) -> None:
    assert check_password_strength(password) == expected


def test_eight_characters_is_accepted() -> None:
    assert check_password_strength("Ab1!efgh") is None


def test_seven_characters_is_rejected() -> None:
    assert check_password_strength("Ab1!efg") == PasswordProblem.TOO_SHORT


def test_password_equal_to_the_current_one_is_rejected() -> None:
    assert (
        check_password_strength("Abc1efgh!", current_password="Abc1efgh!")
        == PasswordProblem.SAME_AS_CURRENT
    )


def test_password_in_the_history_is_rejected() -> None:
    recent = [hash_password("OldPass1!")]

    assert check_password_strength("OldPass1!", recent_hashes=recent) == PasswordProblem.REUSED


def test_a_fresh_password_passes_with_history_present() -> None:
    recent = [hash_password("OldPass1!")]

    assert check_password_strength("Totally2@new", recent_hashes=recent) is None


def test_every_cause_has_a_distinct_message() -> None:
    """The point of the change: no generic sentence covering every case."""
    messages = {problem: password_error_detail(problem)["message"] for problem in PasswordProblem}

    assert len(set(messages.values())) == len(messages)
    for problem, message in messages.items():
        assert password_error_detail(problem)["code"] == problem.value
        assert message.endswith(".")


def test_unknown_problem_still_answers_with_a_code() -> None:
    detail = password_error_detail(None)

    assert detail["code"] == "password_rejected"
    assert detail["message"]
