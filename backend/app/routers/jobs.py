from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Job
from app.schemas import JobOut
from app.services.jobs import cache_is_stale, list_jobs, rank_jobs, refresh_jobs, to_out
from app.services.jobs import favorite_job_ids
from app.services.profile import get_or_create_profile

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/search", response_model=list[JobOut])
async def search_jobs(
    q: str = "",
    city: str = "",
    source: str = "",
    refresh: bool = Query(False),
    db: Session = Depends(get_db),
) -> list[JobOut]:
    profile = get_or_create_profile(db)
    if refresh or cache_is_stale(db):
        await refresh_jobs(db)
    keywords = " ".join(part for part in [q, profile.expected_role, profile.expected_city] if part)
    jobs = list_jobs(db, q=q or profile.expected_role, city=city or profile.expected_city, source=source)
    return rank_jobs(db, profile, jobs, keywords)


@router.post("/refresh", response_model=list[JobOut])
async def refresh(db: Session = Depends(get_db)) -> list[JobOut]:
    profile = get_or_create_profile(db)
    await refresh_jobs(db)
    jobs = list_jobs(db)
    keywords = " ".join(part for part in [profile.expected_role, profile.expected_city] if part)
    return rank_jobs(db, profile, jobs, keywords)


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: str, db: Session = Depends(get_db)) -> JobOut:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="职位不存在")
    profile = get_or_create_profile(db)
    return to_out(job, profile=profile, favorited=job.id in favorite_job_ids(db))
