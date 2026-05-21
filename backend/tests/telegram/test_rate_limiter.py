"""Tests for the in-memory rate limiter."""
import time

from backend.app.infrastructure.rate_limiter import RateLimiter


def test_allows_first_request() -> None:
    """Primera request siempre permitida."""
    limiter = RateLimiter(max_requests=5, window_seconds=60)
    assert limiter.allow("user-1") is True


def test_allows_up_to_max() -> None:
    """Permite hasta max_requests, luego bloquea."""
    limiter = RateLimiter(max_requests=3, window_seconds=60)
    assert limiter.allow("user-1") is True
    assert limiter.allow("user-1") is True
    assert limiter.allow("user-1") is True
    assert limiter.allow("user-1") is False  # bloqueado
    assert limiter.remaining("user-1") == 0


def test_different_keys_independent() -> None:
    """Usuarios diferentes tienen buckets independientes."""
    limiter = RateLimiter(max_requests=2, window_seconds=60)
    assert limiter.allow("user-a") is True
    assert limiter.allow("user-a") is True
    assert limiter.allow("user-a") is False  # bloqueado
    assert limiter.allow("user-b") is True   # otro user, permitido


def test_sliding_window_expires() -> None:
    """Requests fuera de la ventana se descartan."""
    limiter = RateLimiter(max_requests=2, window_seconds=1)
    assert limiter.allow("user-1") is True
    assert limiter.allow("user-1") is True
    assert limiter.allow("user-1") is False  # bloqueado
    time.sleep(1.1)  # esperar que expire la ventana
    assert limiter.allow("user-1") is True   # renovado


def test_remaining_decreases() -> None:
    """remaining() refleja cuantos requests quedan."""
    limiter = RateLimiter(max_requests=5, window_seconds=60)
    assert limiter.remaining("user-1") == 5
    limiter.allow("user-1")
    assert limiter.remaining("user-1") == 4
    limiter.allow("user-1")
    assert limiter.remaining("user-1") == 3
