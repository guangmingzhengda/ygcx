from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import ChatIn, ChatOut, ConversationOut, ConversationSummary
from app.services.conversations import (
    add_message,
    delete_conversation,
    get_conversation,
    get_or_create_conversation,
    list_conversations,
    to_conversation_out,
)
from app.services.filters import describe_constraints
from app.services.jobs import cache_is_stale, list_jobs, rank_jobs, refresh_jobs
from app.services.llm import plan_search
from app.services.profile import get_or_create_profile

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatOut)
async def chat(payload: ChatIn, db: Session = Depends(get_db)) -> ChatOut:
    profile = get_or_create_profile(db)
    plan = plan_search(profile, payload.message)
    if payload.refresh or cache_is_stale(db):
        await refresh_jobs(db)
    jobs = list_jobs(
        db,
        q=plan.keywords,
        city=plan.city,
        job_type=plan.job_type,
        salary_min=plan.salary_min,
        salary_max=plan.salary_max,
    )
    ranked = rank_jobs(db, profile, jobs, plan.keywords, constraints=plan)[:12]
    if not ranked:
        plan.reply = (
            f"按「{describe_constraints(plan)}」没有筛到合适职位。"
            "社招已排除；未标注薪资的校招入口只有在类型匹配时才会保留。可以放宽薪资或城市再试。"
        )
    conv = get_or_create_conversation(db, payload.conversation_id, payload.message)
    add_message(db, conv, "user", payload.message)
    add_message(db, conv, "assistant", plan.reply, ranked)
    conv = get_conversation(db, conv.id) or conv
    return ChatOut(
        conversation_id=conv.id,
        assistant=plan.reply,
        jobs=ranked,
        conversation=to_conversation_out(conv),
    )


@router.get("/conversations", response_model=list[ConversationSummary])
def conversations(db: Session = Depends(get_db)) -> list[ConversationSummary]:
    return list_conversations(db)


@router.get("/conversations/{cid}", response_model=ConversationOut)
def conversation_detail(cid: str, db: Session = Depends(get_db)) -> ConversationOut:
    conv = get_conversation(db, cid)
    if not conv:
        raise HTTPException(status_code=404, detail="对话不存在")
    return to_conversation_out(conv)


@router.delete("/conversations/{cid}")
def conversation_delete(cid: str, db: Session = Depends(get_db)) -> dict:
    if not delete_conversation(db, cid):
        raise HTTPException(status_code=404, detail="对话不存在")
    return {"ok": True}
