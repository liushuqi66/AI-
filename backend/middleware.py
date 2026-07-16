"""Flask middleware: request logging, timing, and rate limiting.

Provides:
    - RequestLogger: Logs all API requests with method, path, status, and timing
    - RateLimiter: Simple in-memory rate limiter per IP address
    - ErrorHandler: Unified error response formatting
"""

import logging
import time
from collections import defaultdict
from functools import wraps
from typing import Callable

from flask import jsonify, request, g

logger = logging.getLogger("api")


# ── Request Logging Middleware ─────────────────────────────

class RequestLogger:
    """Middleware that logs every request with timing and status.

    Usage:
        RequestLogger(app)
    """

    def __init__(self, app):
        self.app = app

        @app.before_request
        def before_request():
            g.start_time = time.perf_counter()

        @app.after_request
        def after_request(response):
            if hasattr(g, "start_time"):
                elapsed_ms = (time.perf_counter() - g.start_time) * 1000
                logger.info(
                    "%s %s → %d (%.2f ms)",
                    request.method,
                    request.path,
                    response.status_code,
                    elapsed_ms,
                )
                # Add timing header
                response.headers["X-Response-Time-ms"] = f"{elapsed_ms:.2f}"
            return response


# ── Rate Limiter ───────────────────────────────────────────

class RateLimiter:
    """Simple in-memory rate limiter based on client IP.

    Limits requests to a configurable number per time window.
    Uses a sliding window approach with cleanup of stale entries.

    Usage:
        limiter = RateLimiter(max_requests=100, window_seconds=60)

        @limiter.limit
        def my_handler():
            ...
    """

    def __init__(
        self,
        max_requests: int = 60,
        window_seconds: int = 60,
    ):
        self._max_requests = max_requests
        self._window = window_seconds
        self._clients: defaultdict[str, list[float]] = defaultdict(list)

    def _cleanup(self) -> None:
        """Remove expired entries from all client records."""
        now = time.time()
        threshold = now - self._window
        for ip in list(self._clients.keys()):
            self._clients[ip] = [
                t for t in self._clients[ip] if t > threshold
            ]
            if not self._clients[ip]:
                del self._clients[ip]

    def is_allowed(self, ip: str) -> bool:
        """Check if a request from this IP is within rate limits."""
        now = time.time()
        threshold = now - self._window

        # Clean up old entries for this IP
        self._clients[ip] = [
            t for t in self._clients[ip] if t > threshold
        ]

        if len(self._clients[ip]) >= self._max_requests:
            return False

        self._clients[ip].append(now)
        return True

    def limit(self, func: Callable) -> Callable:
        """Decorator to apply rate limiting to a Flask route."""
        @wraps(func)
        def wrapper(*args, **kwargs):
            ip = request.remote_addr or "unknown"
            if not self.is_allowed(ip):
                return jsonify({
                    "success": False,
                    "error": {
                        "message": "请求过于频繁，请稍后再试",
                        "code": "RATE_LIMITED",
                    },
                }), 429
            return func(*args, **kwargs)
        return wrapper


# ── Error Handler Registration ─────────────────────────────

def register_error_handlers(app) -> None:
    """Register standardized error handlers for common HTTP errors."""

    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({
            "success": False,
            "error": {
                "message": "请求参数无效",
                "code": "BAD_REQUEST",
            },
        }), 400

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({
            "success": False,
            "error": {
                "message": "接口不存在",
                "code": "NOT_FOUND",
            },
        }), 404

    @app.errorhandler(405)
    def method_not_allowed(error):
        return jsonify({
            "success": False,
            "error": {
                "message": "请求方法不允许",
                "code": "METHOD_NOT_ALLOWED",
            },
        }), 405

    @app.errorhandler(413)
    def payload_too_large(error):
        max_mb = app.config.get("MAX_CONTENT_LENGTH", 16 * 1024 * 1024) // (1024 * 1024)
        return jsonify({
            "success": False,
            "error": {
                "message": f"文件大小超过限制（最大 {max_mb} MB）",
                "code": "FILE_TOO_LARGE",
            },
        }), 413

    @app.errorhandler(429)
    def too_many_requests(error):
        return jsonify({
            "success": False,
            "error": {
                "message": "请求过于频繁，请稍后再试",
                "code": "RATE_LIMITED",
            },
        }), 429

    @app.errorhandler(500)
    def internal_error(error):
        logger.exception("Internal server error: %s", error)
        return jsonify({
            "success": False,
            "error": {
                "message": "服务器内部错误，请稍后重试",
                "code": "INTERNAL_ERROR",
            },
        }), 500
