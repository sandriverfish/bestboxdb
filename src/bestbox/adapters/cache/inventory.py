import json
import logging
from decimal import Decimal

from pydantic import ValidationError

from bestbox.adapters.cache.redis_cache import CacheConfig, RedisCache
from bestbox.core.domain.inventory import InventoryLot, ProductStock
from bestbox.core.ports.inventory import InventoryRepositoryProtocol

logger = logging.getLogger(__name__)


class CachedInventoryRepository:
    def __init__(
        self,
        repo: InventoryRepositoryProtocol,
        cache: RedisCache,
        config: CacheConfig,
    ):
        self._repo = repo
        self._cache = cache
        self._config = config

    def _cache_get(self, key: str) -> str | None:
        try:
            return self._cache.get(key)
        except (AttributeError, ConnectionError, OSError, TypeError) as exc:
            logger.warning("Inventory cache read failed for %s: %s", key, exc)
            return None

    def _cache_set(self, key: str, value: str, ttl: int) -> None:
        try:
            self._cache.set(key, value, ttl)
        except (AttributeError, ConnectionError, OSError, TypeError) as exc:
            logger.warning("Inventory cache write failed for %s: %s", key, exc)

    def _load_single(self, key: str) -> ProductStock | None:
        cached = self._cache_get(key)
        if cached is None:
            return None
        try:
            return ProductStock.model_validate_json(cached)
        except (ValidationError, ValueError, TypeError) as exc:
            logger.warning(
                "Inventory cache payload invalid for %s: %s",
                key,
                exc,
            )
            return None

    def _load_lots(self, key: str) -> list[InventoryLot] | None:
        cached = self._cache_get(key)
        if cached is None:
            return None
        try:
            payload = json.loads(cached)
            return [InventoryLot.model_validate(item) for item in payload]
        except (ValidationError, ValueError, TypeError) as exc:
            logger.warning(
                "Inventory cache payload invalid for %s: %s",
                key,
                exc,
            )
            return None

    def _load_stock_list(self, key: str) -> list[ProductStock] | None:
        cached = self._cache_get(key)
        if cached is None:
            return None
        try:
            payload = json.loads(cached)
            return [ProductStock.model_validate(item) for item in payload]
        except (ValidationError, ValueError, TypeError) as exc:
            logger.warning(
                "Inventory cache payload invalid for %s: %s",
                key,
                exc,
            )
            return None

    def get_product_stock(self, product_id: int) -> ProductStock | None:
        key = f"bestbox:inv:stock:id:{product_id}"
        cached = self._load_single(key)
        if cached is not None:
            return cached

        result = self._repo.get_product_stock(product_id)
        if result is not None:
            self._cache_set(
                key,
                result.model_dump_json(),
                self._config.ttl_stock_sec,
            )
        return result

    def get_product_stock_by_part_number(self, part_number: str) -> ProductStock | None:
        key = f"bestbox:inv:stock:{part_number}"
        cached = self._load_single(key)
        if cached is not None:
            return cached

        result = self._repo.get_product_stock_by_part_number(part_number)
        if result is not None:
            self._cache_set(
                key,
                result.model_dump_json(),
                self._config.ttl_stock_sec,
            )
        return result

    def list_lots(self, product_id: int) -> list[InventoryLot]:
        key = f"bestbox:inv:lots:{product_id}"
        cached = self._load_lots(key)
        if cached is not None:
            return cached

        results = self._repo.list_lots(product_id)
        payload = json.dumps([lot.model_dump(mode="json") for lot in results])
        self._cache_set(key, payload, self._config.ttl_lots_sec)
        return results

    def list_low_stock(self, threshold: Decimal) -> list[ProductStock]:
        key = f"bestbox:inv:lowstock:{threshold}"
        cached = self._load_stock_list(key)
        if cached is not None:
            return cached

        results = self._repo.list_low_stock(threshold)
        payload = json.dumps([stock.model_dump(mode="json") for stock in results])
        self._cache_set(key, payload, self._config.ttl_low_stock_sec)
        return results
