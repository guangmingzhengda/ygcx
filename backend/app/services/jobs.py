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
        existing.title = raw.title
        existing.company = raw.company
        existing.city = raw.city
        existing.job_type = raw.job_type
        existing.source = raw.source
        existing.apply_url = raw.apply_url
        existing.official_url = raw.official_url
        existing.description = raw.description
        existing.tags = _tags_dump(raw.tags)
        existing.company_info = raw.company_info
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
    return len(list(db.scalars(select(Job))))


def heuristic_score(profile: Profile, job: Job, keywords: str) -> tuple[int, str]:
    hay = " ".join(
        [
            job.title,
            job.company,
            job.city,
            job.description,
            job.company_info,
            " ".join(_tags_load(job.tags)),
        ]
    ).lower()
    score = 35
    reasons: list[str] = []
    city = (profile.expected_city or "").strip()
    role = (profile.expected_role or "").strip()
    major = (profile.major or "").strip()
    if city and city.lower() in hay:
        score += 22
        reasons.append(f"工作地/介绍中出现「{city}」")
    if role and role.lower() in hay:
        score += 22
        reasons.append(f"与期望岗位「{role}」相关")
    if major and major.lower() in hay:
        score += 10
        reasons.append(f"与专业「{major}」相关")
    for token in (keywords or "").split():
        if len(token) >= 2 and token.lower() in hay:
            score += 6
    skills = [s.strip() for s in (profile.skills or "").replace("，", ",").split(",") if s.strip()]
    hit_skills = [s for s in skills if s.lower() in hay]
    if hit_skills:
        score += min(12, 4 * len(hit_skills))
        reasons.append("技能关键词：" + "、".join(hit_skills[:3]))
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
) -> JobOut:
    if profile and score is None:
        score, reason = heuristic_score(profile, job, keywords)
    search_key = keywords or (profile.expected_role if profile else "") or job.title
    city = (profile.expected_city if profile else "") or job.city
    return JobOut(
        id=job.id,
        title=job.title,
        company=job.company,
        city=job.city,
        job_type=job.job_type,
        source=job.source,
        apply_url=job.apply_url,
        official_url=job.official_url,
        description=job.description,
        tags=_tags_load(job.tags),
        company_info=job.company_info,
        fetched_at=job.fetched_at,
        match_score=score,
        match_reason=reason,
        boss_search_url=boss_search_url(search_key, city.split("/")[0].strip() if city else ""),
        favorited=favorited,
    )


def list_jobs(db: Session, q: str = "", city: str = "", source: str = "") -> list[Job]:
    stmt = select(Job)
    rows = list(db.scalars(stmt))
    qn = q.lower().strip()
    city_n = city.lower().strip()
    source_n = source.strip()
    filtered: list[Job] = []
    for job in rows:
        hay = f"{job.title} {job.company} {job.city} {job.description} {job.tags}".lower()
        if qn and not all(token.lower() in hay for token in qn.split() if token):
            # 宽松：任一关键词命中即可
            if not any(token.lower() in hay for token in qn.split() if token):
                continue
        if city_n and city_n not in (job.city or "").lower() and city_n not in hay:
            continue
        if source_n and job.source != source_n:
            continue
        filtered.append(job)
    return filtered or rows


def favorite_job_ids(db: Session) -> set[str]:
    ids = db.scalars(select(Favorite.job_id).where(Favorite.job_id.is_not(None))).all()
    return {i for i in ids if i}


def rank_jobs(db: Session, profile: Profile, jobs: list[Job], keywords: str) -> list[JobOut]:
    favs = favorite_job_ids(db)
    payload = [
        {
            "id": job.id,
            "title": job.title,
            "company": job.company,
            "city": job.city,
            "description": job.description,
        }
        for job in jobs
    ]
    llm_ranks = rank_with_llm(profile, payload, keywords)
    outs: list[JobOut] = []
    for job in jobs:
        extra = llm_ranks.get(job.id)
        score = extra["score"] if extra else None
        reason = extra["reason"] if extra else None
        outs.append(
            to_out(
                job,
                profile=profile,
                keywords=keywords,
                favorited=job.id in favs,
                score=score,
                reason=reason,
            )
        )
    outs.sort(key=lambda item: item.match_score or 0, reverse=True)
    return outs
