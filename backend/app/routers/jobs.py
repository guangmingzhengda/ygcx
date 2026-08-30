from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Job
from app.schemas import JobOut
from app.services.filters import constraints_from_profile
from app.services.experiences import experience_cache_is_stale, refresh_experiences
from app.services.jobs import cache_is_stale, favorite_job_ids, list_jobs, rank_jobs, refresh_jobs, to_out
from app.services.profile import get_or_create_profile

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/search", response_model=list[JobOut])
async def search_jobs(
    q: str = "",
    city: str = "",
    source: str = "",
    job_type: str = "",
    salary_min: int = Query(0),
    salary_max: int = Query(0),
    refresh: bool = Query(False),
    db: Session = Depends(get_db),
) -> list[JobOut]:
    profile = get_or_create_profile(db)
    if refresh or cache_is_stale(db):
        await refresh_jobs(db)
    elif experience_cache_is_stale(db):
        await refresh_experiences(db)
    base = constraints_from_profile(profile)
    use_type = job_type or base.job_type
    use_city = city or base.city
    use_min = salary_min or base.salary_min
    use_max = salary_max or base.salary_max
    use_q = q or base.keywords
    jobs = list_jobs(
        db,
        q=use_q,
        city=use_city,
        source=source,
        job_type=use_type,
        salary_min=use_min,
        salary_max=use_max,
    )
    plan = base
    plan.keywords, plan.city, plan.job_type = use_q, use_city, use_type
    plan.salary_min, plan.salary_max = use_min, use_max
    return rank_jobs(db, profile, jobs, use_q, constraints=plan, use_llm=False)


@router.post("/refresh", response_model=list[JobOut])
async def refresh(db: Session = Depends(get_db)) -> list[JobOut]:
    profile = get_or_create_profile(db)
    await refresh_jobs(db)
    base = constraints_from_profile(profile)
    jobs = list_jobs(
        db,
        q=base.keywords,
        city=base.city,
        job_type=base.job_type,
        salary_min=base.salary_min,
        salary_max=base.salary_max,
    )
    return rank_jobs(db, profile, jobs, base.keywords, constraints=base, use_llm=False)


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: str, db: Session = Depends(get_db)) -> JobOut:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="职位不存在")
    profile = get_or_create_profile(db)
    return to_out(job, profile=profile, favorited=job.id in favorite_job_ids(db), db=db)
