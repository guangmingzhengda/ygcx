from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    education: Mapped[str] = mapped_column(String(32), default="本科")
    graduation_year: Mapped[int] = mapped_column(Integer, default=2027)
    major: Mapped[str] = mapped_column(String(128), default="")
    expected_job_type: Mapped[str] = mapped_column(String(32), default="校招全职")
    expected_role: Mapped[str] = mapped_column(String(128), default="")
    expected_city: Mapped[str] = mapped_column(String(64), default="")
    skills: Mapped[str] = mapped_column(Text, default="")
    self_intro: Mapped[str] = mapped_column(Text, default="")
    expected_salary_min: Mapped[int] = mapped_column(Integer, default=0)
    expected_salary_max: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    title: Mapped[str] = mapped_column(String(256))
    company: Mapped[str] = mapped_column(String(128), default="")
    city: Mapped[str] = mapped_column(String(128), default="")
    job_type: Mapped[str] = mapped_column(String(32), default="校招")
    source: Mapped[str] = mapped_column(String(32), default="official")
    apply_url: Mapped[str] = mapped_column(Text, default="")
    official_url: Mapped[str] = mapped_column(Text, default="")
    description: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[str] = mapped_column(Text, default="[]")
    company_info: Mapped[str] = mapped_column(Text, default="")
    salary_min: Mapped[int] = mapped_column(Integer, default=0)
    salary_max: Mapped[int] = mapped_column(Integer, default=0)
    salary_text: Mapped[str] = mapped_column(String(64), default="")
    fetched_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Experience(Base):
    __tablename__ = "experiences"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    title: Mapped[str] = mapped_column(String(256), default="")
    url: Mapped[str] = mapped_column(Text, default="")
    company: Mapped[str] = mapped_column(String(128), default="")
    source: Mapped[str] = mapped_column(String(32), default="nowcoder")
    fetched_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Favorite(Base):
    __tablename__ = "favorites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("jobs.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(256), default="")
    url: Mapped[str] = mapped_column(Text, default="")
    kind: Mapped[str] = mapped_column(String(32), default="job")
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    job: Mapped[Job | None] = relationship()


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    title: Mapped[str] = mapped_column(String(256), default="新对话")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.id",
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(String(32), ForeignKey("conversations.id"))
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text, default="")
    jobs_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    conversation: Mapped[Conversation] = relationship(back_populates="messages")
