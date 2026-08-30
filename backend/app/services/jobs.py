from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Favorite, Job, Profile
from app.schemas import JobOut
from app.services.adapters import RawJob
from app.services.adapters.boss import boss_search_url
from app.services.adapters.nowcoder import fetch_nowcoder
from app.services.adapters.official import fetch_official, seed_portals
from app.services.experiences import (
    experience_cache_is_stale,
    list_experiences_for,
    nowcoder_experience_url,
    refresh_experiences,
    zhihu_experience_url,
)
from app.services.company_catalog import lookup_company, resolve_company_links
from app.services.filters import (
    Constraints,
    classify_job_type,
    expand_role_hints,
    keyword_tokens,
    parse_salary,
    salary_overlap,
    type_allowed,
)
from app.services.llm import rank_with_llm

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def job_id_for(raw: RawJob) -> str:
    basis = f"{raw.source}|{raw.apply_url or raw.title}|{raw.company}"
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16]


def _tags_dump(tags: list[str]) -> str:
    return json.dumps(tags, ensure_ascii=False)


def _tags_load(raw: str) -> list[str]:
    try:
        data = json.loads(raw or "[]")
        if isinstance(data, list):
            return [str(x) for x in data]
    except json.JSONDecodeError:
        pass
    return []


def upsert_jobs(db: Session, raws: list[RawJob]) -> None:
    now = _now()
    seen: dict[str, Job] = {}
    for raw in raws:
        jid = job_id_for(raw)
        existing = seen.get(jid) or db.get(Job, jid)
        if existing is None:
            existing = Job(id=jid)
            db.add(existing)
        blob = f"{raw.title} {raw.description} {raw.company_info}"
        smin, smax, stext = parse_salary(blob)
        if raw.salary_min or raw.salary_max:
            smin, smax = raw.salary_min, raw.salary_max
            stext = raw.salary_text or stext
        existing.title = raw.title
        existing.company = raw.company
        existing.city = raw.city
        existing.job_type = classify_job_type(raw.title, raw.description, " ".join(raw.tags), raw.job_type)
        existing.source = raw.source
        apply_url, official_url = resolve_company_links(raw.company, raw.apply_url, raw.official_url)
        existing.apply_url = apply_url
        existing.official_url = official_url
        existing.description = raw.description
        existing.tags = _tags_dump(raw.tags)
        existing.company_info = raw.company_info
        existing.salary_min = smin
        existing.salary_max = smax
        existing.salary_text = stext
        existing.fetched_at = now
        seen[jid] = existing
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise


def cache_is_stale(db: Session) -> bool:
    latest = db.scalar(select(Job.fetched_at).order_by(Job.fetched_at.desc()).limit(1))
    if latest is None:
        return True
    latest_naive = latest.replace(tzinfo=None) if latest.tzinfo else latest
    return _now() - latest_naive > timedelta(hours=settings.cache_ttl_hours)


async def refresh_jobs(db: Session) -> int:
    upsert_jobs(db, seed_portals())
    try:
        results = await asyncio.wait_for(
            asyncio.gather(fetch_nowcoder(), fetch_official(), return_exceptions=True),
            timeout=20,
        )
    except TimeoutError:
        logger.warning("refresh timed out; using whitelist portal cards")
        results = []
    merged: list[RawJob] = []
    for result in results:
        if isinstance(result, BaseException):
            logger.warning("adapter failed: %s", result)
            continue
        merged.extend(result)
    if merged:
        upsert_jobs(db, merged)
    try:
        await refresh_experiences(db)
    except Exception:
        logger.warning("experience refresh failed", exc_info=True)
    return len(list(db.scalars(select(Job))))


def _job_hay(job: Job) -> str:
    rec = lookup_company(job.company)
    extra = ""
    if rec:
        extra = " ".join(
            [
                str(rec.get("industry") or ""),
                str(rec.get("blurb") or ""),
                " ".join(str(t) for t in (rec.get("tags") or [])),
            ]
        )
    return " ".join(
        [
            job.title,
            job.company,
            job.city,
            job.description,
            job.company_info,
            " ".join(_tags_load(job.tags)),
            extra,
        ]
    ).lower()


