"""Rate limiting: a fixed budget of requests per caller per minute (APP_RATE_LIMIT_PER_MINUTE).

The caller is identified by its credential (hashed, never stored) or, without one, its network
address. Refused requests get 429 with Retry-After and are audited like any other call.

Counters live in this process's memory, so with several API replicas each replica counts
separately. A shared store (Redis) is the next step when that matters.
"""
from __future__ import annotations

import hashlib
import time
from collections.abc import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

EXEMPT_PATHS = ("/api/v1/platform/health",)


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limit_per_minute: int, clock: Callable[[], float] = time.monotonic):
        super().__init__(app)
        self.limit = limit_per_minute
        self.clock = clock
        self._windows: dict[str, tuple[int, int]] = {}     # caller -> (window number, count)

    def _caller(self, request: Request) -> str:
        credential = request.headers.get("authorization")
        if credential:
            return "c:" + hashlib.sha256(credential.encode()).hexdigest()[:24]
        return "ip:" + (request.client.host if request.client else "unknown")

    async def dispatch(self, request: Request, call_next):
        if self.limit <= 0 or not request.url.path.startswith("/api/") or request.url.path in EXEMPT_PATHS:
            return await call_next(request)
        now = self.clock()
        window = int(now // 60)
        caller = self._caller(request)
        seen_window, count = self._windows.get(caller, (window, 0))
        if seen_window != window:
            count = 0
        if count >= self.limit:
            retry_after = max(1, int(60 - (now % 60)))
            return JSONResponse({"detail": "Rate limit exceeded"}, status_code=429,
                                headers={"Retry-After": str(retry_after)})
        self._windows[caller] = (window, count + 1)
        if len(self._windows) > 10_000:                     # forget callers from past windows
            self._windows = {k: v for k, v in self._windows.items() if v[0] == window}
        return await call_next(request)
