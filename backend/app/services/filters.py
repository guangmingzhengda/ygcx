from __future__ import annotations

import re
from dataclasses import dataclass

from app.models import Profile

SOCIAL = re.compile(r"社招|社会招聘|社会招聘|experienced\s*hire", re.I)
INTERN = re.compile(r"实习|intern", re.I)
CAMPUS = re.compile(r"校招|校园招聘|应届|秋招|春招|提前批|campus|毕业生", re.I)

# 15-25k / 15k-25k / 15~25K / 1.5万-2.5万 / 15000-25000
RANGE_K = re.compile(
    r"(?P<a>\d+(?:\.\d+)?)\s*(?P<ua>[kKwW万千])?\s*[-~～—到至]\s*(?P<b>\d+(?:\.\d+)?)\s*(?P<ub>[kKwW万千])?",
)
ABOVE_K = re.compile(r"(?:不低于|高于|大于|以上|起)\s*(?P<a>\d+(?:\.\d+)?)\s*(?P<u>[kKwW万千])?")
ABOVE_K2 = re.compile(r"(?P<a>\d+(?:\.\d+)?)\s*(?P<u>[kKwW万千])\s*(?:以上|起)")
SINGLE_K = re.compile(r"(?:月薪|薪资|工资|待遇)\s*(?P<a>\d+(?:\.\d+)?)\s*(?P<u>[kKwW万千])")

STOPWORDS = {
    "的",
    "和",
    "与",
    "在",
    "找",
    "帮我",
    "相关",
    "职位",
    "岗位",
    "工作",
    "一下",
    "给我",
    "推荐",
    "有哪些",
    "限制",
    "要求",
    "期望",
}


def _to_k(num: float, unit: str | None) -> int:
    unit = (unit or "").lower()
    if unit in {"w", "万"}:
        return int(round(num * 10))
    if unit in {"千"}:
        return int(round(num))
    if unit in {"k"}:
        return int(round(num))
    if num >= 1000:
        return int(round(num / 1000))
    return int(round(num))


def parse_salary(text: str) -> tuple[int, int, str]:
    """从文本解析月薪（单位 K）。没有则 (0, 0, '')。"""
    raw = text or ""
    m = RANGE_K.search(raw)
    if m:
        ua, ub = m.group("ua"), m.group("ub")
        unit = ub or ua or "k"
        low = _to_k(float(m.group("a")), ua or unit)
        high = _to_k(float(m.group("b")), ub or unit)
        if low > high:
            low, high = high, low
        return low, high, m.group(0).replace(" ", "")
    m = ABOVE_K2.search(raw) or ABOVE_K.search(raw)
    if m:
        low = _to_k(float(m.group("a")), m.group("u"))
        return low, 0, m.group(0).replace(" ", "")
    m = SINGLE_K.search(raw)
    if m:
        val = _to_k(float(m.group("a")), m.group("u"))
        return max(val - 3, 0), val + 3, m.group(0).replace(" ", "")
    return 0, 0, ""


def classify_job_type(title: str, description: str = "", tags: str = "", fallback: str = "校招") -> str:
    blob = f"{title} {description} {tags}"
    if SOCIAL.search(blob):
        return "社招"
    if CAMPUS.search(blob):
        if INTERN.search(title) and not re.search(r"应届|校招|校园招聘", title):
            return "实习"
        return "校招"
    if INTERN.search(blob):
        return "实习"
    if re.search(r"招聘", blob):
        return "社招"
    return fallback or "校招"


def salary_overlap(job_min: int, job_max: int, want_min: int, want_max: int) -> bool:
    if want_min <= 0 and want_max <= 0:
        return True
    if job_min <= 0 and job_max <= 0:
        return True
    jmin = job_min or job_max
    jmax = job_max or job_min
    wmin = want_min if want_min > 0 else 0
    wmax = want_max if want_max > 0 else 10**9
    return jmax >= wmin and jmin <= wmax


def type_allowed(job_type: str, want: str) -> bool:
    want = (want or "").strip()
    job_type = (job_type or "").strip()
    if not want or want in {"不限", "全部"}:
        return True
    if job_type == "社招" and "社招" not in want:
        return False
    if want in {"校招全职", "校招"}:
        return job_type == "校招"
    if want == "实习":
        # 库里多为公司校招入口，实习岗往往也在这些页面里，不能整表丢掉
        return job_type in {"实习", "校招"}
    if "均可" in want or "校招全职 / 实习" in want:
        return job_type in {"校招", "实习"}
    if "社招" in want:
        return job_type == "社招"
    return job_type != "社招"


def keyword_tokens(q: str) -> list[str]:
    text = (q or "").strip()
    text = re.sub(r"\d+(?:\.\d+)?\s*[kKwW万千]?", " ", text)
    parts = re.split(r"[\s,，/|]+", text)
    out: list[str] = []
    for part in parts:
        token = part.strip().lower()
        if len(token) < 2 or token in STOPWORDS:
            continue
        if token in {"校招", "社招", "实习", "全职", "校园", "应届"}:
            continue
        out.append(token)
    return out


