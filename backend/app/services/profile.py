from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Profile
from app.schemas import ProfileIn


def get_or_create_profile(db: Session) -> Profile:
    profile = db.get(Profile, 1)
    if profile is None:
        profile = Profile(
            id=1,
            education="本科",
            graduation_year=datetime.now().year + 1,
            major="",
            expected_job_type="校招全职",
            expected_role="",
            expected_city="",
            skills="",
            self_intro="",
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


def update_profile(db: Session, data: ProfileIn) -> Profile:
    profile = get_or_create_profile(db)
    for key, value in data.model_dump().items():
        setattr(profile, key, value)
    db.commit()
    db.refresh(profile)
    return profile
