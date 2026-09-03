from __future__ import annotations

import time
from collections import defaultdict, deque
from hmac import compare_digest
from threading import Lock

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.config import settings

_PUBLIC_API = {"/api/health"}


class _WindowLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str, limit: int, window_sec: float) -> bool:
        now = time.monotonic()
        with self._lock:
            queue = self._hits[key]
            while queue and now - queue[0] > window_sec:
                queue.popleft()
            if len(queue) >= limit:
                return False
            queue.append(now)
            return True


_limiter = _WindowLimiter()


def client_ip(request: Request) -> str:
    peer = request.client.host if request.client else "unknown"
    if peer in {"127.0.0.1", "::1"}:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip() or peer
    return peer


class AccessGateMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method == "OPTIONS":
            return await call_next(request)
        path = request.url.path
        token = settings.access_token.strip()
        if token and path.startswith("/api") and path not in _PUBLIC_API:
            provided = request.headers.get("x-access-token", "")
            if not provided or not compare_digest(provided, token):
                return JSONResponse({"detail": "需要访问口令"}, status_code=401)
        if path.startswith("/api/chat"):
            if not _limiter.allow(f"chat:{client_ip(request)}", 20, 600):
                return JSONResponse({"detail": "对话太频繁，请稍后再试"}, status_code=429)
        if path == "/api/jobs/refresh" or (
            path.startswith("/api/jobs/search") and "refresh=true" in (request.url.query or "")
        ):
            if not _limiter.allow(f"refresh:{client_ip(request)}", 4, 3600):
                return JSONResponse({"detail": "刷新太频繁，请稍后再试"}, status_code=429)
        return await call_next(request)
