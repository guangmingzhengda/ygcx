from __future__ import annotations

import json
import logging
import re

from openai import OpenAI

from app.config import settings
from app.models import Profile

logger = logging.getLogger(__name__)


def llm_enabled() -> bool:
    return bool(settings.llm_api_key.strip())


def _client() -> OpenAI:
    return OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)


def _complete(system: str, user: str) -> str:
    client = _client()
    response = client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.3,
    )
    return (response.choices[0].message.content or "").strip()


def _extract_json(text: str) -> dict | list | None:
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fenced:
        text = fenced.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                return None
    return None


def profile_brief(profile: Profile) -> str:
    return (
        f"学历:{profile.education}; 毕业:{profile.graduation_year}; 专业:{profile.major}; "
        f"期望类型:{profile.expected_job_type}; 期望岗位:{profile.expected_role}; "
        f"城市:{profile.expected_city}; 技能:{profile.skills}; 简介:{profile.self_intro}"
    )


def plan_search(profile: Profile, message: str) -> dict:
    fallback_keywords = " ".join(
        part
        for part in [
            profile.expected_role,
            profile.expected_city,
            profile.major,
            "校招",
        ]
        if part
    ).strip() or "校招"
    fallback = {
        "reply": f"已根据你的档案检索「{fallback_keywords}」相关校招信息。",
        "keywords": fallback_keywords,
        "city": profile.expected_city or "",
    }
    if not llm_enabled():
        if message.strip():
            fallback["keywords"] = f"{message.strip()} {fallback_keywords}".strip()
            fallback["reply"] = (
                f"当前未配置大模型，已用关键词匹配检索「{fallback['keywords']}」。"
                "在 .env 中填写 LLM_API_KEY 后可获得匹配理由。"
            )
        return fallback
    try:
        raw = _complete(
            "你是面向应届生的校招助手。只输出 JSON，不要 Markdown。"
            "字段: reply(中文回复), keywords(检索词), city(城市，可空)。",
            f"学生档案: {profile_brief(profile)}\n用户问题: {message}",
        )
        data = _extract_json(raw)
        if not isinstance(data, dict):
            return fallback
        return {
            "reply": str(data.get("reply") or fallback["reply"]),
            "keywords": str(data.get("keywords") or fallback["keywords"]),
            "city": str(data.get("city") or fallback["city"]),
        }
    except Exception:
        logger.warning("plan_search llm failed", exc_info=True)
        return fallback


def rank_with_llm(profile: Profile, jobs: list[dict], keywords: str) -> dict[str, dict]:
    """返回 {job_id: {score, reason}}。失败时为空 dict。"""
    if not llm_enabled() or not jobs:
        return {}
    payload = [
        {
            "id": job["id"],
            "title": job["title"],
            "company": job["company"],
            "city": job["city"],
            "description": (job.get("description") or "")[:180],
        }
        for job in jobs[:18]
    ]
    try:
        raw = _complete(
            "根据学生档案给校招职位打分。只输出 JSON 数组，"
            '每项: {"id": "...", "score": 0-100 整数, "reason": "一两句中文"}。',
            f"档案: {profile_brief(profile)}\n检索词: {keywords}\n职位: {json.dumps(payload, ensure_ascii=False)}",
        )
        data = _extract_json(raw)
        if isinstance(data, dict) and "items" in data:
            data = data["items"]
        if not isinstance(data, list):
            return {}
        result: dict[str, dict] = {}
        for item in data:
            if not isinstance(item, dict) or "id" not in item:
                continue
            try:
                score = int(item.get("score") or 0)
            except (TypeError, ValueError):
                score = 0
            result[str(item["id"])] = {
                "score": max(0, min(100, score)),
                "reason": str(item.get("reason") or ""),
            }
        return result
    except Exception:
        logger.warning("rank_with_llm failed", exc_info=True)
        return {}
