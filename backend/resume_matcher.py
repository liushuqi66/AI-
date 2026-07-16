"""Module 3: Resume Scoring & Job Matching

Computes a multi-dimensional compatibility score between a resume
and a job description using AI (when configured) or keyword-based
fallback matching.

Public API:
    match_resume_to_job(resume_info, job_description) -> dict
    extract_job_keywords(job_description) -> list[str]

Scoring Dimensions (total 100 points):
    - Skill Match (0-40): Technology stack and tool alignment
    - Experience Relevance (0-30): Work years and role fit
    - Education Match (0-15): Degree level alignment
    - Project Match (0-15): Project experience relevance
"""

import json
import logging
import re
from typing import Any, Dict, List

from config import config
from utils import call_ai, sanitize_ai_json

logger = logging.getLogger(__name__)


# ── Prompt Templates ───────────────────────────────────────

_MATCHING_SYSTEM_PROMPT = (
    "你是一个专业的招聘匹配分析专家。"
    "请严格按照 JSON 格式返回评分结果，不要添加任何解释或 markdown 标记。"
)

_MATCHING_USER_PROMPT = """请根据以下简历信息和岗位需求，进行精准的匹配度分析。

## 评分维度（满分 100 分）：
1. 技能匹配度（0-40分）：简历中的技能与岗位要求的技术栈、工具的匹配程度
2. 工作经验相关性（0-30分）：工作年限、过往经验与岗位的相关程度
3. 学历匹配度（0-15分）：学历背景是否符合岗位要求
4. 项目经验匹配度（0-15分）：项目经历与岗位需求的契合度

## 简历信息：
{resume_info}

## 岗位需求：
{job_description}

## 返回格式（纯 JSON，不要 ``` 标记）：
{{
  "total_score": 85,
  "skill_score": 34,
  "experience_score": 25,
  "education_score": 13,
  "project_score": 13,
  "analysis": "200字以内的综合分析",
  "strengths": ["优势1", "优势2"],
  "weaknesses": ["不足1", "不足2"],
  "recommendation": "推荐面试/可以面试/暂不推荐"
}}"""


# ── Technology Keyword Patterns ────────────────────────────

_TECH_PATTERNS: List[str] = [
    # Programming languages
    r"\b(Python|Java|JavaScript|TypeScript|Go|Rust|C\+\+|C#|PHP|Ruby|Swift|Kotlin|Scala)\b",
    # Frameworks
    r"\b(React|Vue\.?js|Angular|Node\.js|Django|Flask|Spring\s*Boot|Express|FastAPI|Next\.js|Nuxt\.js)\b",
    # Databases & Storage
    r"\b(SQL|MySQL|PostgreSQL|MongoDB|Redis|Elasticsearch|Cassandra|DynamoDB|ClickHouse)\b",
    # DevOps & Cloud
    r"\b(Docker|Kubernetes|AWS|Azure|GCP|阿里云|腾讯云|CI/CD|DevOps|Jenkins|GitLab\s*CI|Terraform)\b",
    # AI & Data
    r"\b(AI|机器学习|深度学习|NLP|计算机视觉|数据分析|大数据|Hadoop|Spark|PyTorch|TensorFlow)\b",
    # General tools
    r"\b(Git|Linux|微服务|RESTful|GraphQL|gRPC|MQ|Kafka|RabbitMQ|Nginx)\b",
    # Soft skills in Chinese
    r"[\u4e00-\u9fa5]{2,6}(?:开发|设计|管理|分析|测试|运维|架构|优化|驱动)",
]


# ── Education Hierarchy ────────────────────────────────────

_EDUCATION_SCORES: Dict[str, int] = {
    "博士": 15,
    "硕士": 13,
    "研究生": 13,
    "本科": 11,
    "学士": 11,
    "大专": 8,
}


# ── Default Match Result ───────────────────────────────────

def _make_empty_match() -> Dict[str, Any]:
    """Return an empty match result with the correct structure."""
    return {
        "total_score": 0,
        "skill_score": 0,
        "experience_score": 0,
        "education_score": 0,
        "project_score": 0,
        "analysis": "",
        "strengths": [],
        "weaknesses": [],
        "recommendation": "未评分",
        "matched_keywords": [],
        "job_keywords": [],
    }


# ── Public API ─────────────────────────────────────────────

def match_resume_to_job(
    resume_info: Dict[str, Any],
    job_description: str,
) -> Dict[str, Any]:
    """Match resume against job description and compute a score.

    Uses AI model when configured, otherwise falls back to
    keyword-based matching. Both paths also compute basic
    keyword matches for reference.

    Args:
        resume_info: Structured resume info from extract_resume_info().
        job_description: Text description of job requirements.

    Returns:
        Dictionary with scoring details including sub-scores,
        matched keywords, analysis, strengths, and weaknesses.
    """
    if not job_description or not job_description.strip():
        logger.warning("Empty job description, returning empty match")
        return _make_empty_match()

    if not config.is_ai_configured:
        logger.info("AI not configured, using keyword-based matching")
        return _keyword_match(resume_info, job_description)

    return _ai_match(resume_info, job_description)


def extract_job_keywords(job_description: str) -> List[str]:
    """Extract technology keywords from a job description.

    Uses regex patterns to identify common tech skills, tools,
    and requirements mentioned in the description.

    Args:
        job_description: The job description text.

    Returns:
        Deduplicated list of extracted keywords.
    """
    keywords: set[str] = set()

    for pattern in _TECH_PATTERNS:
        matches = re.findall(pattern, job_description, re.IGNORECASE)
        keywords.update(matches)

    # Extract Chinese skill phrases (2-6 chars + common suffix)
    chinese_skills = re.findall(
        r"[\u4e00-\u9fa5]{2,6}(?:开发|设计|管理|分析|测试|运维|架构|优化)",
        job_description,
    )
    keywords.update(chinese_skills)

    return list(keywords)


