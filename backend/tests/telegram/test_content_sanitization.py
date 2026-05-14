"""Tests for content sanitization in agent responses."""
import pytest
from backend.app.application.telegram.sanitize import sanitize_text


def test_sanitize_strips_html_tags():
    assert sanitize_text("<script>alert(1)</script>") == "alert(1)"


def test_sanitize_handles_normal_text():
    assert sanitize_text("Dr. Juan Pérez") == "Dr. Juan Pérez"


def test_sanitize_handles_empty():
    assert sanitize_text("") == ""


def test_sanitize_handles_none():
    assert sanitize_text(None) == ""


def test_sanitize_strips_multiple_tags():
    assert sanitize_text("<b>Dr.</b> <i>García</i>") == "Dr. García"


def test_sanitize_strips_img_and_svg():
    assert sanitize_text("<img src=x onerror=alert(1)>") == ""
    assert sanitize_text("<svg/onload=alert(1)>") == ""


def test_format_rows_sanitizes_values():
    """format_rows sanitizes DB values."""
    from backend.app.application.telegram.sanitize import format_rows

    rows = [{"name": "<script>alert(1)</script>", "sex": "male"}]
    result = format_rows(rows, ["name", "sex"])
    assert "<script>" not in result
    assert "alert(1)" in result


def test_agent_format_rows_sanitizes_xss():
    """format_rows sanitizes dangerous values."""
    from backend.app.application.telegram.sanitize import format_rows

    rows = [{"name": "<script>x</script>", "count": 5}]
    result = format_rows(rows, ["name", "count"])
    assert "<script>" not in result
    assert "x" in result


def test_intent_router_format_sanitizes_xss():
    """format_rows sanitizes dangerous values from DB."""
    from backend.app.application.telegram.sanitize import format_rows

    rows = [
        {"name": "<script>alert(1)</script>", "area": "<img src=x>"},
    ]
    result = format_rows(rows, ["name", "area"])
    assert "<script>" not in result
    assert "<img" not in result
    assert "alert(1)" in result
