"""Retries with backoff. Only errors marked transient are retried; everything else fails at once."""
from __future__ import annotations

import time
from collections.abc import Callable

from pydantic import BaseModel


class TransientError(Exception):
    """A failure worth retrying: timeout, dropped connection, rate limit, provider overload."""


class RetriesExhausted(Exception):
    """A transient failure kept happening until the retry policy gave up."""


class RetryPolicy(BaseModel):
    max_attempts: int = 3          # total tries, including the first
    base_delay_s: float = 0.5      # wait before the 2nd try; doubles each time
    max_delay_s: float = 8.0


def call_with_retry[T](fn: Callable[[], T], policy: RetryPolicy, *, sleep: Callable[[float], None] = time.sleep,
                    on_retry: Callable[[int, Exception], None] | None = None) -> T:
    for attempt in range(1, policy.max_attempts + 1):
        try:
            return fn()
        except TransientError as exc:
            if attempt >= policy.max_attempts:
                raise RetriesExhausted(f"gave up after {attempt} attempts: {exc}") from exc
            if on_retry:
                on_retry(attempt, exc)
            sleep(min(policy.max_delay_s, policy.base_delay_s * 2 ** (attempt - 1)))
    raise AssertionError("unreachable")
