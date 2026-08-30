from __future__ import annotations

from functools import lru_cache
from urllib.parse import urlparse

from app.services.adapters.official import load_companies

ALIASES = {
    "字节": "字节跳动",
    "头条": "字节跳动",
    "抖音": "字节跳动",
    "阿里": "阿里巴巴",
    "淘天": "阿里巴巴",
    "菜鸟": "阿里巴巴",
    "企鹅": "腾讯",
    "微信": "腾讯",
    "雷火": "网易",
    "网易游戏": "网易",
    "互娱": "网易",
    "美团点评": "美团",
    "快手科技": "快手",
    "小米集团": "小米",
    "京东集团": "京东",
    "滴滴出行": "滴滴",
    "理想": "理想汽车",
}


@lru_cache(maxsize=1)
def _records() -> list[dict]:
    return load_companies()


def canonical_company_name(name: str) -> str:
    rec = lookup_company(name)
    if rec and rec.get("name"):
        return str(rec["name"])
    return (name or "").strip()


def company_keywords(name: str) -> list[str]:
    rec = lookup_company(name)
    canon = str((rec or {}).get("name") or name or "").strip()
    keys = [canon] if canon else []
    if rec:
        for alias, target in ALIASES.items():
            if target == rec.get("name") and alias not in keys:
                keys.append(alias)
    return [k for k in keys if len(k) >= 2]


def title_mentions_company(title: str, company: str) -> bool:
    blob = (title or "").replace(" ", "").replace("·", "")
    if not blob:
        return False
    return any(key and key in blob for key in company_keywords(company))


def lookup_company(name: str) -> dict | None:
    raw = (name or "").replace(" ", "").replace("·", "")
    if not raw:
        return None
    for company in _records():
        cname = str(company.get("name") or "")
        if cname and (cname in raw or raw in cname):
            return company
    for alias, canonical in ALIASES.items():
        if alias in raw:
            for company in _records():
                if company.get("name") == canonical:
                    return company
    return None


def _host(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except ValueError:
        return ""


def is_aggregator(url: str) -> bool:
    raw = (url or "").strip()
    if not raw.startswith(("http://", "https://")):
        return True
    host = _host(raw)
    return any(
        part in host
        for part in ("nowcoder.com", "zhipin.com", "bosszhipin.com", "liepin.com", "51job.com")
    )


def resolve_company_links(company: str, apply_url: str, official_url: str) -> tuple[str, str]:
    """返回 (投递链接, 公司官网)。官网优先用简介站，投递用校招页。"""
    rec = lookup_company(company)
    apply = apply_url or ""
    official = official_url or ""
    homepage = str((rec or {}).get("site_url") or "")
    career = str((rec or {}).get("apply_url") or (rec or {}).get("career_url") or "")
    if not apply:
        apply = career
    if homepage:
        official = homepage
    elif is_aggregator(official) and career:
        official = career
    if "牛客" in (company or "") and is_aggregator(apply or official):
        official = "https://www.nowcoder.com/"
    if official and apply and official.rstrip("/") == apply.rstrip("/") and homepage:
        official = homepage
    if official and apply and official.rstrip("/") == apply.rstrip("/"):
        official = ""
    if official and not official.startswith(("http://", "https://")):
        official = homepage
    if official and is_aggregator(official) and homepage:
        official = homepage
    if official and is_aggregator(official) and "牛客" not in (company or ""):
        official = ""
    return apply, official
