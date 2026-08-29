from __future__ import annotations

import asyncio
from collections import defaultdict

from app.config import settings


class HostLimiter:
    """同一域名请求之间保持间隔，避免对公开页过于频繁访问。"""

    def __init__(self, interval: float | None = None) -> None:
        self.interval = interval if interval is not None else settings.request_interval_seconds
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._last: dict[str, float] = {}

    async def wait(self, host: str) -> None:
        lock = self._locks[host]
        async with lock:
            loop = asyncio.get_running_loop()
            now = loop.time()
            last = self._last.get(host, 0.0)
            delay = self.interval - (now - last)
            if delay > 0:
                await asyncio.sleep(delay)
            self._last[host] = loop.time()


limiter = HostLimiter()
