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
from app.services.llm import analyze_jobs, llm_enabled, plan_search
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
    relaxed = False
    if not jobs:
        jobs = list_jobs(db, q=plan.keywords, job_type="校招全职 / 实习均可")
        relaxed = True
    ranked = rank_jobs(db, profile, jobs, plan.keywords, constraints=plan, use_llm=False)[:12]
    analysis, llm_ranks = analyze_jobs(
        profile,
        payload.message,
        [
            {
                "id": item.id,
                "title": item.title,
                "company": item.company,
                "city": item.city,
                "job_type": item.job_type,
                "salary": item.salary_text,
                "tags": item.tags,
                "description": item.description,
            }
            for item in ranked
        ],
    )
    if llm_ranks:
        merged = []
        for item in ranked:
            extra = llm_ranks.get(item.id)
            if extra:
                h = item.match_score or 0
                item = item.model_copy(
                    update={
                        "match_score": max(0, min(100, round(0.5 * int(extra["score"]) + 0.5 * h))),
                        "match_reason": extra.get("reason") or item.match_reason,
                    }
                )
            merged.append(item)
        merged.sort(key=lambda row: row.match_score or 0, reverse=True)
        ranked = merged
    if ranked:
        if analysis:
            note = ""
            if relaxed:
                note = "\n\n（城市/薪资硬条件已放宽，低匹配度也会列出。）"
            plan.reply = analysis + note
        elif llm_enabled():
            plan.reply = (
                "大模型当前繁忙或暂时不可用，这次先用规则排序，点评会比较短。稍后再问一次会重新分析。\n"
                + (plan.reply or f"已按「{describe_constraints(plan)}」列出结果。")
            )
        elif not plan.reply:
            plan.reply = f"已按「{describe_constraints(plan)}」排序，匹配度低的也会列出。"
    else:
        plan.reply = (
            f"按「{describe_constraints(plan)}」库里暂时没有职位可展示。"
            "请先点职位发现里的「刷新数据源」，或稍后再试。"
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
