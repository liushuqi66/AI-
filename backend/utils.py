"""Shared utility functions for the resume analysis system.

This module provides common helpers used across all backend modules,
including text processing, JSON sanitization, response formatting,
and AI client creation.
"""

import hashlib
import json
import logging
import re
import time
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Tuple

from openai import OpenAI

from config import config

logger = logging.getLogger(__name__)


# ── AI Client ──────────────────────────────────────────────

_ai_client: Optional[OpenAI] = None


def get_ai_client() -> OpenAI:
    """Get or create a singleton OpenAI-compatible client.

    The client is lazily initialized on first call and reused thereafter
    to avoid creating new connections for every request.

    Returns:
        An OpenAI client instance configured from app config.
    """
    global _ai_client
    if _ai_client is None:
        _ai_client = OpenAI(
            api_key=config.OPENAI_API_KEY,
            base_url=config.OPENAI_BASE_URL,
            timeout=60.0,
            max_retries=2,
        )
        logger.info("AI client initialized: model=%s, base_url=%s",
                     config.AI_MODEL, config.OPENAI_BASE_URL)
    return _ai_client


# ── Hash Functions ─────────────────────────────────────────

def compute_md5(content: bytes | str) -> str:
    """Compute MD5 hash of bytes or string content."""
    if isinstance(content, str):
        content = content.encode("utf-8")
    return hashlib.md5(content).hexdigest()


# ── Text Cleaning ──────────────────────────────────────────

def sanitize_ai_json(text: str) -> str:
    """Strip markdown code fences and extract pure JSON from AI response.

    Handles common patterns like:
        ```json\n{...}\n```
        ```\n{...}\n```
        { ... }

    Args:
        text: Raw text response from AI model.

    Returns:
        Cleaned JSON string ready for parsing.
    """
    text = text.strip()
    # Remove code block markers
    if text.startswith("```"):
        text = text.split("\n", 1)[-1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        # Remove optional language tag like "json"
        if text.startswith("json"):
            text = text[4:].strip()
    return text


def safe_json_parse(text: str, default: Any = None) -> Any:
    """Safely parse JSON string, returning default on failure.

    Args:
        text: JSON string to parse.
        default: Value to return if parsing fails.

    Returns:
        Parsed JSON object or default value.
    """
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return default


# ── Response Helpers ───────────────────────────────────────

def make_response(
    data: Any = None,
    error: Optional[str] = None,
    code: Optional[str] = None,
    meta: Optional[Dict] = None,
) -> Dict:
    """Build a standardized API response envelope.

    Args:
        data: Response payload.
        error: Error message (if any).
        code: Error code identifier.
        meta: Additional metadata (timing, pagination, etc.).

    Returns:
        Standardized response dictionary.
    """
    response: Dict[str, Any] = {"success": error is None}
    if data is not None:
        response["data"] = data
    if error is not None:
        response["error"] = {"message": error, "code": code or "UNKNOWN"}
    if meta:
        response["meta"] = meta
    return response


def timed(func: Callable) -> Callable:
    """Decorator that logs function execution time.

    Usage:
        @timed
        def my_slow_function():
            ...
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = (time.perf_counter() - start) * 1000
        logger.debug("%s() completed in %.2f ms", func.__name__, elapsed)
        return result
    return wrapper


# ── Validation ─────────────────────────────────────────────

_ALLOWED_EXTENSIONS = {"pdf"}


def is_valid_pdf(filename: Optional[str]) -> bool:
    """Check if a filename has a valid PDF extension.

    Args:
        filename: The filename to validate (can be None).

    Returns:
        True if the filename ends with .pdf (case-insensitive).
    """
    if not filename:
        return False
    return "." in filename and filename.rsplit(".", 1)[1].lower() in _ALLOWED_EXTENSIONS


# ── AI Call Helper ─────────────────────────────────────────

def call_ai(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.1,
    max_tokens: int = 2000,
) -> Tuple[Optional[str], Optional[str]]:
    """Make an AI API call with error handling.

    Args:
        system_prompt: System message for the AI.
        user_prompt: User message containing the main content.
        temperature: Sampling temperature (0.0-1.0).
        max_tokens: Maximum tokens in the response.

    Returns:
        Tuple of (response_text, error_message). Exactly one is None.
    """
    if not config.OPENAI_API_KEY:
        return None, "AI API key not configured"

    try:
        client = get_ai_client()
        response = client.chat.completions.create(
            model=config.AI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        content = response.choices[0].message.content
        return content or "{}", None
    except Exception as e:
        logger.error("AI call failed: %s", e)
        return None, str(e)


# ── Regex Extractors ───────────────────────────────────────

def extract_email(text: str) -> Optional[str]:
    """Extract email address from text using regex."""
    match = re.search(
        r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        text,
    )
    return match.group() if match else None


def extract_phone(text: str) -> Optional[str]:
    """Extract Chinese phone number from text."""
    patterns = [
        r"(?:电话|手机|tel|phone)[:：]?\s*(\+?86[- ]?)?(\d{3,4}[- ]?\d{7,8}|\d{11})",
        r"1[3-9]\d{9}",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            phone = match.group(0)
            # Clean up label prefix
            phone = re.sub(r"^(?:电话|手机|tel|phone)[:：]?\s*", "", phone, flags=re.IGNORECASE)
            return phone.strip()
    return None


def extract_work_years(text: str) -> Optional[str]:
    """Extract work experience years from text."""
    match = re.search(r"(\d+)\s*年(?:工作|相关)?经验", text)
    return f"{match.group(1)}年" if match else None


def extract_education(text: str) -> Optional[str]:
    """Extract highest education level from text."""
    edu_keywords = ["博士", "硕士", "研究生", "本科", "学士", "大专"]
    for kw in edu_keywords:
        if kw in text:
            return kw
    return None


def extract_chinese_name(text: str) -> Optional[str]:
    """Extract Chinese name from text."""
    match = re.search(r"(?:姓名|名字)[:：]?\s*([\u4e00-\u9fa5]{2,4})", text)
    if match:
        return match.group(1)
    # Fallback: try first line (common in Chinese resumes)
    first_line = text.strip().split("\n")[0].strip()
    name_match = re.match(r"^([\u4e00-\u9fa5]{2,4})$", first_line)
    return name_match.group(1) if name_match else None
