from datetime import datetime

from pydantic import BaseModel, Field


class ProfileIn(BaseModel):
    education: str = "本科"
    graduation_year: int = 2027
    major: str = ""
    expected_job_type: str = "校招全职"
    expected_role: str = ""
    expected_city: str = ""
    skills: str = ""
    self_intro: str = ""
    expected_salary_min: int = 0
    expected_salary_max: int = 0


class ProfileOut(ProfileIn):
    updated_at: datetime | None = None


class ExperiencePostOut(BaseModel):
    title: str
    url: str
    source: str = "nowcoder"


class ExperienceSearchLink(BaseModel):
    label: str
    url: str
    source: str = ""


class JobOut(BaseModel):
    id: str
    title: str
    company: str = ""
    city: str = ""
    job_type: str = "校招"
    source: str = "official"
    apply_url: str = ""
    official_url: str = ""
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    company_info: str = ""
    salary_min: int = 0
    salary_max: int = 0
    salary_text: str = ""
    fetched_at: datetime | None = None
    match_score: int | None = None
    match_reason: str | None = None
    boss_search_url: str = ""
    favorited: bool = False
    experience_posts: list[ExperiencePostOut] = Field(default_factory=list)
    experience_search_links: list[ExperienceSearchLink] = Field(default_factory=list)
    nowcoder_experience_url: str = ""
    zhihu_experience_url: str = ""


class FavoriteIn(BaseModel):
    job_id: str | None = None
    title: str = ""
    url: str = ""
    kind: str = "job"
    note: str = ""


class FavoriteOut(BaseModel):
    id: int
    job_id: str | None = None
    title: str
    url: str
    kind: str
    note: str = ""
    created_at: datetime | None = None
    job: JobOut | None = None


class BossLinkIn(BaseModel):
    url: str
    note: str = ""


class ChatIn(BaseModel):
    message: str
    conversation_id: str | None = None
    refresh: bool = False


class ChatMessageOut(BaseModel):
    id: int
    role: str
    content: str
    jobs: list[JobOut] = Field(default_factory=list)
    created_at: datetime | None = None


class ConversationSummary(BaseModel):
    id: str
    title: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
    preview: str = ""


class ConversationOut(BaseModel):
    id: str
    title: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
    messages: list[ChatMessageOut] = Field(default_factory=list)


class ChatOut(BaseModel):
    conversation_id: str
    assistant: str
    jobs: list[JobOut] = Field(default_factory=list)
    conversation: ConversationOut
