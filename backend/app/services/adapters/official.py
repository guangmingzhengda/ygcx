from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import yaml

from app.config import settings
from app.services.adapters import RawJob
from app.services.html_parse import jobs_from_links, meta_content, page_title, soup_from
from app.services.http_client import fetch_html

logger = logging.getLogger(__name__)


def load_companies(path: Path | None = None) -> list[dict]:
    target = path or settings.companies_path
    with target.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return list(data.get("companies") or [])


def _portal_job(company: dict, description: str = "") -> RawJob:
    name = str(company.get("name") or "未知公司")
    apply = str(company.get("apply_url") or company.get("career_url") or "")
    homepage = str(company.get("site_url") or "")
    tags = company.get("tags") or []
    if not isinstance(tags, list):
        tags = [str(tags)]
    industry = str(company.get("industry") or "")
    tag_list = [str(t) for t in tags]
    if industry and industry not in tag_list:
        tag_list.append(industry)
    return RawJob(
        title=f"{name} 校园招聘入口",
        company=name,
        city=str(company.get("city") or ""),
        job_type="校招",
        source="official",
        apply_url=apply,
        official_url=homepage,
        description=description or str(company.get("blurb") or ""),
        tags=tag_list,
        company_info=str(company.get("blurb") or ""),
    )


def seed_portals() -> list[RawJob]:
    return [_portal_job(company) for company in load_companies()]


async def _enrich_company(company: dict) -> list[RawJob]:
    career_url = str(company.get("career_url") or "")
    portal = _portal_job(company)
    extra: list[RawJob] = []
    if career_url:
        try:
            html = await fetch_html(career_url)
            soup = soup_from(html)
            desc = meta_content(soup, "description", "og:description") or page_title(soup)
            if desc:
                portal.description = desc[:500]
                if not portal.company_info:
                    portal.company_info = desc[:300]
            extra = jobs_from_links(html, career_url, "official", str(company.get("name") or ""))
            extra = [
                job
                for job in extra
                if "管理系统" not in job.title and "mokahr.com" not in (job.apply_url or "")
            ]
            homepage = str(company.get("site_url") or "")
            for job in extra:
                job.city = job.city or str(company.get("city") or "")
                job.company_info = portal.company_info
                job.official_url = homepage
                job.tags = list(portal.tags)
        except Exception:
            logger.warning("official fetch failed: %s", career_url, exc_info=True)
    return [portal, *extra[:6]]


async def fetch_official() -> list[RawJob]:
    companies = load_companies()
    sem = asyncio.Semaphore(3)

    async def bound(company: dict) -> list[RawJob]:
        async with sem:
            return await _enrich_company(company)

    chunks = await asyncio.gather(*(bound(company) for company in companies))
    collected: list[RawJob] = []
    for chunk in chunks:
        collected.extend(chunk)
    return collected