# ── AI Matching ────────────────────────────────────────────

def _ai_match(
    resume_info: Dict[str, Any],
    job_description: str,
) -> Dict[str, Any]:
    """Use AI model for intelligent matching."""
    resume_str = json.dumps(resume_info, ensure_ascii=False, indent=2)

    content, error = call_ai(
        system_prompt=_MATCHING_SYSTEM_PROMPT,
        user_prompt=_MATCHING_USER_PROMPT.format(
            resume_info=resume_str,
            job_description=job_description,
        ),
        temperature=0.2,
        max_tokens=1500,
    )

    if error:
        logger.error("AI matching failed: %s, falling back to keyword match", error)
        return _keyword_match(resume_info, job_description)

    try:
        clean_json = sanitize_ai_json(content or "{}")
        result = json.loads(clean_json)
        result = _normalize_match_result(result)
    except json.JSONDecodeError as exc:
        logger.error("AI matching JSON parse error: %s", exc)
        result = _keyword_match(resume_info, job_description)

    # Always compute basic keyword match for reference
    basic = _keyword_match(resume_info, job_description)
    result["matched_keywords"] = basic.get("matched_keywords", [])
    result["job_keywords"] = basic.get("job_keywords", [])

    logger.info(
        "AI match completed: total_score=%d, recommendation=%s",
        result["total_score"],
        result["recommendation"],
    )

    return result


# ── Keyword-based Fallback ─────────────────────────────────

def _keyword_match(
    resume_info: Dict[str, Any],
    job_description: str,
) -> Dict[str, Any]:
    """Compute a basic keyword-based matching score.

    This is the fallback when AI is unavailable. It provides
    reasonable scores based on keyword overlap, work years,
    education level, and project count.
    """
    resume_text = json.dumps(resume_info, ensure_ascii=False).lower()
    job_lower = job_description.lower()

    # Extract keywords from job description
    job_keywords = extract_job_keywords(job_description)

    # Find matching keywords in resume
    matched_keywords: List[str] = []
    for kw in job_keywords:
        if kw.lower() in resume_text:
            matched_keywords.append(kw)

    # ── Skill Score (0-40) ──
    if job_keywords:
        skill_ratio = len(matched_keywords) / len(job_keywords)
        skill_score = min(40, round(skill_ratio * 40))
    else:
        skill_score = 20  # No keywords found, give base score

    # ── Experience Score (0-30) ──
    experience_score = _calculate_experience_score(resume_info)

    # ── Education Score (0-15) ──
    education_score = _calculate_education_score(resume_info)

    # ── Project Score (0-15) ──
    project_score = _calculate_project_score(resume_info)

    total = skill_score + experience_score + education_score + project_score

    # Generate recommendation
    if total >= 75:
        recommendation = "推荐面试"
    elif total >= 50:
        recommendation = "可以面试"
    else:
        recommendation = "暂不推荐"

    return {
        "total_score": min(100, total),
        "skill_score": skill_score,
        "experience_score": experience_score,
        "education_score": education_score,
        "project_score": project_score,
        "analysis": (
            f"关键词匹配率: {len(matched_keywords)}/{len(job_keywords)}。"
            f"匹配关键词: {', '.join(matched_keywords[:10] or ['无'])}"
        ),
        "strengths": matched_keywords[:3] if matched_keywords else ["简历信息完整"],
        "weaknesses": (
            [f"未匹配: {', '.join(job_keywords[:5])}"]
            if job_keywords and len(matched_keywords) < len(job_keywords)
            else []
        ),
        "recommendation": recommendation,
        "matched_keywords": matched_keywords,
        "job_keywords": job_keywords,
    }


def _calculate_experience_score(resume_info: Dict[str, Any]) -> int:
    """Calculate experience score based on work years."""
    work_years = resume_info.get("background", {}).get("work_years")
    if not work_years:
        return 15  # Base score

    years_match = re.search(r"(\d+)", str(work_years))
    if not years_match:
        return 15

    years = int(years_match.group(1))
    if years >= 5:
        return 28
    elif years >= 3:
        return 22
    elif years >= 1:
        return 16
    return 12


def _calculate_education_score(resume_info: Dict[str, Any]) -> int:
    """Calculate education score based on degree level."""
    edu = resume_info.get("background", {}).get("education", "")
    edu_str = str(edu)

    for keyword, score in _EDUCATION_SCORES.items():
        if keyword in edu_str:
            return score

    return 10  # Base score for unspecified education


def _calculate_project_score(resume_info: Dict[str, Any]) -> int:
    """Calculate project score based on project count."""
    projects = resume_info.get("background", {}).get("project_experience", [])
    if not isinstance(projects, list):
        return 8
    return min(15, len(projects) * 5)


# ── Normalization ──────────────────────────────────────────

def _normalize_match_result(data: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure match result has all required fields with valid types.

    Fills missing fields with defaults and clamps scores to
    the valid 0-100 range.
    """
    defaults = _make_empty_match()

    for key, default_val in defaults.items():
        if key not in data or data[key] is None:
            data[key] = default_val

    # Clamp all score fields to 0-100
    score_keys = [
        "total_score", "skill_score",
        "experience_score", "education_score", "project_score",
    ]
    for key in score_keys:
        try:
            data[key] = max(0, min(100, int(data[key] or 0)))
        except (ValueError, TypeError):
            data[key] = 0

    # Ensure list fields are lists
    for list_key in ["strengths", "weaknesses", "matched_keywords", "job_keywords"]:
        if not isinstance(data.get(list_key), list):
            data[list_key] = []

    return data
