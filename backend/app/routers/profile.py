from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import ProfileIn, ProfileOut
from app.services.profile import get_or_create_profile, update_profile

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("", response_model=ProfileOut)
def read_profile(db: Session = Depends(get_db)) -> ProfileOut:
    profile = get_or_create_profile(db)
    return ProfileOut.model_validate(profile, from_attributes=True)


@router.put("", response_model=ProfileOut)
def save_profile(payload: ProfileIn, db: Session = Depends(get_db)) -> ProfileOut:
    profile = update_profile(db, payload)
    return ProfileOut.model_validate(profile, from_attributes=True)
