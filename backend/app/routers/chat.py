from __future__ import annotations

import json
import logging
from types import SimpleNamespace

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db import SessionLocal, get_db
from app.schemas import ChatIn, ChatOut, ConversationOut, ConversationSummary, JobOut
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
from app.services.llm import analyze_jobs, analyze_jobs_stream, llm_enabled, plan_search
from app.services.profile import get_or_create_profile

router = APIRouter(tags=["chat"])
logger = logging.getLogger(__name__)


def _profile_view(profile) -> SimpleNamespace:
    return SimpleNamespace(
        education=profile.education,
        graduation_year=profile.graduation_year,
        major=profile.major,
        expected_job_type=profile.expected_job_type,
        expected_role=profile.expected_role,
        expected_city=profile.expected_city,
        expected_salary_min=getattr(profile, "expected_salary_min", 0),
        expected_salary_max=getattr(profile, "expected_salary_max", 0),
        skills=profile.skills,
        self_intro=profile.self_intro,
    )


def _jobs_payload(jobs: list[JobOut]) -> list[dict]:
    return [
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
        for item in jobs
    ]


def _apply_ranks(ranked: list[JobOut], llm_ranks: dict[str, dict]) -> list[JobOut]:
    if not llm_ranks:
        return ranked
    merged: list[JobOut] = []
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
    return merged


def _compose_reply(
    *,
    ranked: list[JobOut],
    analysis: str,
    relaxed: bool,
    plan_reply: str,
    plan_desc: str,
) -> str:
    if ranked:
        if analysis:
            note = "\n\n（城市/薪资硬条件已放宽，低匹配度也会列出。）" if relaxed else ""
            return analysis + note
        if llm_enabled():
            return (
                "大模型当前繁忙或暂时不可用，这次先用规则排序，点评会比较短。稍后再问一次会重新分析。\n"
                + (plan_reply or f"已按「{plan_desc}」列出结果。")
            )
        return plan_reply or f"已按「{plan_desc}」排序，匹配度低的也会列出。"
    return f"按「{plan_desc}」库里暂时没有职位可展示。请先点职位发现里的「刷新数据源」，或稍后再试。"


async def _prepare_chat(payload: ChatIn, db: Session):
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
    return profile, plan, ranked, relaxed


@router.post("/chat", response_model=ChatOut)
async def chat(payload: ChatIn, db: Session = Depends(get_db)) -> ChatOut:
    profile, plan, ranked, relaxed = await _prepare_chat(payload, db)
    analysis, llm_ranks = analyze_jobs(profile, payload.message, _jobs_payload(ranked))
    ranked = _apply_ranks(ranked, llm_ranks)
    plan.reply = _compose_reply(
        ranked=ranked,
        analysis=analysis,
        relaxed=relaxed,
        plan_reply=plan.reply,
        plan_desc=describe_constraints(plan),
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


@router.post("/chat/stream")
async def chat_stream(payload: ChatIn, db: Session = Depends(get_db)) -> StreamingResponse:
    profile, plan, ranked, relaxed = await _prepare_chat(payload, db)
    conv = get_or_create_conversation(db, payload.conversation_id, payload.message)
    add_message(db, conv, "user", payload.message)
    conv_id = conv.id
    profile_view = _profile_view(profile)
    plan_reply = plan.reply
    plan_desc = describe_constraints(plan)
    question = payload.message
    start_jobs = [item.model_dump(mode="json") for item in ranked]

    def sse(event: dict) -> str:
        return f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"

    def generate():
        yield sse({"type": "start", "conversation_id": conv_id, "jobs": start_jobs})
        analysis = ""
        llm_ranks: dict[str, dict] = {}
        streamed = False
        final_jobs = ranked
        reply = ""
        try:
            if ranked and llm_enabled():
                try:
                    for kind, item in analyze_jobs_stream(profile_view, question, _jobs_payload(ranked)):
                        if kind == "delta":
                            streamed = True
                            yield sse({"type": "delta", "text": item})
                        elif kind == "result":
                            analysis, llm_ranks = item
                except Exception:
                    logger.exception("analyze_jobs_stream failed")
                    analysis, llm_ranks = "", {}
            final_jobs = _apply_ranks(ranked, llm_ranks)
            reply = _compose_reply(
                ranked=final_jobs,
                analysis=analysis,
                relaxed=relaxed,
                plan_reply=plan_reply,
                plan_desc=plan_desc,
            )
            if streamed and relaxed and analysis and reply.startswith(analysis):
                extra = reply[len(analysis) :]
                if extra:
                    yield sse({"type": "delta", "text": extra})
            elif not streamed and reply:
                yield sse({"type": "delta", "text": reply})
            if llm_ranks:
                yield sse({"type": "jobs", "jobs": [item.model_dump(mode="json") for item in final_jobs]})
            session = SessionLocal()
            try:
                conv_row = get_conversation(session, conv_id)
                if conv_row:
                    add_message(session, conv_row, "assistant", reply, final_jobs)
            finally:
                session.close()
        except Exception:
            logger.exception("chat stream failed")
            if not reply:
                reply = "生成时出错了，请再试一次。"
                yield sse({"type": "delta", "text": reply})
        yield sse(
            {
                "type": "done",
                "conversation_id": conv_id,
                "assistant": reply,
                "jobs": [item.model_dump(mode="json") for item in final_jobs],
            }
        )

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
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
