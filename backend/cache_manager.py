"""Module 4: Multi-tier Caching for Resume Analysis Results

Provides a caching layer to avoid redundant PDF parsing and
AI-based scoring. Supports:
    - Redis cache (primary, shared across instances)
    - In-memory LRU cache (fallback when Redis is unavailable)

Usage:
    from cache_manager import cache_manager
    cached = cache_manager.get_parsed_resume(file_hash)
"""

import hashlib
import json
import logging
import threading
import time
from collections import OrderedDict
from typing import Any, Dict, Optional

import redis

from config import config

logger = logging.getLogger(__name__)


# ── In-Memory LRU Cache ────────────────────────────────────

class _LRUCache:
    """Thread-safe LRU cache with TTL support.

    Used as a local fallback when Redis is unavailable.
    """

    def __init__(self, max_size: int = 128, default_ttl: int = 3600):
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired."""
        with self._lock:
            if key not in self._cache:
                return None
            value, expires_at = self._cache[key]
            if time.time() > expires_at:
                del self._cache[key]
                return None
            # Move to end (most recently used)
            self._cache.move_to_end(key)
            return value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache with TTL."""
        ttl = ttl or self._default_ttl
        expires_at = time.time() + ttl
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            elif len(self._cache) >= self._max_size:
                # Evict least recently used
                self._cache.popitem(last=False)
            self._cache[key] = (value, expires_at)

    def clear(self) -> int:
        """Clear all entries. Returns number of entries cleared."""
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            return count

    @property
    def size(self) -> int:
        """Current number of entries."""
        with self._lock:
            return len(self._cache)


# ── Cache Manager ──────────────────────────────────────────

class CacheManager:
    """Multi-tier cache manager with Redis + in-memory LRU fallback.

    Features:
    - Redis as primary distributed cache
    - In-memory LRU as local fallback
    - Automatic key prefixing and TTL management
    - Graceful degradation when Redis is down
    """

    _KEY_PREFIX = "resume"

    def __init__(self):
        self._redis: Optional[redis.Redis] = None
        self._local = _LRUCache(max_size=128, default_ttl=config.CACHE_TTL)
        self._init_redis()

    def _init_redis(self) -> None:
        """Attempt to connect to Redis with short timeout.

        Connection failure is non-fatal — the system will
        gracefully fall back to in-memory LRU cache.
        """
        try:
            self._redis = redis.Redis(
                host=config.REDIS_HOST,
                port=config.REDIS_PORT,
                password=config.REDIS_PASSWORD,
                db=config.REDIS_DB,
                decode_responses=True,
                socket_connect_timeout=1,
                socket_timeout=1,
            )
            self._redis.ping()
            logger.info("Redis cache connected at %s:%d", config.REDIS_HOST, config.REDIS_PORT)
        except Exception:
            logger.warning(
                "Redis unavailable at %s:%d, using in-memory LRU cache only",
                config.REDIS_HOST, config.REDIS_PORT,
            )
            self._redis = None

    # ── Key Generation ──────────────────────────────────

    def _make_key(self, prefix: str, content: str) -> str:
        """Generate a namespaced cache key with content hash."""
        content_hash = hashlib.md5(content.encode("utf-8")).hexdigest()
        return f"{self._KEY_PREFIX}:{prefix}:{content_hash}"

    # ── Public Properties ───────────────────────────────

    @property
    def is_available(self) -> bool:
        """Check if Redis cache is connected."""
        return self._redis is not None

    @property
    def local_size(self) -> int:
        """Number of entries in local LRU cache."""
        return self._local.size

    # ── Generic Cache Operations ────────────────────────

    def get(self, key: str) -> Optional[Dict]:
        """Get value from cache (Redis first, then local)."""
        # Try Redis first
        if self._redis:
            try:
                data = self._redis.get(key)
                if data:
                    logger.debug("Redis HIT: %s", key)
                    return json.loads(data)
                logger.debug("Redis MISS: %s", key)
            except Exception as exc:
                logger.error("Redis get error: %s", exc)

        # Fall back to local LRU
        local_value = self._local.get(key)
        if local_value is not None:
            logger.debug("Local LRU HIT: %s", key)
        return local_value

    def set(self, key: str, value: Dict, ttl: Optional[int] = None) -> bool:
        """Set value in both Redis and local cache."""
        ttl = ttl or config.CACHE_TTL
        success = False

        # Set in Redis
        if self._redis:
            try:
                self._redis.setex(
                    key, ttl, json.dumps(value, ensure_ascii=False)
                )
                success = True
            except Exception as exc:
                logger.error("Redis set error: %s", exc)

        # Always set in local LRU
        self._local.set(key, value, ttl)
        return success

    # ── Domain-Specific Operations ──────────────────────

    def get_parsed_resume(self, file_hash: str) -> Optional[Dict]:
        """Get cached parsed resume by file hash."""
        return self.get(self._make_key("parsed", file_hash))

    def set_parsed_resume(self, file_hash: str, data: Dict) -> bool:
        """Cache parsed resume result."""
        return self.set(self._make_key("parsed", file_hash), data)

    def get_match_result(
        self, resume_hash: str, job_hash: str
    ) -> Optional[Dict]:
        """Get cached match result by combined hash."""
        combined = f"{resume_hash}:{job_hash}"
        return self.get(self._make_key("match", combined))

    def set_match_result(
        self, resume_hash: str, job_hash: str, data: Dict
    ) -> bool:
        """Cache match result."""
        combined = f"{resume_hash}:{job_hash}"
        return self.set(self._make_key("match", combined), data)

    def clear_all(self) -> Dict[str, Any]:
        """Clear all caches (Redis + local)."""
        result = {"redis_cleared": 0, "local_cleared": 0}

        if self._redis:
            try:
                keys = self._redis.keys(f"{self._KEY_PREFIX}:*")
                if keys:
                    self._redis.delete(*keys)
                result["redis_cleared"] = len(keys)
            except Exception as exc:
                logger.error("Redis clear error: %s", exc)

        result["local_cleared"] = self._local.clear()
        logger.info("Cache cleared: redis=%d, local=%d",
                     result["redis_cleared"], result["local_cleared"])
        return result

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        stats: Dict[str, Any] = {
            "redis_enabled": self.is_available,
            "local_entries": self._local.size,
        }

        if self._redis:
            try:
                info = self._redis.info("stats")
                keys = self._redis.keys(f"{self._KEY_PREFIX}:*")
                stats.update({
                    "redis_keys_total": len(keys),
                    "redis_used_memory": info.get("used_memory_human", "N/A"),
                    "redis_connected_clients": info.get("connected_clients", 0),
                    "redis_hits": info.get("keyspace_hits", 0),
                    "redis_misses": info.get("keyspace_misses", 0),
                })
            except Exception:
                stats["redis_error"] = "Unable to fetch stats"

        return stats


# ── Singleton ──────────────────────────────────────────────

cache_manager = CacheManager()
