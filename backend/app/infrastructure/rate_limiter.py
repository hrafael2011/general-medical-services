"""Simple in-memory sliding-window rate limiter for the Telegram webhook."""

import time
from collections import defaultdict


class RateLimiter:
    """Sliding-window rate limiter per key.

    Tracks request timestamps per *key* (typically ``telegram_user_id``).
    Returns ``True`` if the request is allowed, ``False`` if rate-limited.

    Thread-safe enough for Gunicorn/Uvicorn workers since each worker
    has its own in-memory state.
    """

    def __init__(self, max_requests: int = 20, window_seconds: int = 60) -> None:
        self._max = max_requests
        self._window = window_seconds
        self._buckets: dict[str, list[float]] = defaultdict(list)

    def allow(self, key: str) -> bool:
        now = time.time()
        cutoff = now - self._window
        timestamps = self._buckets[key]
        # Remove timestamps outside the window
        self._buckets[key] = [t for t in timestamps if t > cutoff]
        bucket = self._buckets[key]
        if len(bucket) >= self._max:
            return False
        bucket.append(now)
        return True

    def remaining(self, key: str) -> int:
        """Return how many requests are still allowed in the current window."""
        now = time.time()
        cutoff = now - self._window
        timestamps = [t for t in self._buckets[key] if t > cutoff]
        return max(0, self._max - len(timestamps))
