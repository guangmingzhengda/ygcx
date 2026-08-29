from __future__ import annotations

import logging
from urllib.parse import quote, urlparse

from app.services.adapters import RawJob
from app.services.html_parse import (
    clean_text,
    company_from_campaign,
    extract_json_blobs,
    jobs_from_links,
    meta_content,
    resolve_apply_url,
    soup_from,
    walk_jobs_from_json,
)
from app.services.http_client import fetch_html

logger = logging.getLogger(__name__)

NOWCODER_PAGES = [
    "https://www.nowcoder.com/jobs/recommend/campus",
    "https://nowpick.nowcoder.com/jobs/school/schedule",
]


def _dedupe(jobs: list[RawJob]) -> list[RawJob]:
    seen: set[str] = set()
    out: list[RawJob] = []
    for job in jobs:
        key = f"{job.title}|{job.apply_url}"
        if key in seen:
            continue
        seen.add(key)
        out.append(job)
    return out


async def fetch_nowcoder() -> list[RawJob]:
    collected: list[RawJob] = []
    for url in NOWCODER_PAGES:
        try:
            html = await fetch_html(url)
        except Exception:
            logger.warning("nowcoder fetch failed: %s", url, exc_info=True)
            continue
        soup = soup_from(html)
        info = meta_content(soup, "description", "og:description")
        for blob in extract_json_blobs(html):
            walk_jobs_from_json(blob, collected, "nowcoder")
        for job in jobs_from_links(html, url, "nowcoder"):
            if not job.company:
                job.company = company_from_campaign(clean_text(job.title))
            if not job.description:
                job.description = info
            if not job.official_url:
                job.official_url = url
            job.job_type = "校招"
            collected.append(job)
        page_jobs = collected[:]
        for job in page_jobs:
            job.title = clean_text(job.title)
            job.company = clean_text(job.company) or company_from_campaign(job.title)
            job.apply_url = resolve_apply_url(job.apply_url, url)
            if not job.official_url:
                job.official_url = url
            job.source = "nowcoder"
        if not any(j.apply_url for j in collected):
            # 页面多为客户端渲染时，至少保留入口卡片
            collected.append(
                RawJob(
                    title="牛客校招日程 / 职位广场",
                    company="牛客网",
                    job_type="校招",
                    source="nowcoder",
                    apply_url=url,
                    official_url=url,
                    description=info or "公开校招日程与网申入口，点击跳转牛客查看最新岗位。",
                    tags=["校招", "牛客"],
                    company_info="牛客网聚合互联网校招、实习与网申信息。",
                )
            )
    for job in collected:
        job.source = "nowcoder"
        job.title = clean_text(job.title)
        job.company = clean_text(job.company) or company_from_campaign(job.title)
        if not job.apply_url:
            job.apply_url = NOWCODER_PAGES[0]
        elif job.apply_url.startswith("/"):
            job.apply_url = resolve_apply_url(job.apply_url, NOWCODER_PAGES[0])
    return _dedupe(collected)[:40]


def is_boss_public_url(url: str) -> bool:
    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return False
    if parsed.scheme not in {"http", "https"}:
        return False
    host = (parsed.hostname or "").lower()
    return host in {"www.zhipin.com", "zhipin.com", "www.bosszhipin.com"}


def boss_search_url(keyword: str, city: str = "") -> str:
    query = quote((keyword or "校招").strip() or "校招")
    url = f"https://www.zhipin.com/web/geek/job?query={query}"
    if city:
        url += f"&city={quote(city)}"
    return url
