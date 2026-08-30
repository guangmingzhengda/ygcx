from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from urllib.parse import quote, urljoin, urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Experience
from app.schemas import ExperiencePostOut
from app.services.adapters.official import load_companies
from app.services.company_catalog import canonical_company_name, lookup_company, title_mentions_company
from app.services.html_parse import clean_text, soup_from
from app.services.http_client import fetch_html

logger = logging.getLogger(__name__)

HINT = re.compile(r"面经|凉经|一面|二面|三面|面试|秋招|春招|求职|网申|实习面")
NOISE = re.compile(r"内推码|测评题|项目进阶|打招呼|登录|注册|下载 App|帮助中心")
POST_PATH = re.compile(r"/(?:discuss/\d+|feed/main/detail/[0-9a-fA-F]+)")

INDEX_PAGES = [
    "https://www.nowcoder.com/discuss?type=2&order=3",
]


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def experience_id_for(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


def nowcoder_experience_url(company: str, role: str = "") -> str:
    name = canonical_company_name(company)
    if not name or "牛客" in name:
        query = " ".join(part for part in [role, "校招 面经"] if part).strip()
    else:
        query = " ".join(part for part in [name, role, "校招 面经"] if part).strip()
    return f"https://www.nowcoder.com/search?type=post&query={quote(query or '校招 面经')}"


def zhihu_experience_url(company: str, role: str = "") -> str:
    name = canonical_company_name(company)
    if not name or "牛客" in name:
        query = " ".join(part for part in [role, "校招 面经"] if part).strip()
    else:
        query = " ".join(part for part in [name, role, "校招 面经"] if part).strip()
    return f"https://www.zhihu.com/search?type=content&q={quote(query or '校招 面经')}"


def _clean_url(href: str, base: str) -> str:
    abs_url = urljoin(base, href.split("#")[0])
    parsed = urlparse(abs_url)
    if parsed.scheme not in {"http", "https"}:
        return ""
    host = (parsed.hostname or "").lower()
    if "nowcoder.com" not in host:
        return ""
    if not POST_PATH.search(parsed.path):
        return ""
    return f"{parsed.scheme}://{host}{parsed.path}"


def _infer_company(title: str, hint: str = "") -> str:
    rec = lookup_company(title)
    if rec and rec.get("name"):
        return str(rec["name"])
    if hint and title_mentions_company(title, hint):
        return canonical_company_name(hint)
    return ""


def parse_experience_posts(html: str, base_url: str, company_hint: str = "") -> list[dict]:
    soup = soup_from(html)
    seen: set[str] = set()
    posts: list[dict] = []
    for a in soup.find_all("a", href=True):
        title = clean_text(a.get_text(" ", strip=True))
        if not title or len(title) < 8 or len(title) > 80:
            continue
        if NOISE.search(title) or not HINT.search(title):
            continue
        url = _clean_url(str(a["href"]), base_url)
        if not url or url in seen:
            continue
        company = _infer_company(title, company_hint)
        if company_hint and not title_mentions_company(title, company_hint):
            continue
        if not company:
            continue
        seen.add(url)
        posts.append({"title": title, "url": url, "company": company, "source": "nowcoder"})
        if len(posts) >= 8:
            break
    return posts


def _target_pages() -> list[tuple[str, str]]:
    pages = [(url, "") for url in INDEX_PAGES]
    for company in load_companies():
        name = str(company.get("name") or "")
        if name:
            pages.append((nowcoder_experience_url(name), name))
    return pages


async def fetch_nowcoder_experiences(budget_seconds: float = 20.0) -> list[dict]:
    collected: list[dict] = []
    seen: set[str] = set()
    by_company: dict[str, int] = defaultdict(int)
    loop = asyncio.get_running_loop()
    deadline = loop.time() + budget_seconds

    async def ingest(url: str, hint: str) -> None:
        try:
            html = await fetch_html(url)
        except Exception:
            logger.warning("experience fetch failed: %s", url, exc_info=True)
            return
        for post in parse_experience_posts(html, url, hint):
            if post["url"] in seen:
                continue
            seen.add(post["url"])
            collected.append(post)
            by_company[post["company"]] += 1

    for url, hint in _target_pages()[: len(INDEX_PAGES)]:
        if loop.time() >= deadline:
            break
        await ingest(url, hint)
    names = [str(c.get("name") or "") for c in load_companies() if c.get("name")]
    names.sort(key=lambda name: by_company.get(name, 0))
    for name in names:
        if loop.time() >= deadline:
            break
        if by_company.get(name, 0) >= 3:
            continue
        await ingest(nowcoder_experience_url(name), name)
    return collected[:80]


def upsert_experiences(db: Session, posts: list[dict]) -> None:
    now = _now()
    seen: dict[str, Experience] = {}
    for post in posts:
        url = str(post.get("url") or "")
        if not url:
            continue
        eid = experience_id_for(url)
        row = seen.get(eid) or db.get(Experience, eid)
        if row is None:
            row = Experience(id=eid)
            db.add(row)
        row.title = str(post.get("title") or "")[:256]
        row.url = url
        row.company = str(post.get("company") or "")
        row.source = str(post.get("source") or "nowcoder")
        row.fetched_at = now
        seen[eid] = row
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise


def experience_cache_is_stale(db: Session) -> bool:
    latest = db.scalar(select(Experience.fetched_at).order_by(Experience.fetched_at.desc()).limit(1))
    if latest is None:
        return True
    latest_naive = latest.replace(tzinfo=None) if latest.tzinfo else latest
    return _now() - latest_naive > timedelta(hours=settings.cache_ttl_hours)


def list_experiences_for(db: Session, company: str, limit: int = 3) -> list[ExperiencePostOut]:
    name = canonical_company_name(company)
    if not name or "牛客" in name:
        return []
    rows = list(
        db.scalars(
            select(Experience)
            .where(Experience.company == name)
            .order_by(Experience.fetched_at.desc())
            .limit(limit * 3)
        )
    )
    out: list[ExperiencePostOut] = []
    seen: set[str] = set()
    for row in rows:
        if row.url in seen:
            continue
        seen.add(row.url)
        out.append(ExperiencePostOut(title=row.title, url=row.url, source=row.source))
        if len(out) >= limit:
            break
    return out


async def refresh_experiences(db: Session) -> int:
    posts = await fetch_nowcoder_experiences()
    if posts:
        upsert_experiences(db, posts)
    return len(list(db.scalars(select(Experience))))
