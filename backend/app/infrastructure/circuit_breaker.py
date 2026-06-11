"""Circuit breaker for external API calls.

Protects against cascading failures when upstream services (DeepSeek,
Telegram, Meta) are unavailable — fails fast instead of retrying indefinitely.
"""

import threading
import time
from collections.abc import Callable
from enum import Enum
from typing import Any, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


class CircuitState(Enum):
    CLOSED = "closed"        # Normal operation — calls pass through
    OPEN = "open"            # Failing — calls are rejected immediately
    HALF_OPEN = "half_open"  # Probing recovery — one call allowed through


class CircuitBreakerError(Exception):
    """Raised when a call is rejected because the circuit is OPEN."""


class CircuitBreaker:
    """Thread-safe circuit breaker for external API calls.

    Usage::

        breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60)
        result = breaker.call(some_api_function, arg1, arg2)
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
    ) -> None:
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._failure_count = 0
        self._last_failure_time: float = 0.0
        self._state = CircuitState.CLOSED
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        with self._lock:
            return self._state

    @property
    def failure_count(self) -> int:
        with self._lock:
            return self._failure_count

    def call(self, func: F, *args: Any, **kwargs: Any) -> Any:
        """Execute *func* if the circuit allows it.

        Raises:
            CircuitBreakerError: if the circuit is OPEN.
            Original exception: if *func* raises while the circuit is
                CLOSED or HALF_OPEN.
        """
        with self._lock:
            if self._state == CircuitState.OPEN:
                if time.time() - self._last_failure_time >= self._recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
                else:
                    raise CircuitBreakerError(
                        f"Circuit breaker is OPEN "
                        f"({self._failure_count} failures, "
                        f"retry in {self._recovery_timeout - (time.time() - self._last_failure_time):.0f}s)"
                    )

        try:
            result = func(*args, **kwargs)
        except Exception:
            with self._lock:
                self._failure_count += 1
                self._last_failure_time = time.time()
                if self._failure_count >= self._failure_threshold:
                    self._state = CircuitState.OPEN
            raise

        # Success — reset on HALF_OPEN probe or normal CLOSED
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.CLOSED
            self._failure_count = 0

        return result