ROLE_HINTS: dict[str, list[str]] = {
    "后端": ["后端", "服务端", "server", "java", "golang", "go", "python", "研发", "开发", "工程", "软件"],
    "前端": ["前端", "web", "react", "vue", "客户端", "研发", "开发"],
    "客户端": ["客户端", "android", "ios", "鸿蒙", "终端"],
    "算法": ["算法", "机器学习", "深度学习", "ai", "大模型", "推荐", "智能"],
    "产品": ["产品", "pm"],
    "设计": ["设计", "ui", "ux", "视觉", "工业设计"],
    "测试": ["测试", "qa", "质量"],
    "数据": ["数据", "分析", "数仓", "数分"],
    "硬件": ["硬件", "电子", "嵌入式", "芯片", "通信"],
    "运营": ["运营", "市场", "增长"],
    "游戏": ["游戏", "引擎", "unity", "ue", "雷火"],
}


def expand_role_hints(text: str) -> list[str]:
    blob = (text or "").lower()
    hints: list[str] = []
    for key, words in ROLE_HINTS.items():
        if key in blob or any(word in blob for word in words if len(word) > 1):
            hints.append(key)
            hints.extend(words)
    hints.extend(keyword_tokens(text))
    seen: set[str] = set()
    ordered: list[str] = []
    for item in hints:
        token = item.lower().strip()
        if len(token) < 2 or token in seen:
            continue
        seen.add(token)
        ordered.append(token)
    return ordered


@dataclass
class Constraints:
    keywords: str = ""
    city: str = ""
    job_type: str = "校招"
    salary_min: int = 0
    salary_max: int = 0
    source: str = ""
    reply: str = ""


def constraints_from_profile(profile: Profile) -> Constraints:
    return Constraints(
        keywords=profile.expected_role or "",
        city=profile.expected_city or "",
        job_type=profile.expected_job_type or "校招",
        salary_min=int(getattr(profile, "expected_salary_min", 0) or 0),
        salary_max=int(getattr(profile, "expected_salary_max", 0) or 0),
    )


CITIES = (
    "北京",
    "上海",
    "广州",
    "深圳",
    "杭州",
    "南京",
    "成都",
    "武汉",
    "西安",
    "苏州",
    "长沙",
    "重庆",
    "天津",
    "合肥",
    "郑州",
    "青岛",
    "大连",
    "厦门",
    "珠海",
    "东莞",
    "佛山",
    "宁波",
    "无锡",
    "济南",
    "福州",
    "昆明",
    "南昌",
    "哈尔滨",
    "沈阳",
    "长春",
    "石家庄",
    "太原",
    "南宁",
    "海口",
    "贵阳",
    "兰州",
    "香港",
    "澳门",
)


def _city_from_text(blob: str) -> str:
    for city in CITIES:
        if city in blob:
            return city
    return ""


def constraints_from_message(message: str) -> Constraints:
    blob = message or ""
    job_type = ""
    if re.search(r"(不要|别|排除|不是|非)\s*社招", blob):
        job_type = "校招"
    elif re.search(r"社招|社会招聘", blob):
        job_type = "社招"
    elif re.search(r"实习", blob) and not re.search(r"校招|应届|校园", blob):
        job_type = "实习"
    elif re.search(r"校招|应届|校园|秋招|春招", blob):
        job_type = "校招"
    smin, smax, _ = parse_salary(blob)
    city = _city_from_text(blob)
    return Constraints(keywords=blob, city=city, job_type=job_type, salary_min=smin, salary_max=smax)


def merge_constraints(base: Constraints, *overrides: Constraints) -> Constraints:
    out = Constraints(
        keywords=base.keywords,
        city=base.city,
        job_type=base.job_type,
        salary_min=base.salary_min,
        salary_max=base.salary_max,
        source=base.source,
        reply=base.reply,
    )
    for item in overrides:
        if item.keywords.strip():
            out.keywords = item.keywords
        if item.city.strip():
            out.city = item.city
        if item.job_type.strip():
            out.job_type = item.job_type
        if item.salary_min > 0:
            out.salary_min = item.salary_min
        if item.salary_max > 0:
            out.salary_max = item.salary_max
        if item.source.strip():
            out.source = item.source
        if item.reply.strip():
            out.reply = item.reply
    return out


def describe_constraints(c: Constraints) -> str:
    bits = [c.job_type or "校招"]
    if c.city:
        bits.append(c.city)
    if c.salary_min or c.salary_max:
        if c.salary_min and c.salary_max:
            bits.append(f"{c.salary_min}-{c.salary_max}K")
        elif c.salary_min:
            bits.append(f"{c.salary_min}K 以上")
        else:
            bits.append(f"{c.salary_max}K 以内")
    if c.keywords:
        bits.append(c.keywords)
    return "、".join(bits)
