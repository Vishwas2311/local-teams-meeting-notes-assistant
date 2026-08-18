"""Small bounded exponential retry helper."""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


def with_retry(
    operation: Callable[[], T],
    *,
    attempts: int,
    retryable: Callable[[Exception], bool],
    base_delay: float = 1.0,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Run an operation with finite exponential backoff and jitter."""
    for attempt in range(attempts + 1):
        try:
            return operation()
        except Exception as exc:
            if attempt >= attempts or not retryable(exc):
                raise
            sleep(base_delay * (2**attempt) + random.uniform(0, 0.25))
    raise RuntimeError("unreachable")
