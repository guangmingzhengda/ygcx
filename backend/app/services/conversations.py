from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Conversation, Message
from app.schemas import ChatMessageOut, ConversationOut, ConversationSummary, JobOut


def new_id() -> str:
    return uuid.uuid4().hex[:16]


def list_conversations(db: Session) -> list[ConversationSummary]:
    rows = db.scalars(select(Conversation).order_by(Conversation.updated_at.desc())).all()
    out: list[ConversationSummary] = []
    for conv in rows:
        last = db.scalars(
            select(Message).where(Message.conversation_id == conv.id).order_by(Message.id.desc())
        ).first()
        out.append(
            ConversationSummary(
                id=conv.id,
                title=conv.title,
                created_at=conv.created_at,
                updated_at=conv.updated_at,
                preview=(last.content[:80] if last else ""),
            )
        )
    return out


def get_conversation(db: Session, cid: str) -> Conversation | None:
    return db.scalar(
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(Conversation.id == cid)
    )


def jobs_from_json(raw: str) -> list[JobOut]:
    try:
        data = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    jobs: list[JobOut] = []
    for item in data:
        try:
            jobs.append(JobOut.model_validate(item))
        except Exception:
            continue
    return jobs


def to_conversation_out(conv: Conversation) -> ConversationOut:
    messages = [
        ChatMessageOut(
            id=msg.id,
            role=msg.role,
            content=msg.content,
            jobs=jobs_from_json(msg.jobs_json),
            created_at=msg.created_at,
        )
        for msg in conv.messages
    ]
    return ConversationOut(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        messages=messages,
    )


def get_or_create_conversation(db: Session, cid: str | None, title: str) -> Conversation:
    if cid:
        existing = get_conversation(db, cid)
        if existing:
            return existing
    conv = Conversation(id=new_id(), title=title[:40] or "新对话")
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return get_conversation(db, conv.id) or conv


def add_message(
    db: Session,
    conv: Conversation,
    role: str,
    content: str,
    jobs: list[JobOut] | None = None,
) -> Message:
    msg = Message(
        conversation_id=conv.id,
        role=role,
        content=content,
        jobs_json=json.dumps(
            [job.model_dump(mode="json") for job in (jobs or [])],
            ensure_ascii=False,
            default=str,
        ),
    )
    conv.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    if conv.title in {"新对话", ""} and role == "user":
        conv.title = content.strip()[:32] or "新对话"
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


def delete_conversation(db: Session, cid: str) -> bool:
    conv = db.get(Conversation, cid)
    if not conv:
        return False
    db.delete(conv)
    db.commit()
    return True
