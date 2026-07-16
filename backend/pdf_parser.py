"""Module 1: Resume Upload & PDF Parsing

Handles PDF file parsing with multi-page support, text extraction,
cleaning, and metadata extraction. Uses PyMuPDF (fitz) for robust
PDF handling with graceful error recovery.

Public API:
    parse_pdf(file_bytes, filename) -> Tuple[str, str]
    get_pdf_metadata(file_bytes) -> dict
    clean_resume_text(text) -> str
"""

import io
import logging
import re
from typing import Dict, Tuple

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


# ── Public API ─────────────────────────────────────────────


def parse_pdf(file_bytes: bytes, filename: str) -> Tuple[str, str]:
    """Parse a PDF resume file and extract clean text.

    Opens the PDF from memory (no disk I/O), extracts text from
    every page, and cleans the result for downstream AI processing.

    Args:
        file_bytes: Raw bytes of the PDF file.
        filename: Original filename for validation.

    Returns:
        Tuple of (raw_text, cleaned_text).

    Raises:
        ValueError: If file is not a valid PDF, has no pages, or
                    contains no extractable text.
    """
    if not filename.lower().endswith(".pdf"):
        raise ValueError("仅支持 PDF 格式的简历文件")

    # Validate PDF header magic bytes
    if not file_bytes[:4] == b"%PDF":
        raise ValueError("文件不是有效的 PDF 格式")

    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
    except Exception as exc:
        raise ValueError(f"无法打开 PDF 文件: {exc}") from exc

    try:
        if doc.page_count == 0:
            raise ValueError("PDF 文件为空，没有页面内容")

        raw_pages: list[str] = []
        for page_num in range(doc.page_count):
            page = doc[page_num]
            text = page.get_text("text")
            if text.strip():
                raw_pages.append(text)

        if not raw_pages:
            # Try OCR-like approach: extract text with block sorting
            for page_num in range(doc.page_count):
                page = doc[page_num]
                blocks = page.get_text("blocks")
                page_text = "\n".join(
                    b[4] for b in blocks if b[6] == 0 and b[4].strip()
                )
                if page_text.strip():
                    raw_pages.append(page_text)

        if not raw_pages:
            raise ValueError(
                "无法从 PDF 中提取到有效文本，"
                "请确认简历是否为图片格式（建议使用文本型 PDF）"
            )

        raw_text = "\n".join(raw_pages)
        cleaned_text = clean_resume_text(raw_text)

        logger.info(
            "Parsed PDF '%s': %d pages, raw=%d chars, cleaned=%d chars",
            filename, doc.page_count, len(raw_text), len(cleaned_text),
        )

        return raw_text, cleaned_text

    finally:
        doc.close()


def get_pdf_metadata(file_bytes: bytes) -> Dict:
    """Extract basic metadata from a PDF file.

    Args:
        file_bytes: Raw bytes of the PDF file.

    Returns:
        Dictionary with page_count and file_size_kb.
    """
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        page_count = doc.page_count
        doc.close()
    except Exception:
        page_count = 0

    return {
        "page_count": page_count,
        "file_size_kb": round(len(file_bytes) / 1024, 2),
    }


# ── Internal Helpers ───────────────────────────────────────


def clean_resume_text(text: str) -> str:
    """Clean and normalize extracted resume text for AI processing.

    Performs the following steps:
    1. Remove non-printable control characters
    2. Normalize line endings (CRLF → LF)
    3. Collapse excessive blank lines (max 2 consecutive)
    4. Strip trailing whitespace per line
    5. Collapse multiple spaces into one (preserves line breaks)
    6. Trim leading/trailing blank lines

    Args:
        text: Raw text extracted from PDF.

    Returns:
        Cleaned and normalized text.
    """
    if not text:
        return ""

    # Remove non-printable characters except common whitespace and CJK
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", "", text)

    # Normalize line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Collapse 3+ consecutive newlines into max 2
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Process each line
    lines = []
    for line in text.split("\n"):
        # Strip trailing whitespace and collapse internal spaces
        cleaned = re.sub(r"[ \t]+", " ", line).strip()
        lines.append(cleaned)

    # Remove leading/trailing blank lines
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()

    return "\n".join(lines)