def _merged_tags(job: Job) -> list[str]:
    tags = _tags_load(job.tags)
    rec = lookup_company(job.company)
    if not rec:
        return tags
    for item in rec.get("tags") or []:
        text = str(item)
        if text and text not in tags:
            tags.append(text)
    industry = str(rec.get("industry") or "")
    if industry and industry not in tags:
        tags.append(industry)
    return tags


def heuristic_score(profile: Profile, job: Job, keywords: str, constraints: Constraints | None = None) -> tuple[int, str]:
    hay = _job_hay(job)
    title = (job.title or "").lower()
    score = 22
    reasons: list[str] = []
    city = (constraints.city if constraints else "") or (profile.expected_city or "").strip()
    role = (profile.expected_role or "").strip()
    major = (profile.major or "").strip()
    query = " ".join(part for part in [keywords, role] if part)
    job_type = classify_job_type(job.title, job.description, job.tags, job.job_type)
    generic = any(mark in title for mark in ("校园招聘入口", "校招日程", "职位广场"))
    want_type = ((constraints.job_type if constraints else "") or profile.expected_job_type or "").strip()
    if want_type == "实习":
        if job_type == "实习":
            score += 16
            reasons.append("实习岗位")
        elif job_type == "校招":
            score += 6
            reasons.append("校招入口里通常也有实习，需打开确认")
        else:
            score -= 20
            reasons.append("不是实习/校招向")
    elif job_type == "校招":
        score += 10
        reasons.append("校招/应届向")
    elif job_type == "实习":
        score += 4
        reasons.append("实习岗位")
    if generic:
        score -= 12
        reasons.append("这是公司校招入口，不是具体岗位 JD")
    if city and city.lower() in hay:
        score += 14
        reasons.append(f"地点含「{city}」")
    elif city:
        score -= 16
        reasons.append(f"地点未明确写出「{city}」")
    hints = expand_role_hints(query)
    hit_hints = [h for h in hints if h in hay]
    if hit_hints:
        score += min(28, 7 * len(hit_hints[:4]))
        if any(h in title for h in hit_hints):
            score += 10
            reasons.append("标题里出现了你要的方向")
        else:
            reasons.append("公司方向接近「" + "、".join(hit_hints[:3]) + "」")
    elif query:
        score -= 10
        reasons.append("卡片文本未写明你搜的岗位方向")
    if major and major.lower() in hay:
        score += 8
        reasons.append(f"与专业「{major}」相关")
    for token in keyword_tokens(keywords):
        if token in hay and token not in hit_hints:
            score += 5
    skills = [s.strip() for s in (profile.skills or "").replace("，", ",").split(",") if s.strip()]
    hit_skills = [s for s in skills if s.lower() in hay]
    if hit_skills:
        score += min(12, 4 * len(hit_skills))
        reasons.append("技能：" + "、".join(hit_skills[:3]))
    if job.source == "official":
        score += 3
    smin = int(getattr(job, "salary_min", 0) or 0)
    smax = int(getattr(job, "salary_max", 0) or 0)
    want_min = constraints.salary_min if constraints else int(getattr(profile, "expected_salary_min", 0) or 0)
    want_max = constraints.salary_max if constraints else int(getattr(profile, "expected_salary_max", 0) or 0)
    if smin or smax:
        reasons.append(getattr(job, "salary_text", "") or f"{smin}-{smax}K")
    elif want_min or want_max:
        score -= 6
        reasons.append("未标注薪资，需打开原链接核对")
    score = max(0, min(100, score))
    if not reasons:
        reasons.append("来自公开校招入口，建议打开原链接核对岗位方向")
    return score, "；".join(reasons)


