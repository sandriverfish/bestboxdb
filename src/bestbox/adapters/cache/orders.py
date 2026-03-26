import hashlib
import json
import logging
from datetime import datetime

from pydantic import ValidationError

from bestbox.adapters.cache.redis_cache import CacheConfig, RedisCache
from bestbox.core.domain.orders import PurchaseOrder, SalesOrder
from bestbox.core.ports.orders import OrderRepositoryProtocol

logger = logging.getLogger(__name__)


def _list_cache_key(prefix: str, params: dict) -> str:
    payload = json.dumps(params, sort_keys=True, default=str)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"{prefix}:{digest}"


class CachedOrderRepository:
    def __init__(
        self,
        repo: OrderRepositoryProtocol,
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
            logger.warning("Order cache read failed for %s: %s", key, exc)
            return None

    def _cache_set(self, key: str, value: str, ttl: int) -> None:
        try:
            self._cache.set(key, value, ttl)
        except (AttributeError, ConnectionError, OSError, TypeError) as exc:
            logger.warning("Order cache write failed for %s: %s", key, exc)

    def _load_single(self, key: str, model_cls):
        cached = self._cache_get(key)
        if cached is None:
            return None
        try:
            return model_cls.model_validate_json(cached)
        except (ValidationError, ValueError, TypeError) as exc:
            logger.warning("Order cache payload invalid for %s: %s", key, exc)
            return None

    def _load_list(self, key: str, model_cls):
        cached = self._cache_get(key)
        if cached is None:
            return None
        try:
            payload = json.loads(cached)
            return [model_cls.model_validate(item) for item in payload]
        except (ValidationError, ValueError, TypeError) as exc:
            logger.warning("Order cache payload invalid for %s: %s", key, exc)
            return None

    def get_sales_order(self, order_id: int) -> SalesOrder | None:
        key = f"bestbox:so:{order_id}"
        cached = self._load_single(key, SalesOrder)
        if cached is not None:
            return cached

        result = self._repo.get_sales_order(order_id)
        if result is not None:
            self._cache_set(
                key, result.model_dump_json(), self._config.ttl_sales_order_sec
            )
        return result

    def list_sales_orders(
        self,
        customer_id: int | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        status: int | None = None,
        limit: int = 50,
    ) -> list[SalesOrder]:
        params = {
            "customer_id": customer_id,
            "date_from": date_from,
            "date_to": date_to,
            "status": status,
            "limit": limit,
        }
        key = _list_cache_key("bestbox:so:list", params)
        cached = self._load_list(key, SalesOrder)
        if cached is not None:
            return cached

        results = self._repo.list_sales_orders(
            customer_id=customer_id,
            date_from=date_from,
            date_to=date_to,
            status=status,
            limit=limit,
        )
        payload = json.dumps([order.model_dump(mode="json") for order in results])
        self._cache_set(key, payload, self._config.ttl_sales_order_list_sec)
        return results

    def get_purchase_order(self, order_id: int) -> PurchaseOrder | None:
        key = f"bestbox:po:{order_id}"
        cached = self._load_single(key, PurchaseOrder)
        if cached is not None:
            return cached

        result = self._repo.get_purchase_order(order_id)
        if result is not None:
            self._cache_set(
                key,
                result.model_dump_json(),
                self._config.ttl_purchase_order_sec,
            )
        return result

    def list_purchase_orders(
        self,
        supplier_id: int | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        status: int | None = None,
        limit: int = 50,
    ) -> list[PurchaseOrder]:
        params = {
            "supplier_id": supplier_id,
            "date_from": date_from,
            "date_to": date_to,
            "status": status,
            "limit": limit,
        }
        key = _list_cache_key("bestbox:po:list", params)
        cached = self._load_list(key, PurchaseOrder)
        if cached is not None:
            return cached

        results = self._repo.list_purchase_orders(
            supplier_id=supplier_id,
            date_from=date_from,
            date_to=date_to,
            status=status,
            limit=limit,
        )
        payload = json.dumps([order.model_dump(mode="json") for order in results])
        self._cache_set(key, payload, self._config.ttl_purchase_order_list_sec)
        return results
