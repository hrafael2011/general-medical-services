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
