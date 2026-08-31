from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from urllib.parse import quote, urljoin, urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Experience
from app.schemas import ExperiencePostOut, ExperienceSearchLink
from app.services.adapters.official import load_companies
from app.services.company_catalog import canonical_company_name, lookup_company, title_mentions_company
from app.services.html_parse import clean_text, soup_from
from app.services.http_client import fetch_html

logger = logging.getLogger(__name__)

HINT = re.compile(r"面经|凉经|一面|二面|三面|面试|面过|已offer|秋招|春招|求职|网申|实习面")
NOISE = re.compile(r"内推码|测评题|项目进阶|打招呼|登录|注册|下载 App|帮助中心|字节码")
POST_PATH = re.compile(r"/(?:discuss/\d+|feed/main/detail/[0-9a-fA-F]+)")
SF_POST_PATH = re.compile(r"^/(?:a|q)/\d+")

NOWCODER_INDEX = ["https://www.nowcoder.com/discuss?type=2&order=3"]
SEGMENTFAULT_INDEX = ["https://segmentfault.com/search?q=" + quote("校招 面经")]

SEARCH_SOURCES: tuple[tuple[str, str, str], ...] = (
    ("nowcoder", "牛客", "https://www.nowcoder.com/search?type=post&query={q}"),
    ("zhihu", "知乎", "https://www.zhihu.com/search?type=content&q={q}"),
    ("juejin", "掘金", "https://juejin.cn/search?query={q}&type=2"),
    ("csdn", "CSDN", "https://so.csdn.net/so/search?q={q}&t=blog"),
    ("xiaohongshu", "小红书", "https://www.xiaohongshu.com/search_result?keyword={q}"),
    ("segmentfault", "思否", "https://segmentfault.com/search?q={q}"),
    ("v2ex", "V2EX", "https://www.sov2ex.com/?q={q}"),
    ("yingjiesheng", "应届生", "https://www.baidu.com/s?wd={q}"),
)


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def experience_id_for(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


def _search_query(company: str, role: str = "", *, for_site: str = "") -> str:
    name = canonical_company_name(company)
    if not name or "牛客" in name:
        query = " ".join(part for part in [role, "校招 面经"] if part).strip()
    else:
        query = " ".join(part for part in [name, role, "校招 面经"] if part).strip()
    query = query or "校招 面经"
    if for_site == "yingjiesheng":
        return f"site:yingjiesheng.com {query}"
    return query


def nowcoder_experience_url(company: str, role: str = "") -> str:
    return f"https://www.nowcoder.com/search?type=post&query={quote(_search_query(company, role))}"


def zhihu_experience_url(company: str, role: str = "") -> str:
    return f"https://www.zhihu.com/search?type=content&q={quote(_search_query(company, role))}"


def experience_search_links(company: str, role: str = "") -> list[ExperienceSearchLink]:
    links: list[ExperienceSearchLink] = []
    for source, label, template in SEARCH_SOURCES:
        query = _search_query(company, role, for_site=source)
        links.append(
            ExperienceSearchLink(
                source=source,
                label=f"{label}面经搜索",
                url=template.format(q=quote(query)),
            )
        )
    return links


def _clean_nowcoder_url(href: str, base: str) -> str:
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


def _clean_segmentfault_url(href: str) -> str:
    parsed = urlparse(urljoin("https://segmentfault.com", href.split("#")[0]))
    if parsed.scheme not in {"http", "https"}:
        return ""
    host = (parsed.hostname or "").lower()
    if "segmentfault.com" not in host:
        return ""
    if not SF_POST_PATH.search(parsed.path):
        return ""
    return f"https://segmentfault.com{parsed.path}"


def _resolve_company(title: str, hint: str = "") -> str:
    if hint and title_mentions_company(title, hint):
        return canonical_company_name(hint)
    rec = lookup_company(title)
    if rec and rec.get("name"):
        return str(rec["name"])
    return ""


def _accept_title(title: str, hint: str = "") -> bool:
    if not title or len(title) < 8 or len(title) > 80:
        return False
    if NOISE.search(title) or not HINT.search(title):
        return False
    if hint and not title_mentions_company(title, hint):
        return False
    return True


def parse_experience_posts(html: str, base_url: str, company_hint: str = "") -> list[dict]:
    soup = soup_from(html)
    seen: set[str] = set()
    posts: list[dict] = []
    for a in soup.find_all("a", href=True):
        title = clean_text(a.get_text(" ", strip=True))
        if not _accept_title(title, company_hint):
            continue
        url = _clean_nowcoder_url(str(a["href"]), base_url)
        if not url or url in seen:
            continue
        company = _resolve_company(title, company_hint)
        if not company:
            continue
        seen.add(url)
        posts.append({"title": title, "url": url, "company": company, "source": "nowcoder"})
        if len(posts) >= 8:
            break
    return posts


def _next_data(html: str) -> dict:
    match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not match:
        return {}
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def parse_segmentfault_posts(html: str, company_hint: str = "") -> list[dict]:
    data = _next_data(html)
    rows = (
        data.get("props", {})
        .get("pageProps", {})
        .get("initialState", {})
        .get("search", {})
        .get("result", {})
        .get("rows", [])
    )
    if not isinstance(rows, list):
        return []
    seen: set[str] = set()
    posts: list[dict] = []
    for row in rows:
        if not isinstance(row, dict) or row.get("type") != "article":
            continue
        contents = row.get("contents") or {}
        if not isinstance(contents, dict):
            continue
        title = clean_text(str(contents.get("title") or ""))
        if not _accept_title(title, company_hint):
            continue
        url = _clean_segmentfault_url(str(contents.get("url") or ""))
        if not url or url in seen:
            continue
        company = _resolve_company(title, company_hint)
        if not company:
            continue
        seen.add(url)
        posts.append({"title": title, "url": url, "company": company, "source": "segmentfault"})
        if len(posts) >= 8:
            break
    return posts


def _company_names() -> list[str]:
    names = [str(c.get("name") or "") for c in load_companies() if c.get("name")]
    return [n for n in names if n and "牛客" not in n]


async def _collect(
    index_pages: list[str],
    company_pages: list[tuple[str, str]],
    parse,
    *,
    budget_seconds: float,
    per_company: int,
    cap: int,
) -> list[dict]:
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
        for post in parse(html, hint, url):
            if post["url"] in seen:
                continue
            seen.add(post["url"])
            collected.append(post)
            by_company[post["company"]] += 1

    for url in index_pages:
        if loop.time() >= deadline or len(collected) >= cap:
            break
        await ingest(url, "")
    remaining = sorted(company_pages, key=lambda item: by_company.get(item[1], 0))
    for url, hint in remaining:
        if loop.time() >= deadline or len(collected) >= cap:
            break
        if hint and by_company.get(hint, 0) >= per_company:
            continue
        await ingest(url, hint)
    return collected[:cap]


async def fetch_nowcoder_experiences(budget_seconds: float = 18.0) -> list[dict]:
    company_pages = [(nowcoder_experience_url(name), name) for name in _company_names()]
    return await _collect(
        NOWCODER_INDEX,
        company_pages,
        lambda html, hint, url: parse_experience_posts(html, url, hint),
        budget_seconds=budget_seconds,
        per_company=3,
        cap=80,
    )


async def fetch_segmentfault_experiences(budget_seconds: float = 18.0) -> list[dict]:
    company_pages = [
        (f"https://segmentfault.com/search?q={quote(_search_query(name))}", name)
        for name in _company_names()
    ]
    return await _collect(
        SEGMENTFAULT_INDEX,
        company_pages,
        lambda html, hint, _url: parse_segmentfault_posts(html, hint),
        budget_seconds=budget_seconds,
        per_company=2,
        cap=80,
    )


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
        row.source = str(post.get("source") or "nowcoder")[:32]
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


def list_experiences_for(db: Session, company: str, limit: int = 4) -> list[ExperiencePostOut]:
    name = canonical_company_name(company)
    if not name or "牛客" in name:
        return []
    rows = list(
        db.scalars(
            select(Experience)
            .where(Experience.company == name)
            .order_by(Experience.fetched_at.desc())
            .limit(max(limit, 1) * 6)
        )
    )
    buckets: dict[str, list[Experience]] = defaultdict(list)
    for row in rows:
        buckets[row.source or "nowcoder"].append(row)
    out: list[ExperiencePostOut] = []
    seen: set[str] = set()
    sources = list(buckets)
    while len(out) < limit:
        progressed = False
        for source in sources:
            if not buckets[source]:
                continue
            row = buckets[source].pop(0)
            if row.url in seen:
                continue
            seen.add(row.url)
            out.append(ExperiencePostOut(title=row.title, url=row.url, source=row.source))
            progressed = True
            if len(out) >= limit:
                break
        if not progressed:
            break
    return out


async def refresh_experiences(db: Session) -> int:
    results = await asyncio.gather(
        fetch_nowcoder_experiences(),
        fetch_segmentfault_experiences(),
        return_exceptions=True,
    )
    posts: list[dict] = []
    for result in results:
        if isinstance(result, BaseException):
            logger.warning("experience source failed: %s", result)
            continue
        posts.extend(result)
    if posts:
        upsert_experiences(db, posts)
    return len(list(db.scalars(select(Experience))))
