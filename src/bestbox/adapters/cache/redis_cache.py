import logging
import os
from dataclasses import dataclass, field

from redis import Redis, RedisError

logger = logging.getLogger(__name__)


def _get_env_int(name: str, default: int) -> int:
    return int(os.environ.get(name, str(default)))


@dataclass(slots=True)
class CacheConfig:
    redis_url: str = field(
        default_factory=lambda: os.environ.get(
            "REDIS_URL",
            "redis://localhost:6379",
        )
    )
    ttl_sales_order_sec: int = field(
        default_factory=lambda: _get_env_int("CACHE_TTL_SALES_ORDER_SEC", 60)
    )
    ttl_sales_order_list_sec: int = field(
        default_factory=lambda: _get_env_int(
            "CACHE_TTL_SALES_ORDER_LIST_SEC",
            180,
        )
    )
    ttl_purchase_order_sec: int = field(
        default_factory=lambda: _get_env_int(
            "CACHE_TTL_PURCHASE_ORDER_SEC",
            300,
        )
    )
    ttl_purchase_order_list_sec: int = field(
        default_factory=lambda: _get_env_int(
            "CACHE_TTL_PURCHASE_ORDER_LIST_SEC",
            300,
        )
    )
    ttl_stock_sec: int = field(
        default_factory=lambda: _get_env_int("CACHE_TTL_STOCK_SEC", 120)
    )
    ttl_lots_sec: int = field(
        default_factory=lambda: _get_env_int("CACHE_TTL_LOTS_SEC", 120)
    )
    ttl_low_stock_sec: int = field(
        default_factory=lambda: _get_env_int("CACHE_TTL_LOW_STOCK_SEC", 300)
    )


class RedisCache:
    def __init__(self, config: CacheConfig):
        self._client = Redis.from_url(config.redis_url, decode_responses=True)

    def ping(self) -> bool:
        try:
            return bool(self._client.ping())
        except RedisError as exc:
            logger.warning("Redis ping failed: %s", exc)
            return False

    def get(self, key: str) -> str | None:
        try:
            return self._client.get(key)
        except RedisError as exc:
            logger.warning("Redis GET failed for %s: %s", key, exc)
            return None

    def set(self, key: str, value: str, ttl: int) -> None:
        try:
            self._client.set(key, value, ex=ttl)
        except RedisError as exc:
            logger.warning("Redis SET failed for %s: %s", key, exc)

    def invalidate(self, pattern: str) -> int:
        try:
            keys = list(self._client.scan_iter(match=pattern))
            if not keys:
                return 0
            return int(self._client.delete(*keys))
        except RedisError as exc:
            logger.warning(
                "Redis invalidate failed for pattern %s: %s",
                pattern,
                exc,
            )
            return 0
