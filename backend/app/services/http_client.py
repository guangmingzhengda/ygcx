from __future__ import annotations

import httpx

from app.services import limiter

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 JobNav/1.0"
)


async def fetch_html(url: str, timeout: float = 10.0) -> str:
    host = httpx.URL(url).host or "unknown"
    await limiter.wait(host)
    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT, "Accept-Language": "zh-CN,zh;q=0.9"},
        follow_redirects=True,
        timeout=timeout,
    ) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.text
