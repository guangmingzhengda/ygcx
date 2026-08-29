from __future__ import annotations

import json
import re
from html import unescape
from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup

from app.services.adapters import RawJob

JOB_HINT = re.compile(
    r"招聘|校招|实习|岗位|职位|campus|career|join|jobs?|position",
    re.I,
)
NOISE = re.compile(r"登录|注册|下载|隐私|协议|cookie|帮助中心", re.I)


def clean_text(text: str) -> str:
    text = unescape(text or "")
    text = re.sub(r"<br\s*/?>", " ", text, flags=re.I)
    text = soup_from(f"<div>{text}</div>").get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text).strip()


def resolve_apply_url(href: str, base: str) -> str:
    if not href:
        return base
    abs_url = urljoin(base, href)
    query = parse_qs(urlparse(abs_url).query)
    for key in ("url", "target"):
        values = query.get(key) or []
        if values and values[0].startswith(("http://", "https://")):
            return values[0]
    return abs_url


def soup_from(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def meta_content(soup: BeautifulSoup, *keys: str) -> str:
    for key in keys:
        tag = soup.find("meta", attrs={"name": key}) or soup.find("meta", attrs={"property": key})
        if tag and tag.get("content"):
            return unescape(str(tag["content"]).strip())
    return ""


def page_title(soup: BeautifulSoup) -> str:
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    h1 = soup.find("h1")
    if h1:
        return h1.get_text(" ", strip=True)
    return ""


def extract_json_blobs(html: str) -> list[dict]:
    blobs: list[dict] = []
    for match in re.finditer(
        r"(?:window\.__INITIAL_STATE__|window\.__NEXT_DATA__)\s*=\s*(\{.*?\})\s*;",
        html,
        re.S,
    ):
        try:
            blobs.append(json.loads(match.group(1)))
        except json.JSONDecodeError:
            continue
    soup = soup_from(html)
    for script in soup.find_all("script", type="application/ld+json"):
        text = script.string or ""
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            blobs.append(data)
        elif isinstance(data, list):
            blobs.extend(item for item in data if isinstance(item, dict))
    return blobs


def walk_jobs_from_json(obj: object, acc: list[RawJob], source: str) -> None:
    if isinstance(obj, dict):
        title = str(obj.get("title") or obj.get("jobName") or obj.get("name") or "")
        url = str(obj.get("url") or obj.get("jobUrl") or obj.get("link") or obj.get("applyUrl") or "")
        company = str(obj.get("company") or obj.get("companyName") or obj.get("orgName") or "")
        if title and JOB_HINT.search(title) and len(title) < 80:
            acc.append(
                RawJob(
                    title=title.strip(),
                    company=company.strip(),
                    city=str(obj.get("city") or obj.get("workCity") or obj.get("location") or ""),
                    source=source,
                    apply_url=url,
                    official_url=url,
                    description=str(obj.get("description") or obj.get("desc") or "")[:800],
                )
            )
        for value in obj.values():
            walk_jobs_from_json(value, acc, source)
    elif isinstance(obj, list):
        for item in obj[:80]:
            walk_jobs_from_json(item, acc, source)


def jobs_from_links(html: str, base_url: str, source: str, company: str = "") -> list[RawJob]:
    soup = soup_from(html)
    seen: set[str] = set()
    jobs: list[RawJob] = []
    for a in soup.find_all("a", href=True):
        text = a.get_text(" ", strip=True)
        href = str(a["href"]).strip()
        if not text or len(text) < 4 or len(text) > 80:
            continue
        if NOISE.search(text) or href.startswith("javascript:"):
            continue
        if not JOB_HINT.search(text) and not JOB_HINT.search(href):
            continue
        url = urljoin(base_url, href)
        if url in seen or url.rstrip("/") == base_url.rstrip("/"):
            continue
        seen.add(url)
        jobs.append(
            RawJob(
                title=text,
                company=company,
                source=source,
                apply_url=url,
                official_url=base_url,
            )
        )
        if len(jobs) >= 12:
            break
    return jobs


def company_from_campaign(title: str) -> str:
    cleaned = re.sub(r"\s+", "", title)
    cleaned = re.split(r"\d{4}届|校园招聘|秋季校招|春季校招|招聘开启|邀您投递", cleaned, maxsplit=1)[0]
    cleaned = cleaned.strip("·-|—_！!")
    return cleaned[:32] if cleaned else title[:32]
