"""Module 2: Key Information Extraction using AI Model

Extracts structured information from resume text using AI (when
configured) or regex-based fallback extraction.

Public API:
    extract_resume_info(resume_text: str) -> dict

Output Structure:
    {
        "basic_info": {"name", "phone", "email", "address"},
        "job_info": {"job_intention", "expected_salary"},
        "background": {"work_years", "education", "project_experience": [...]}
    }
"""

import json
import logging
from typing import Any, Dict, Optional

from config import config
from utils import (
    call_ai,
    extract_chinese_name,
    extract_education,
    extract_email,
    extract_phone,
    extract_work_years,
    sanitize_ai_json,
)

logger = logging.getLogger(__name__)


# ── Prompt Templates ───────────────────────────────────────

_EXTRACTION_SYSTEM_PROMPT = (
    "你是一个精准的简历信息提取工具。"
    "请严格按照 JSON 格式返回结果，不要添加任何解释或 markdown 标记。"
    "如果某个字段无法从简历中找到，请将该字段值设为 null。"
)

_EXTRACTION_USER_PROMPT = """请从以下简历文本中提取关键信息，以 JSON 格式返回。

## 提取规则：
1. 基本信息（必选）：姓名、电话、邮箱、地址
2. 求职信息（加分）：求职意向、期望薪资
3. 背景信息（加分）：工作年限、学历背景、项目经历

## 注意事项：
- 电话号码格式可能是手机号或座机号，只提取纯数字部分
- 工作年限如果简历中明确写了就提取，否则根据工作经历推算
- 学历背景请提取最高学历
- 项目经历提取为数组，每个项目包含 project_name 和 description
- 只返回纯 JSON，不要包含 ``` 或任何其他标记

## 简历文本：
{resume_text}

## 输出格式：
{{
  "basic_info": {{
    "name": "姓名或 null",
    "phone": "电话或 null",
    "email": "邮箱或 null",
    "address": "地址或 null"
  }},
  "job_info": {{
    "job_intention": "求职意向或 null",
    "expected_salary": "期望薪资或 null"
  }},
  "background": {{
    "work_years": "工作年限或 null",
    "education": "学历背景或 null",
    "project_experience": [
      {{"project_name": "项目名称", "description": "项目描述"}}
    ]
  }}
}}"""


# ── Default Structure ──────────────────────────────────────

def _make_empty_extraction() -> Dict[str, Any]:
    """Return an empty extraction result with the correct structure."""
    return {
        "basic_info": {
            "name": None,
            "phone": None,
            "email": None,
            "address": None,
        },
        "job_info": {
            "job_intention": None,
            "expected_salary": None,
        },
        "background": {
            "work_years": None,
            "education": None,
            "project_experience": [],
        },
    }


# ── Public API ─────────────────────────────────────────────

def extract_resume_info(resume_text: str) -> Dict[str, Any]:
    """Extract structured information from resume text.

    Uses AI model when configured via OPENAI_API_KEY, otherwise
    falls back to regex-based extraction.

    Args:
        resume_text: Cleaned resume text content.

    Returns:
        Dictionary with basic_info, job_info, and background sections.
        All fields default to None/empty if not found.
    """
    if not resume_text or not resume_text.strip():
        logger.warning("Empty resume text provided for extraction")
        return _make_empty_extraction()

    # Truncate very long texts to stay within model token limits
    if len(resume_text) > 8000:
        logger.info("Truncating resume text from %d to 8000 chars", len(resume_text))
        resume_text = resume_text[:8000]

    if not config.is_ai_configured:
        logger.info("AI not configured, using regex fallback extraction")
        return _fallback_extraction(resume_text)

    return _ai_extraction(resume_text)


# ── AI Extraction ──────────────────────────────────────────

def _ai_extraction(resume_text: str) -> Dict[str, Any]:
    """Extract information using AI model."""
    content, error = call_ai(
        system_prompt=_EXTRACTION_SYSTEM_PROMPT,
        user_prompt=_EXTRACTION_USER_PROMPT.format(resume_text=resume_text),
        temperature=0.1,
        max_tokens=2000,
    )

    if error:
        logger.error("AI extraction failed: %s, falling back to regex", error)
        return _fallback_extraction(resume_text)

    try:
        clean_json = sanitize_ai_json(content or "{}")
        extracted = json.loads(clean_json)
        result = _normalize_extraction(extracted)
        logger.info(
            "AI extraction successful: name=%s, has_email=%s",
            result["basic_info"].get("name"),
            bool(result["basic_info"].get("email")),
        )
        return result
    except json.JSONDecodeError as exc:
        logger.error("AI response JSON parse error: %s", exc)
        return _fallback_extraction(resume_text)


# ── Normalization ──────────────────────────────────────────

def _normalize_extraction(data: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure extracted data has the correct structure with defaults.

    Fills missing sections and fields with default values,
    normalizes project experience field names.
    """
    default = _make_empty_extraction()

    for section_name, section_default in default.items():
        if section_name not in data or not isinstance(data[section_name], dict):
            data[section_name] = section_default
        else:
            for key, default_val in section_default.items():
                if key not in data[section_name]:
                    data[section_name][key] = default_val

    # Normalize project experience: support both "name"/"project_name"
    projects = data.get("background", {}).get("project_experience", [])
    if isinstance(projects, list):
        normalized_projects = []
        for proj in projects:
            if isinstance(proj, dict):
                normalized_projects.append({
                    "project_name": proj.get("project_name") or proj.get("name"),
                    "description": proj.get("description") or proj.get("desc"),
                })
        data["background"]["project_experience"] = normalized_projects

    return data


# ── Fallback Extraction ────────────────────────────────────

def _fallback_extraction(resume_text: str) -> Dict[str, Any]:
    """Regex-based fallback extraction when AI is unavailable.

    Uses pattern matching to extract common fields from
    Chinese/English resumes.
    """
    result = _make_empty_extraction()

    # Basic info
    result["basic_info"]["name"] = extract_chinese_name(resume_text)
    result["basic_info"]["phone"] = extract_phone(resume_text)
    result["basic_info"]["email"] = extract_email(resume_text)

    # Background
    result["background"]["work_years"] = extract_work_years(resume_text)
    result["background"]["education"] = extract_education(resume_text)

    logger.info(
        "Fallback extraction: name=%s, email=%s, phone=%s",
        result["basic_info"]["name"],
        result["basic_info"]["email"],
        "***" if result["basic_info"]["phone"] else None,
    )

    return result
