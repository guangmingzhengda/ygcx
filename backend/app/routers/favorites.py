from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.models import Favorite, Job
from app.schemas import BossLinkIn, FavoriteIn, FavoriteOut, JobOut
from app.services.adapters.boss import is_boss_public_url
from app.services.jobs import favorite_job_ids, to_out
from app.services.profile import get_or_create_profile

router = APIRouter(prefix="/favorites", tags=["favorites"])


def _to_out(fav: Favorite, profile, fav_ids: set[str], db: Session | None = None) -> FavoriteOut:
    job_out: JobOut | None = None
    if fav.job:
        job_out = to_out(fav.job, profile=profile, favorited=fav.job.id in fav_ids, db=db)
    return FavoriteOut(
        id=fav.id,
        job_id=fav.job_id,
        title=fav.title,
        url=fav.url,
        kind=fav.kind,
        note=fav.note,
        created_at=fav.created_at,
        job=job_out,
    )


@router.get("", response_model=list[FavoriteOut])
def list_favorites(db: Session = Depends(get_db)) -> list[FavoriteOut]:
    rows = db.scalars(
        select(Favorite).options(selectinload(Favorite.job)).order_by(Favorite.created_at.desc())
    ).all()
    profile = get_or_create_profile(db)
    fav_ids = favorite_job_ids(db)
    return [_to_out(row, profile, fav_ids, db) for row in rows]


@router.post("", response_model=FavoriteOut)
def add_favorite(payload: FavoriteIn, db: Session = Depends(get_db)) -> FavoriteOut:
    title = payload.title
    url = payload.url
    kind = payload.kind or "job"
    if payload.job_id:
        job = db.get(Job, payload.job_id)
        if not job:
            raise HTTPException(status_code=404, detail="职位不存在")
        existing = db.scalar(select(Favorite).where(Favorite.job_id == job.id))
        if existing:
            existing = db.scalar(
                select(Favorite).options(selectinload(Favorite.job)).where(Favorite.id == existing.id)
            ) or existing
            profile = get_or_create_profile(db)
            return _to_out(existing, profile, favorite_job_ids(db), db)
        title = title or job.title
        url = url or job.apply_url or job.official_url
        kind = "job"
        fav = Favorite(job_id=job.id, title=title, url=url, kind=kind, note=payload.note)
    else:
        if not url:
            raise HTTPException(status_code=400, detail="请提供链接或职位")
        fav = Favorite(job_id=None, title=title or url, url=url, kind=kind, note=payload.note)
    db.add(fav)
    db.commit()
    db.refresh(fav)
    if fav.job_id:
        loaded = db.scalar(select(Favorite).options(selectinload(Favorite.job)).where(Favorite.id == fav.id))
        if loaded is not None:
            fav = loaded
    profile = get_or_create_profile(db)
    return _to_out(fav, profile, favorite_job_ids(db), db)


@router.delete("/by-job/{job_id}")
def remove_favorite_by_job(job_id: str, db: Session = Depends(get_db)) -> dict:
    fav = db.scalar(select(Favorite).where(Favorite.job_id == job_id))
    if not fav:
        raise HTTPException(status_code=404, detail="收藏不存在")
    db.delete(fav)
    db.commit()
    return {"ok": True}


@router.delete("/{fav_id}")
def remove_favorite(fav_id: int, db: Session = Depends(get_db)) -> dict:
    fav = db.get(Favorite, fav_id)
    if not fav:
        raise HTTPException(status_code=404, detail="收藏不存在")
    db.delete(fav)
    db.commit()
    return {"ok": True}


@router.post("/boss-link", response_model=FavoriteOut)
def save_boss_link(payload: BossLinkIn, db: Session = Depends(get_db)) -> FavoriteOut:
    url = payload.url.strip()
    if not is_boss_public_url(url):
        raise HTTPException(status_code=400, detail="请粘贴 Boss 直聘公开分享链接（zhipin.com）")
    fav = Favorite(
        title="Boss 直聘分享",
        url=url,
        kind="boss",
        note=payload.note,
    )
    db.add(fav)
    db.commit()
    db.refresh(fav)
    profile = get_or_create_profile(db)
    return _to_out(fav, profile, favorite_job_ids(db), db)
