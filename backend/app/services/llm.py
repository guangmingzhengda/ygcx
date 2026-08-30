from __future__ import annotations

import json
import logging
import re
import time

from openai import OpenAI, RateLimitError

from app.config import settings
from app.models import Profile
from app.services.filters import (
    Constraints,
    constraints_from_message,
    constraints_from_profile,
    describe_constraints,
    merge_constraints,
)

logger = logging.getLogger(__name__)


def llm_enabled() -> bool:
    return bool(settings.llm_api_key.strip())


def _client() -> OpenAI:
    return OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)


def _complete(system: str, user: str, *, max_tokens: int = 2500) -> str:
    client = _client()
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            response = client.chat.completions.create(
                model=settings.llm_model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0.4,
                max_tokens=max_tokens,
                extra_body={"thinking": {"type": "disabled"}},
            )
            message = response.choices[0].message
            text = (message.content or "").strip()
            if not text:
                text = (getattr(message, "reasoning_content", None) or "").strip()
            return text
        except RateLimitError as exc:
            last_error = exc
            logger.warning("llm rate limited, retry=%s", attempt)
            if attempt == 0:
                time.sleep(1.6)
                continue
            raise
    raise last_error or RuntimeError("llm failed")


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
        f"城市:{profile.expected_city}; 期望薪资K:{getattr(profile, 'expected_salary_min', 0)}-"
        f"{getattr(profile, 'expected_salary_max', 0)}; 技能:{profile.skills}; 简介:{profile.self_intro}"
    )


def _as_int(value: object) -> int:
    try:
        return int(float(str(value).replace("K", "").replace("k", "").strip() or 0))
    except (TypeError, ValueError):
        return 0


def plan_search(profile: Profile, message: str, *, use_llm: bool = False) -> Constraints:
    base = constraints_from_profile(profile)
    from_msg = constraints_from_message(message)
    fallback = merge_constraints(base, from_msg)
    fallback.reply = f"已按「{describe_constraints(fallback)}」筛选，社招已排除（除非你明确要社招）。未标注薪资的校招入口会保留，请打开原链接核对。"
    if message.strip() and not fallback.keywords:
        fallback.keywords = message.strip()
    if not use_llm or not llm_enabled():
        return fallback
    try:
        raw = _complete(
            "你是面向应届生的校招助手。只输出 JSON，不要 Markdown。"
            "字段: reply(中文), keywords(岗位关键词，不要写校招/薪资数字), city, "
            "job_type(校招|实习|社招|校招全职|不限), salary_min(月薪K整数,没有则0), salary_max(月薪K整数,没有则0)。"
            "用户要校招时 job_type 必须是校招或校招全职，不要推荐社招。"
            "用户要实习时 job_type 用实习；库里多为校招入口，不要为了纯实习把结果留空。",
            f"学生档案: {profile_brief(profile)}\n用户问题: {message}",
        )
        data = _extract_json(raw)
        if not isinstance(data, dict):
            return fallback
        llm_c = Constraints(
            keywords=str(data.get("keywords") or ""),
            city=str(data.get("city") or ""),
            job_type=str(data.get("job_type") or ""),
            salary_min=_as_int(data.get("salary_min")),
            salary_max=_as_int(data.get("salary_max")),
            reply=str(data.get("reply") or ""),
        )
        merged = merge_constraints(fallback, llm_c)
        if not merged.reply:
            merged.reply = fallback.reply
        return merged
    except Exception:
        logger.warning("plan_search llm failed", exc_info=True)
        return fallback


def analyze_jobs(profile: Profile, question: str, jobs: list[dict]) -> tuple[str, dict[str, dict]]:
    """一次调用：写点评段落 + 给卡片打分。失败返回 ('', {})。"""
    if not llm_enabled() or not jobs:
        return "", {}
    payload = [
        {
            "id": job.get("id"),
            "title": job.get("title"),
            "company": job.get("company"),
            "city": job.get("city"),
            "job_type": job.get("job_type") or "",
            "salary": job.get("salary") or "",
            "tags": job.get("tags") or [],
            "description": (job.get("description") or "")[:160],
        }
        for job in jobs[:12]
    ]
    try:
        raw = _complete(
            "你是面向应届生的校招顾问。只输出一个 JSON 对象，不要 Markdown。"
            "字段: reply(中文点评，180-320字，不要客套开头；点名2-4家更值得看的公司，"
            "说明和用户要的实习/岗位/城市差在哪；明确哪些只是校招入口、要自己点进去看实习和算法岗)，"
            'ranks(数组，每张卡一项: {"id","score"0-100整数,"reason"两句具体中文})。'
            "分数必须拉开。社招给 0 分。入口页最高 72 分。",
            f"档案: {profile_brief(profile)}\n用户问题: {question}\n职位: {json.dumps(payload, ensure_ascii=False)}",
        )
        data = _extract_json(raw)
        if not isinstance(data, dict):
            return "", {}
        reply = str(data.get("reply") or "").strip()
        ranks_raw = data.get("ranks") or data.get("items") or []
        if isinstance(ranks_raw, dict):
            ranks_raw = ranks_raw.get("items") or []
        result: dict[str, dict] = {}
        if isinstance(ranks_raw, list):
            for item in ranks_raw:
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
        return reply, result
    except Exception:
        logger.warning("analyze_jobs llm failed", exc_info=True)
        return "", {}


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
            "job_type": job.get("job_type") or "",
            "salary": job.get("salary") or "",
            "description": (job.get("description") or "")[:180],
        }
        for job in jobs[:18]
    ]
    try:
        raw = _complete(
            "根据学生档案给校招职位打分。社招必须给 0 分。只输出 JSON 数组。"
            "分数必须拉开：高度匹配 75-95，一般 45-70，弱相关 15-40，不要给一串相同分数。"
            "公司校招入口（没有具体岗位 JD）最高不超过 72。"
            '每项: {"id": "...", "score": 0-100 整数, "reason": "一两句中文，点名岗位/城市/是否只是入口页"}。',
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