def to_out(
    job: Job,
    *,
    profile: Profile | None,
    keywords: str = "",
    favorited: bool = False,
    score: int | None = None,
    reason: str | None = None,
    constraints: Constraints | None = None,
    db: Session | None = None,
) -> JobOut:
    job_type = classify_job_type(job.title, job.description, job.tags, job.job_type)
    smin = int(getattr(job, "salary_min", 0) or 0)
    smax = int(getattr(job, "salary_max", 0) or 0)
    stext = getattr(job, "salary_text", "") or ""
    if not smin and not smax:
        smin, smax, parsed = parse_salary(f"{job.title} {job.description}")
        stext = stext or parsed
    if profile and score is None:
        score, reason = heuristic_score(profile, job, keywords, constraints)
    apply_url, official_url = resolve_company_links(job.company, job.apply_url, job.official_url)
    search_key = " ".join(
        part
        for part in [
            keywords,
            profile.expected_role if profile else "",
            job_type,
        ]
        if part
    ) or job.title
    city = (constraints.city if constraints else "") or (profile.expected_city if profile else "") or job.city
    role = keywords or (profile.expected_role if profile else "")
    return JobOut(
        id=job.id,
        title=job.title,
        company=job.company,
        city=job.city,
        job_type=job_type,
        source=job.source,
        apply_url=apply_url,
        official_url=official_url,
        description=job.description,
        tags=_merged_tags(job),
        company_info=job.company_info,
        salary_min=smin,
        salary_max=smax,
        salary_text=stext,
        fetched_at=job.fetched_at,
        match_score=score,
        match_reason=reason,
        boss_search_url=boss_search_url(search_key, city.split("/")[0].strip() if city else ""),
        favorited=favorited,
        experience_posts=list_experiences_for(db, job.company) if db is not None else [],
        nowcoder_experience_url=nowcoder_experience_url(job.company, role),
        zhihu_experience_url=zhihu_experience_url(job.company, role),
    )


def list_jobs(
    db: Session,
    q: str = "",
    city: str = "",
    source: str = "",
    job_type: str = "",
    salary_min: int = 0,
    salary_max: int = 0,
) -> list[Job]:
    rows = list(db.scalars(select(Job)))
    city_n = city.lower().strip()
    source_n = source.strip()
    intern_search = (job_type or "").strip() == "实习"
    filtered: list[Job] = []
    for job in rows:
        hay = f"{job.title} {job.company} {job.city} {job.description} {job.tags}".lower()
        effective_type = classify_job_type(job.title, job.description, job.tags, job.job_type)
        if not type_allowed(effective_type, job_type):
            continue
        smin = int(getattr(job, "salary_min", 0) or 0)
        smax = int(getattr(job, "salary_max", 0) or 0)
        if not smin and not smax:
            smin, smax, stext = parse_salary(f"{job.title} {job.description}")
            job.salary_min, job.salary_max = smin, smax
            if stext:
                job.salary_text = stext
        if not intern_search and not salary_overlap(smin, smax, salary_min, salary_max):
            continue
        if city_n and city_n not in (job.city or "").lower() and city_n not in hay:
            continue
        if source_n and job.source != source_n:
            continue
        filtered.append(job)
    return filtered


def favorite_job_ids(db: Session) -> set[str]:
    ids = db.scalars(select(Favorite.job_id).where(Favorite.job_id.is_not(None))).all()
    return {i for i in ids if i}


def rank_jobs(
    db: Session,
    profile: Profile,
    jobs: list[Job],
    keywords: str,
    constraints: Constraints | None = None,
    use_llm: bool = True,
) -> list[JobOut]:
    favs = favorite_job_ids(db)
    payload = [
        {
            "id": job.id,
            "title": job.title,
            "company": job.company,
            "city": job.city,
            "job_type": classify_job_type(job.title, job.description, job.tags, job.job_type),
            "salary": getattr(job, "salary_text", "") or "",
            "description": job.description,
        }
        for job in jobs
    ]
    llm_ranks = rank_with_llm(profile, payload, keywords) if use_llm else {}
    outs: list[JobOut] = []
    for job in jobs:
        h_score, h_reason = heuristic_score(profile, job, keywords, constraints)
        extra = llm_ranks.get(job.id)
        if extra:
            score = round(0.4 * int(extra["score"]) + 0.6 * h_score)
            reason = extra.get("reason") or h_reason
        else:
            score, reason = h_score, h_reason
        outs.append(
            to_out(
                job,
                profile=profile,
                keywords=keywords,
                favorited=job.id in favs,
                score=max(0, min(100, score)),
                reason=reason,
                constraints=constraints,
                db=db,
            )
        )
    outs.sort(key=lambda item: item.match_score or 0, reverse=True)
    return outs
