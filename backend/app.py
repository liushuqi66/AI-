"""AI-Powered Intelligent Resume Analysis System — Main Application

A Flask RESTful API that provides:
  - PDF resume upload and parsing (PyMuPDF)
  - AI-driven key information extraction (OpenAI-compatible API)
  - Multi-dimensional resume-job matching and scoring
  - Redis + in-memory LRU caching

Run:
    python app.py            # Production mode
    FLASK_ENV=development python app.py   # Debug mode

Environment variables:
    See config.py for full list (or .env.example).
"""

import logging
import os
import sys
import time
import uuid
from typing import Any, Dict, Optional

from flask import Flask, jsonify, request
from flask_cors import CORS
from werkzeug.utils import secure_filename

from cache_manager import cache_manager
from config import config
from middleware import RateLimiter, RequestLogger, register_error_handlers
from pdf_parser import get_pdf_metadata, parse_pdf
from resume_extractor import extract_resume_info
from resume_matcher import match_resume_to_job
from utils import compute_md5, is_valid_pdf, make_response

# ── Logging Configuration ──────────────────────────────────

logging.basicConfig(
    level=logging.DEBUG if config.is_development else logging.INFO,
    format="%(asctime)s [%(levelname)-5s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── App Initialization ─────────────────────────────────────

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = config.MAX_CONTENT_LENGTH

# CORS: Allow frontend dev server and production origins
CORS(app, resources={
    r"/api/*": {
        "origins": [
            "http://localhost:3000",
            "http://localhost:5173",
            "https://*.github.io",
        ],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type"],
    },
})

# Register middleware
RequestLogger(app)
register_error_handlers(app)
rate_limiter = RateLimiter(max_requests=60, window_seconds=60)

# Temp upload directory
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ── Helper Functions ───────────────────────────────────────

def _validate_uploaded_pdf() -> tuple[Optional[bytes], Optional[str], Optional[str]]:
    """Validate and read an uploaded PDF file from the request.

    Returns:
        Tuple of (file_bytes, filename, error_message).
        If error_message is not None, the upload is invalid.
    """
    if "file" not in request.files:
        return None, None, "请上传简历文件"

    file = request.files["file"]

    if not file.filename:
        return None, None, "文件名为空"

    if not is_valid_pdf(file.filename):
        return None, None, "仅支持 PDF 格式文件"

    file_bytes = file.read()
    if not file_bytes:
        return None, None, "上传的文件为空"

    filename = secure_filename(file.filename or "resume.pdf")
    return file_bytes, filename, None


# ═══════════════════════════════════════════════════════════
#  API Routes
# ═══════════════════════════════════════════════════════════


@app.route("/api/health", methods=["GET"])
def health_check():
    """Health check and system status endpoint.

    Returns service status, AI configuration, and cache state.
    Used by frontend to verify backend connectivity on load.

    Returns:
        200: { success, data: { status, version, ai_configured, ... } }
    """
    return jsonify(make_response(data={
        "status": "ok",
        "service": "AI Resume Analysis System",
        "version": "1.1.0",
        "cache_enabled": cache_manager.is_available,
        "cache_local_entries": cache_manager.local_size,
        "ai_configured": config.is_ai_configured,
        "ai_model": config.AI_MODEL if config.is_ai_configured else None,
        "timestamp": int(time.time()),
    }))


@app.route("/api/resume/upload", methods=["POST"])
@rate_limiter.limit
def upload_resume():
    """Module 1: Upload and parse a PDF resume.

    Accepts a PDF file via multipart/form-data, parses it,
    cleans the text, and returns structured results.

    Request:
        multipart/form-data
        - file: PDF file (required)

    Returns:
        200: Parsed resume text and metadata
        400: Invalid file or parse error
        413: File too large
    """
    file_bytes, filename, error = _validate_uploaded_pdf()
    if error:
        return jsonify(make_response(error=error, code="INVALID_FILE")), 400

    try:
        file_hash = compute_md5(file_bytes)

        # Check cache first
        cached = cache_manager.get_parsed_resume(file_hash)
        if cached:
            cached["from_cache"] = True
            logger.info("Cache HIT for resume: %s", filename)
            return jsonify(make_response(data=cached))

        # Parse PDF
        start_time = time.perf_counter()
        raw_text, cleaned_text = parse_pdf(file_bytes, filename)
        metadata = get_pdf_metadata(file_bytes)
        parse_time_ms = round((time.perf_counter() - start_time) * 1000, 2)

        result = {
            "resume_id": str(uuid.uuid4()),
            "file_name": filename,
            "file_hash": file_hash,
            "metadata": metadata,
            "raw_text_length": len(raw_text),
            "cleaned_text_length": len(cleaned_text),
            "cleaned_text": cleaned_text,
            "parse_time_ms": parse_time_ms,
            "from_cache": False,
        }

        # Cache the result
        cache_manager.set_parsed_resume(file_hash, result)

        return jsonify(make_response(data=result))

    except ValueError as exc:
        return jsonify(make_response(error=str(exc), code="PARSE_ERROR")), 400
    except Exception as exc:
        logger.exception("Unexpected error during resume upload")
        return jsonify(make_response(error=str(exc), code="INTERNAL_ERROR")), 500


@app.route("/api/resume/extract", methods=["POST"])
@rate_limiter.limit
def extract_information():
    """Module 2: Extract key information from resume text using AI.

    Accepts pre-parsed resume text and returns structured
    information including basic info, job preferences, and
    educational/project background.

    Request:
        application/json
        {
            "resume_text": "简历文本内容...",
            "resume_id": "optional-resume-id"
        }

    Returns:
        200: Structured resume information
        400: Empty or invalid request
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify(make_response(error="请求体不能为空", code="INVALID_JSON")), 400

    resume_text = (data.get("resume_text") or "").strip()
    if not resume_text:
        return jsonify(make_response(error="简历文本不能为空", code="EMPTY_TEXT")), 400

    try:
        start_time = time.perf_counter()
        extracted_info = extract_resume_info(resume_text)
        extract_time_ms = round((time.perf_counter() - start_time) * 1000, 2)

        result = {
            "resume_id": data.get("resume_id", str(uuid.uuid4())),
            "extracted_info": extracted_info,
            "extract_time_ms": extract_time_ms,
            "ai_used": config.is_ai_configured,
        }

        return jsonify(make_response(data=result))

    except Exception as exc:
        logger.exception("Error during information extraction")
        return jsonify(make_response(error=str(exc), code="EXTRACT_ERROR")), 500


@app.route("/api/resume/analyze", methods=["POST"])
@rate_limiter.limit
def analyze_resume():
    """Full pipeline: Upload PDF → Parse → Extract → Match.

    This is the recommended endpoint for the frontend. It handles
    the complete workflow in a single request.

    Request:
        multipart/form-data
        - file: PDF file (required)
        - job_description: Job requirements text (optional)

    Returns:
        200: Complete analysis with all results
        400: Invalid file or parse error
    """
    file_bytes, filename, error = _validate_uploaded_pdf()
    if error:
        return jsonify(make_response(error=error, code="INVALID_FILE")), 400

    job_description = (request.form.get("job_description") or "").strip()

    try:
        file_hash = compute_md5(file_bytes)
        job_hash = compute_md5(job_description) if job_description else ""
        total_start = time.perf_counter()

        # ── Step 1: Parse PDF ──
        raw_text, cleaned_text = parse_pdf(file_bytes, filename)
        metadata = get_pdf_metadata(file_bytes)

        # ── Step 2: Extract Information ──
        extracted_info = extract_resume_info(cleaned_text)

        # ── Step 3: Match with Job Description ──
        match_result = None
        if job_description:
            # Check cache for resume+job combination
            cached_match = cache_manager.get_match_result(file_hash, job_hash)
            if cached_match:
                match_result = cached_match
                match_result["from_cache"] = True
                logger.info("Cache HIT for match result")
            else:
                match_result = match_resume_to_job(extracted_info, job_description)
                match_result["from_cache"] = False
                cache_manager.set_match_result(file_hash, job_hash, match_result)

        total_time_ms = round((time.perf_counter() - total_start) * 1000, 2)

        result = {
            "resume_id": str(uuid.uuid4()),
            "file_name": filename,
            "file_hash": file_hash,
            "metadata": metadata,
            "cleaned_text": cleaned_text,
            "extracted_info": extracted_info,
            "match_result": match_result,
            "total_time_ms": total_time_ms,
            "cache_enabled": cache_manager.is_available,
            "ai_used": config.is_ai_configured,
            "ai_model": config.AI_MODEL if config.is_ai_configured else None,
        }

        logger.info(
            "Full analysis completed: '%s' in %.2f ms (AI=%s)",
            filename, total_time_ms, config.is_ai_configured,
        )

        return jsonify(make_response(data=result))

    except ValueError as exc:
        return jsonify(make_response(error=str(exc), code="PARSE_ERROR")), 400
    except Exception as exc:
        logger.exception("Unexpected error during full analysis")
        return jsonify(make_response(error=str(exc), code="INTERNAL_ERROR")), 500


@app.route("/api/resume/match", methods=["POST"])
@rate_limiter.limit
def match_resume():
    """Module 3: Match parsed resume against a job description.

    Standalone matching endpoint for cases where the resume
    has already been parsed/extracted.

    Request:
        application/json
        {
            "resume_info": { ... extracted resume info ... },
            "job_description": "岗位需求描述文本"
        }

    Returns:
        200: Match scoring details
        400: Missing required fields
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify(make_response(error="请求体不能为空", code="INVALID_JSON")), 400

    resume_info = data.get("resume_info")
    job_description = (data.get("job_description") or "").strip()

    if not resume_info:
        return jsonify(make_response(error="简历信息不能为空", code="EMPTY_RESUME_INFO")), 400

    if not job_description:
        return jsonify(make_response(error="岗位需求描述不能为空", code="EMPTY_JOB_DESC")), 400

    try:
        start_time = time.perf_counter()
        match_result = match_resume_to_job(resume_info, job_description)
        match_time_ms = round((time.perf_counter() - start_time) * 1000, 2)

        result = {
            "match_result": match_result,
            "match_time_ms": match_time_ms,
            "ai_used": config.is_ai_configured,
        }

        logger.info("Match completed: score=%d, time=%.2f ms",
                     match_result.get("total_score", 0), match_time_ms)

        return jsonify(make_response(data=result))

    except Exception as exc:
        logger.exception("Error during matching")
        return jsonify(make_response(error=str(exc), code="MATCH_ERROR")), 500


@app.route("/api/cache/stats", methods=["GET"])
def cache_stats():
    """Get cache statistics for monitoring.

    Returns:
        200: Cache statistics including hit rates and entry counts.
    """
    stats = cache_manager.get_stats()
    return jsonify(make_response(data=stats))


@app.route("/api/cache/clear", methods=["POST"])
def clear_cache():
    """Clear all cached resume analysis results.

    Returns:
        200: Number of cleared entries from each cache tier.
    """
    result = cache_manager.clear_all()
    return jsonify(make_response(data={
        "message": f"已清除 {result['redis_cleared'] + result['local_cleared']} 条缓存",
        **result,
    }))


# ═══════════════════════════════════════════════════════════
#  Entry Point
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    banner = f"""
╔══════════════════════════════════════════════════════════════╗
║     AI 智能简历分析系统  v1.1.0                              ║
║     AI-Powered Resume Analysis System                        ║
╠══════════════════════════════════════════════════════════════╣
║  Port:    {config.FLASK_PORT:<6}                                          ║
║  AI:      {"Configured (" + config.AI_MODEL + ")" if config.is_ai_configured else "Not Configured":<30} ║
║  Cache:   {"Redis" if cache_manager.is_available else "In-Memory LRU":<12}                              ║
║  Env:     {config.FLASK_ENV:<10}                                        ║
╚══════════════════════════════════════════════════════════════╝
"""
    print(banner)

    app.run(
        host="0.0.0.0",
        port=config.FLASK_PORT,
        debug=config.is_development,
    )
