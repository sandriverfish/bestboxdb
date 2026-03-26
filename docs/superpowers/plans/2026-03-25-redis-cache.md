# Redis Cache Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Redis-backed caching decorator layer to BestBox that wraps the SmartTrade repositories, reducing SQL Server calls with per-query-type TTLs and graceful fallback when Redis is unavailable.

**Architecture:** `CachedOrderRepository` and `CachedInventoryRepository` implement the same `Protocol` as their SmartTrade counterparts, wrapping them transparently. A shared `RedisCache` helper handles all Redis I/O with silent fallback on errors. `CacheConfig` centralises TTL values, all overridable via env vars.

**Tech Stack:** Python 3.10+, redis-py (`redis`), Pydantic v2 (`model_dump_json` / `model_validate_json`), pytest with `unittest.mock`

---

## File Map

| Action | Path | Responsibility |
|---|---|---|
| Create | `src/bestbox/adapters/cache/__init__.py` | Package marker |
| Create | `src/bestbox/adapters/cache/redis_cache.py` | `CacheConfig` + `RedisCache` |
| Create | `src/bestbox/adapters/cache/orders.py` | `CachedOrderRepository` decorator |
| Create | `src/bestbox/adapters/cache/inventory.py` | `CachedInventoryRepository` decorator |
| Modify | `src/bestbox/rest/main.py` | Wrap repos with cached counterparts |
| Modify | `src/bestbox/mcp/server.py` | Wrap repos with cached counterparts |
| Modify | `pyproject.toml` | Add `redis>=5.0.0` dependency |
| Modify | `.env.example` | Document `REDIS_URL` |
| Create | `tests/unit/test_redis_cache.py` | Unit tests for RedisCache fallback |
| Create | `tests/unit/test_cached_orders.py` | Unit tests for CachedOrderRepository |
| Create | `tests/unit/test_cached_inventory.py` | Unit tests for CachedInventoryRepository |
| Create | `tests/integration/test_cache_integration.py` | Integration tests requiring live Redis |

---

## Task 1: Add dependency and CacheConfig

**Files:**
- Modify: `pyproject.toml`
- Modify: `.env.example`
- Create: `src/bestbox/adapters/cache/__init__.py`
- Create: `src/bestbox/adapters/cache/redis_cache.py`
- Create: `tests/unit/test_redis_cache.py`

- [ ] **Step 1: Add `redis` to pyproject.toml**

In `pyproject.toml`, add `"redis>=5.0.0"` to the `dependencies` list:

```toml
dependencies = [
    "fastapi>=0.111.0",
    "uvicorn[standard]>=0.29.0",
    "pyodbc>=5.0.0",
    "pydantic>=2.0.0",
    "python-dotenv>=1.0.0",
    "mcp[cli]>=1.0.0",
    "redis>=5.0.0",
]
```

- [ ] **Step 2: Install the new dependency**

```bash
pip install redis>=5.0.0
```

Expected: `Successfully installed redis-5.x.x`

- [ ] **Step 3: Document REDIS_URL in .env.example**

Open `.env.example` and append:

```
REDIS_URL=redis://localhost:6379
CACHE_TTL_SALES_ORDER_SEC=60
CACHE_TTL_SALES_ORDER_LIST_SEC=180
CACHE_TTL_PURCHASE_ORDER_SEC=300
CACHE_TTL_PURCHASE_ORDER_LIST_SEC=300
CACHE_TTL_STOCK_SEC=120
CACHE_TTL_LOTS_SEC=120
CACHE_TTL_LOW_STOCK_SEC=300
```

- [ ] **Step 4: Write the failing test**

Create `tests/unit/test_redis_cache.py`:

```python
from unittest.mock import MagicMock, patch, PropertyMock
import pytest
from redis import RedisError


def _make_config(redis_url="redis://localhost:6379"):
    from bestbox.adapters.cache.redis_cache import CacheConfig
    cfg = CacheConfig()
    cfg.redis_url = redis_url
    return cfg


def test_cache_config_defaults():
    from bestbox.adapters.cache.redis_cache import CacheConfig
    cfg = CacheConfig()
    assert cfg.redis_url == "redis://localhost:6379"
    assert cfg.ttl_sales_order_sec == 60
    assert cfg.ttl_stock_sec == 120
    assert cfg.ttl_low_stock_sec == 300


def test_redis_cache_get_returns_value():
    from bestbox.adapters.cache.redis_cache import RedisCache, CacheConfig
    with patch("bestbox.adapters.cache.redis_cache.Redis") as MockRedis:
        mock_client = MockRedis.from_url.return_value
        mock_client.get.return_value = '{"key": "value"}'
        cache = RedisCache(CacheConfig())
        result = cache.get("some:key")
    assert result == '{"key": "value"}'


def test_redis_cache_get_returns_none_on_error():
    from bestbox.adapters.cache.redis_cache import RedisCache, CacheConfig
    with patch("bestbox.adapters.cache.redis_cache.Redis") as MockRedis:
        mock_client = MockRedis.from_url.return_value
        mock_client.get.side_effect = RedisError("connection refused")
        cache = RedisCache(CacheConfig())
        result = cache.get("some:key")
    assert result is None


def test_redis_cache_set_calls_redis():
    from bestbox.adapters.cache.redis_cache import RedisCache, CacheConfig
    with patch("bestbox.adapters.cache.redis_cache.Redis") as MockRedis:
        mock_client = MockRedis.from_url.return_value
        cache = RedisCache(CacheConfig())
        cache.set("some:key", "value", 60)
    mock_client.set.assert_called_once_with("some:key", "value", ex=60)


def test_redis_cache_set_silently_ignores_error():
    from bestbox.adapters.cache.redis_cache import RedisCache, CacheConfig
    with patch("bestbox.adapters.cache.redis_cache.Redis") as MockRedis:
        mock_client = MockRedis.from_url.return_value
        mock_client.set.side_effect = RedisError("write failed")
        cache = RedisCache(CacheConfig())
        cache.set("some:key", "value", 60)  # must not raise


def test_redis_cache_ping_returns_true_on_success():
    from bestbox.adapters.cache.redis_cache import RedisCache, CacheConfig
    with patch("bestbox.adapters.cache.redis_cache.Redis") as MockRedis:
        mock_client = MockRedis.from_url.return_value
        mock_client.ping.return_value = True
        cache = RedisCache(CacheConfig())
        assert cache.ping() is True


def test_redis_cache_ping_returns_false_on_error():
    from bestbox.adapters.cache.redis_cache import RedisCache, CacheConfig
    with patch("bestbox.adapters.cache.redis_cache.Redis") as MockRedis:
        mock_client = MockRedis.from_url.return_value
        mock_client.ping.side_effect = RedisError("unreachable")
        cache = RedisCache(CacheConfig())
        assert cache.ping() is False
```

- [ ] **Step 5: Run tests to confirm they fail**

```bash
pytest tests/unit/test_redis_cache.py -v
```

Expected: `ImportError` or `ModuleNotFoundError` — `bestbox.adapters.cache.redis_cache` does not exist yet.

- [ ] **Step 6: Create the package marker**

Create `src/bestbox/adapters/cache/__init__.py` (empty file).

- [ ] **Step 7: Implement `redis_cache.py`**

Create `src/bestbox/adapters/cache/redis_cache.py`:

```python
import os
import logging
from redis import Redis, RedisError

logger = logging.getLogger(__name__)


class CacheConfig:
    redis_url:                    str = os.environ.get("REDIS_URL", "redis://localhost:6379")
    ttl_sales_order_sec:          int = int(os.environ.get("CACHE_TTL_SALES_ORDER_SEC", "60"))
    ttl_sales_order_list_sec:     int = int(os.environ.get("CACHE_TTL_SALES_ORDER_LIST_SEC", "180"))
    ttl_purchase_order_sec:       int = int(os.environ.get("CACHE_TTL_PURCHASE_ORDER_SEC", "300"))
    ttl_purchase_order_list_sec:  int = int(os.environ.get("CACHE_TTL_PURCHASE_ORDER_LIST_SEC", "300"))
    ttl_stock_sec:                int = int(os.environ.get("CACHE_TTL_STOCK_SEC", "120"))
    ttl_lots_sec:                 int = int(os.environ.get("CACHE_TTL_LOTS_SEC", "120"))
    ttl_low_stock_sec:            int = int(os.environ.get("CACHE_TTL_LOW_STOCK_SEC", "300"))


class RedisCache:
    def __init__(self, config: CacheConfig):
        self._client = Redis.from_url(config.redis_url, decode_responses=True)

    def ping(self) -> bool:
        try:
            self._client.ping()
            return True
        except RedisError:
            return False

    def get(self, key: str) -> str | None:
        try:
            return self._client.get(key)
        except RedisError as e:
            logger.warning("Redis GET failed for %s: %s", key, e)
            return None

    def set(self, key: str, value: str, ttl: int) -> None:
        try:
            self._client.set(key, value, ex=ttl)
        except RedisError as e:
            logger.warning("Redis SET failed for %s: %s", key, e)

    def invalidate(self, pattern: str) -> int:
        try:
            keys = list(self._client.scan_iter(pattern))
            if keys:
                return self._client.delete(*keys)
            return 0
        except RedisError as e:
            logger.warning("Redis invalidate failed for pattern %s: %s", pattern, e)
            return 0
```

- [ ] **Step 8: Run tests to confirm they pass**

```bash
pytest tests/unit/test_redis_cache.py -v
```

Expected: 7 tests pass.

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml .env.example src/bestbox/adapters/cache/ tests/unit/test_redis_cache.py
git commit -m "feat: add CacheConfig and RedisCache helper with silent fallback"
```

---

## Task 2: CachedOrderRepository

**Files:**
- Create: `src/bestbox/adapters/cache/orders.py`
- Create: `tests/unit/test_cached_orders.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_cached_orders.py`:

```python
import json
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock
import pytest

from bestbox.core.domain.orders import (
    OrderStatus, OrderItem, SalesOrder, PurchaseOrder
)
from bestbox.adapters.cache.redis_cache import CacheConfig


def _make_item(item_id=1):
    return OrderItem(
        item_id=item_id, line_no=item_id, product_id=10,
        part_number="P001", brand="TI", description="IC",
        qty_ordered=Decimal("100"), qty_shipped=Decimal("0"),
        qty_available=Decimal("50"), unit_price=1.0,
        delivery_date=datetime(2026, 3, 1),
        status=OrderStatus.APPROVED,
    )


def _make_sales_order(order_id=1):
    return SalesOrder(
        order_id=order_id, order_sn=f"SO-{order_id:04d}",
        order_date=datetime(2026, 1, 1), customer_id=1,
        currency="CNY", total_amount=100.0,
        delivery_date=datetime(2026, 3, 1),
        status=OrderStatus.APPROVED, remark=None,
        items=[_make_item()],
    )


def _make_po(order_id=1):
    return PurchaseOrder(
        order_id=order_id, order_sn=f"PO-{order_id:04d}",
        order_date=datetime(2026, 1, 1), supplier_id=5,
        currency="CNY", total_amount=100.0,
        delivery_date=datetime(2026, 3, 1),
        status=OrderStatus.APPROVED,
        items=[],
    )


def _make_cache(hit_value=None):
    mock = MagicMock()
    mock.get.return_value = hit_value
    return mock


def _make_config():
    cfg = CacheConfig()
    cfg.ttl_sales_order_sec = 60
    cfg.ttl_sales_order_list_sec = 180
    cfg.ttl_purchase_order_sec = 300
    cfg.ttl_purchase_order_list_sec = 300
    return cfg


# --- get_sales_order ---

def test_get_sales_order_cache_hit_skips_repo():
    from bestbox.adapters.cache.orders import CachedOrderRepository
    order = _make_sales_order(order_id=42)
    mock_cache = _make_cache(hit_value=order.model_dump_json())
    mock_repo = MagicMock()

    repo = CachedOrderRepository(mock_repo, mock_cache, _make_config())
    result = repo.get_sales_order(42)

    assert result is not None
    assert result.order_id == 42
    mock_repo.get_sales_order.assert_not_called()


def test_get_sales_order_cache_miss_calls_repo_and_stores():
    from bestbox.adapters.cache.orders import CachedOrderRepository
    order = _make_sales_order(order_id=42)
    mock_cache = _make_cache(hit_value=None)
    mock_repo = MagicMock()
    mock_repo.get_sales_order.return_value = order

    repo = CachedOrderRepository(mock_repo, mock_cache, _make_config())
    result = repo.get_sales_order(42)

    assert result.order_id == 42
    mock_repo.get_sales_order.assert_called_once_with(42)
    mock_cache.set.assert_called_once()
    key, value, ttl = mock_cache.set.call_args[0]
    assert key == "bestbox:so:42"
    assert ttl == 60


def test_get_sales_order_not_found_does_not_cache():
    from bestbox.adapters.cache.orders import CachedOrderRepository
    mock_cache = _make_cache(hit_value=None)
    mock_repo = MagicMock()
    mock_repo.get_sales_order.return_value = None

    repo = CachedOrderRepository(mock_repo, mock_cache, _make_config())
    result = repo.get_sales_order(99)

    assert result is None
    mock_cache.set.assert_not_called()


# --- list_sales_orders ---

def test_list_sales_orders_cache_hit_skips_repo():
    from bestbox.adapters.cache.orders import CachedOrderRepository
    orders = [_make_sales_order(i) for i in range(1, 4)]
    cached_json = json.dumps([o.model_dump(mode="json") for o in orders])
    mock_cache = _make_cache(hit_value=cached_json)
    mock_repo = MagicMock()

    repo = CachedOrderRepository(mock_repo, mock_cache, _make_config())
    result = repo.list_sales_orders(limit=20)

    assert len(result) == 3
    mock_repo.list_sales_orders.assert_not_called()


def test_list_sales_orders_cache_miss_calls_repo_and_stores():
    from bestbox.adapters.cache.orders import CachedOrderRepository
    orders = [_make_sales_order(i) for i in range(1, 3)]
    mock_cache = _make_cache(hit_value=None)
    mock_repo = MagicMock()
    mock_repo.list_sales_orders.return_value = orders

    repo = CachedOrderRepository(mock_repo, mock_cache, _make_config())
    result = repo.list_sales_orders(customer_id=1, limit=10)

    assert len(result) == 2
    mock_repo.list_sales_orders.assert_called_once()
    mock_cache.set.assert_called_once()
    key, value, ttl = mock_cache.set.call_args[0]
    assert key.startswith("bestbox:so:list:")
    assert ttl == 180


def test_list_sales_orders_different_params_different_keys():
    from bestbox.adapters.cache.orders import CachedOrderRepository, _list_cache_key
    key1 = _list_cache_key("bestbox:so:list", {"customer_id": 1, "limit": 20})
    key2 = _list_cache_key("bestbox:so:list", {"customer_id": 2, "limit": 20})
    assert key1 != key2


# --- get_purchase_order ---

def test_get_purchase_order_cache_hit_skips_repo():
    from bestbox.adapters.cache.orders import CachedOrderRepository
    po = _make_po(order_id=7)
    mock_cache = _make_cache(hit_value=po.model_dump_json())
    mock_repo = MagicMock()

    repo = CachedOrderRepository(mock_repo, mock_cache, _make_config())
    result = repo.get_purchase_order(7)

    assert result.order_id == 7
    mock_repo.get_purchase_order.assert_not_called()


def test_get_purchase_order_cache_miss_calls_repo_and_stores():
    from bestbox.adapters.cache.orders import CachedOrderRepository
    po = _make_po(order_id=7)
    mock_cache = _make_cache(hit_value=None)
    mock_repo = MagicMock()
    mock_repo.get_purchase_order.return_value = po

    repo = CachedOrderRepository(mock_repo, mock_cache, _make_config())
    result = repo.get_purchase_order(7)

    assert result.order_id == 7
    key, value, ttl = mock_cache.set.call_args[0]
    assert key == "bestbox:po:7"
    assert ttl == 300
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/unit/test_cached_orders.py -v
```

Expected: `ImportError` — `bestbox.adapters.cache.orders` does not exist yet.

- [ ] **Step 3: Implement `orders.py`**

Create `src/bestbox/adapters/cache/orders.py`:

```python
import json
import hashlib
from datetime import datetime
from bestbox.core.domain.orders import SalesOrder, PurchaseOrder
from bestbox.core.ports.orders import OrderRepositoryProtocol
from bestbox.adapters.cache.redis_cache import RedisCache, CacheConfig


def _list_cache_key(prefix: str, params: dict) -> str:
    digest = hashlib.sha256(
        json.dumps(params, sort_keys=True, default=str).encode()
    ).hexdigest()[:16]
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

    def get_sales_order(self, order_id: int) -> SalesOrder | None:
        key = f"bestbox:so:{order_id}"
        cached = self._cache.get(key)
        if cached is not None:
            return SalesOrder.model_validate_json(cached)
        result = self._repo.get_sales_order(order_id)
        if result is not None:
            self._cache.set(key, result.model_dump_json(), self._config.ttl_sales_order_sec)
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
            "customer_id": customer_id, "date_from": date_from,
            "date_to": date_to, "status": status, "limit": limit,
        }
        key = _list_cache_key("bestbox:so:list", params)
        cached = self._cache.get(key)
        if cached is not None:
            return [SalesOrder.model_validate(item) for item in json.loads(cached)]
        results = self._repo.list_sales_orders(
            customer_id=customer_id, date_from=date_from,
            date_to=date_to, status=status, limit=limit,
        )
        self._cache.set(
            key,
            json.dumps([o.model_dump(mode="json") for o in results]),
            self._config.ttl_sales_order_list_sec,
        )
        return results

    def get_purchase_order(self, order_id: int) -> PurchaseOrder | None:
        key = f"bestbox:po:{order_id}"
        cached = self._cache.get(key)
        if cached is not None:
            return PurchaseOrder.model_validate_json(cached)
        result = self._repo.get_purchase_order(order_id)
        if result is not None:
            self._cache.set(key, result.model_dump_json(), self._config.ttl_purchase_order_sec)
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
            "supplier_id": supplier_id, "date_from": date_from,
            "date_to": date_to, "status": status, "limit": limit,
        }
        key = _list_cache_key("bestbox:po:list", params)
        cached = self._cache.get(key)
        if cached is not None:
            return [PurchaseOrder.model_validate(item) for item in json.loads(cached)]
        results = self._repo.list_purchase_orders(
            supplier_id=supplier_id, date_from=date_from,
            date_to=date_to, status=status, limit=limit,
        )
        self._cache.set(
            key,
            json.dumps([o.model_dump(mode="json") for o in results]),
            self._config.ttl_purchase_order_list_sec,
        )
        return results
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
pytest tests/unit/test_cached_orders.py -v
```

Expected: 9 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/bestbox/adapters/cache/orders.py tests/unit/test_cached_orders.py
git commit -m "feat: add CachedOrderRepository decorator with per-query-type TTL"
```

---

## Task 3: CachedInventoryRepository

**Files:**
- Create: `src/bestbox/adapters/cache/inventory.py`
- Create: `tests/unit/test_cached_inventory.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_cached_inventory.py`:

```python
import json
from decimal import Decimal
from unittest.mock import MagicMock
import pytest

from bestbox.core.domain.inventory import (
    InventoryStatus, InventoryLot, ProductStock
)
from bestbox.adapters.cache.redis_cache import CacheConfig


def _make_lot(lot_id=1, product_id=10, quantity=1000):
    return InventoryLot(
        lot_id=lot_id, product_id=product_id,
        part_number="GRM188", brand="MURATA",
        quantity=Decimal(str(quantity)),
        stockroom_id=1, date_code="2024-10-W1",
        unit_price=0.5, status=InventoryStatus.AVAILABLE,
    )


def _make_stock(product_id=10, part_number="GRM188"):
    return ProductStock(
        product_id=product_id, part_number=part_number,
        brand="MURATA", total_qty=Decimal("5000"),
        available_qty=Decimal("5000"), on_order_qty=Decimal("0"),
        lots=[_make_lot(product_id=product_id)],
    )


def _make_cache(hit_value=None):
    mock = MagicMock()
    mock.get.return_value = hit_value
    return mock


def _make_config():
    cfg = CacheConfig()
    cfg.ttl_stock_sec = 120
    cfg.ttl_lots_sec = 120
    cfg.ttl_low_stock_sec = 300
    return cfg


# --- get_product_stock_by_part_number ---

def test_check_stock_cache_hit_skips_repo():
    from bestbox.adapters.cache.inventory import CachedInventoryRepository
    stock = _make_stock(part_number="GRM188")
    mock_cache = _make_cache(hit_value=stock.model_dump_json())
    mock_repo = MagicMock()

    repo = CachedInventoryRepository(mock_repo, mock_cache, _make_config())
    result = repo.get_product_stock_by_part_number("GRM188")

    assert result is not None
    assert result.part_number == "GRM188"
    mock_repo.get_product_stock_by_part_number.assert_not_called()


def test_check_stock_cache_miss_calls_repo_and_stores():
    from bestbox.adapters.cache.inventory import CachedInventoryRepository
    stock = _make_stock(part_number="GRM188")
    mock_cache = _make_cache(hit_value=None)
    mock_repo = MagicMock()
    mock_repo.get_product_stock_by_part_number.return_value = stock

    repo = CachedInventoryRepository(mock_repo, mock_cache, _make_config())
    result = repo.get_product_stock_by_part_number("GRM188")

    assert result.part_number == "GRM188"
    mock_repo.get_product_stock_by_part_number.assert_called_once_with("GRM188")
    key, value, ttl = mock_cache.set.call_args[0]
    assert key == "bestbox:inv:stock:GRM188"
    assert ttl == 120


def test_check_stock_not_found_does_not_cache():
    from bestbox.adapters.cache.inventory import CachedInventoryRepository
    mock_cache = _make_cache(hit_value=None)
    mock_repo = MagicMock()
    mock_repo.get_product_stock_by_part_number.return_value = None

    repo = CachedInventoryRepository(mock_repo, mock_cache, _make_config())
    result = repo.get_product_stock_by_part_number("NOTFOUND")

    assert result is None
    mock_cache.set.assert_not_called()


# --- get_product_stock ---

def test_get_product_stock_cache_hit_skips_repo():
    from bestbox.adapters.cache.inventory import CachedInventoryRepository
    stock = _make_stock(product_id=42)
    mock_cache = _make_cache(hit_value=stock.model_dump_json())
    mock_repo = MagicMock()

    repo = CachedInventoryRepository(mock_repo, mock_cache, _make_config())
    result = repo.get_product_stock(42)

    assert result.product_id == 42
    mock_repo.get_product_stock.assert_not_called()


def test_get_product_stock_cache_miss_calls_repo_and_stores():
    from bestbox.adapters.cache.inventory import CachedInventoryRepository
    stock = _make_stock(product_id=42)
    mock_cache = _make_cache(hit_value=None)
    mock_repo = MagicMock()
    mock_repo.get_product_stock.return_value = stock

    repo = CachedInventoryRepository(mock_repo, mock_cache, _make_config())
    result = repo.get_product_stock(42)

    assert result.product_id == 42
    key, value, ttl = mock_cache.set.call_args[0]
    assert key == "bestbox:inv:stock:id:42"
    assert ttl == 120


# --- list_lots ---

def test_list_lots_cache_hit_skips_repo():
    from bestbox.adapters.cache.inventory import CachedInventoryRepository
    lots = [_make_lot(lot_id=i, product_id=10) for i in range(1, 4)]
    cached_json = json.dumps([l.model_dump(mode="json") for l in lots])
    mock_cache = _make_cache(hit_value=cached_json)
    mock_repo = MagicMock()

    repo = CachedInventoryRepository(mock_repo, mock_cache, _make_config())
    result = repo.list_lots(10)

    assert len(result) == 3
    mock_repo.list_lots.assert_not_called()


def test_list_lots_cache_miss_calls_repo_and_stores():
    from bestbox.adapters.cache.inventory import CachedInventoryRepository
    lots = [_make_lot(lot_id=i, product_id=10) for i in range(1, 3)]
    mock_cache = _make_cache(hit_value=None)
    mock_repo = MagicMock()
    mock_repo.list_lots.return_value = lots

    repo = CachedInventoryRepository(mock_repo, mock_cache, _make_config())
    result = repo.list_lots(10)

    assert len(result) == 2
    key, value, ttl = mock_cache.set.call_args[0]
    assert key == "bestbox:inv:lots:10"
    assert ttl == 120


# --- list_low_stock ---

def test_list_low_stock_cache_hit_skips_repo():
    from bestbox.adapters.cache.inventory import CachedInventoryRepository
    stocks = [_make_stock(product_id=i) for i in range(1, 4)]
    cached_json = json.dumps([s.model_dump(mode="json") for s in stocks])
    mock_cache = _make_cache(hit_value=cached_json)
    mock_repo = MagicMock()

    repo = CachedInventoryRepository(mock_repo, mock_cache, _make_config())
    result = repo.list_low_stock(Decimal("100"))

    assert len(result) == 3
    mock_repo.list_low_stock.assert_not_called()


def test_list_low_stock_cache_miss_calls_repo_and_stores():
    from bestbox.adapters.cache.inventory import CachedInventoryRepository
    stocks = [_make_stock(product_id=i) for i in range(1, 3)]
    mock_cache = _make_cache(hit_value=None)
    mock_repo = MagicMock()
    mock_repo.list_low_stock.return_value = stocks

    repo = CachedInventoryRepository(mock_repo, mock_cache, _make_config())
    result = repo.list_low_stock(Decimal("500"))

    assert len(result) == 2
    key, value, ttl = mock_cache.set.call_args[0]
    assert key == "bestbox:inv:lowstock:500"
    assert ttl == 300
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/unit/test_cached_inventory.py -v
```

Expected: `ImportError` — `bestbox.adapters.cache.inventory` does not exist yet.

- [ ] **Step 3: Implement `inventory.py`**

Create `src/bestbox/adapters/cache/inventory.py`:

```python
import json
from decimal import Decimal
from bestbox.core.domain.inventory import ProductStock, InventoryLot
from bestbox.core.ports.inventory import InventoryRepositoryProtocol
from bestbox.adapters.cache.redis_cache import RedisCache, CacheConfig


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

    def get_product_stock(self, product_id: int) -> ProductStock | None:
        key = f"bestbox:inv:stock:id:{product_id}"
        cached = self._cache.get(key)
        if cached is not None:
            return ProductStock.model_validate_json(cached)
        result = self._repo.get_product_stock(product_id)
        if result is not None:
            self._cache.set(key, result.model_dump_json(), self._config.ttl_stock_sec)
        return result

    def get_product_stock_by_part_number(self, part_number: str) -> ProductStock | None:
        key = f"bestbox:inv:stock:{part_number}"
        cached = self._cache.get(key)
        if cached is not None:
            return ProductStock.model_validate_json(cached)
        result = self._repo.get_product_stock_by_part_number(part_number)
        if result is not None:
            self._cache.set(key, result.model_dump_json(), self._config.ttl_stock_sec)
        return result

    def list_lots(self, product_id: int) -> list[InventoryLot]:
        key = f"bestbox:inv:lots:{product_id}"
        cached = self._cache.get(key)
        if cached is not None:
            return [InventoryLot.model_validate(item) for item in json.loads(cached)]
        results = self._repo.list_lots(product_id)
        self._cache.set(
            key,
            json.dumps([l.model_dump(mode="json") for l in results]),
            self._config.ttl_lots_sec,
        )
        return results

    def list_low_stock(self, threshold: Decimal) -> list[ProductStock]:
        key = f"bestbox:inv:lowstock:{threshold}"
        cached = self._cache.get(key)
        if cached is not None:
            return [ProductStock.model_validate(item) for item in json.loads(cached)]
        results = self._repo.list_low_stock(threshold)
        self._cache.set(
            key,
            json.dumps([s.model_dump(mode="json") for s in results]),
            self._config.ttl_low_stock_sec,
        )
        return results
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
pytest tests/unit/test_cached_inventory.py -v
```

Expected: 10 tests pass.

- [ ] **Step 5: Run all unit tests to check nothing is broken**

```bash
pytest tests/unit/ -v
```

Expected: all existing tests plus new cache tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/bestbox/adapters/cache/inventory.py tests/unit/test_cached_inventory.py
git commit -m "feat: add CachedInventoryRepository decorator"
```

---

## Task 4: Wire cache into REST app and MCP server

**Files:**
- Modify: `src/bestbox/rest/main.py`
- Modify: `src/bestbox/mcp/server.py`

No new tests needed here — the wiring uses `create_app(order_service=..., inventory_service=...)` injection in existing REST tests, so they remain unaffected. The MCP server wiring is covered by integration tests in Task 5.

- [ ] **Step 1: Update `rest/main.py`**

Replace the two `if ... is None:` blocks in `create_app()` with:

```python
import logging

from fastapi import FastAPI
from bestbox.services.orders import OrderService
from bestbox.services.inventory import InventoryService
from bestbox.rest.routers import orders as orders_router_mod
from bestbox.rest.routers import inventory as inventory_router_mod

logger = logging.getLogger(__name__)


def create_app(
    order_service: OrderService | None = None,
    inventory_service: InventoryService | None = None,
) -> FastAPI:
    app = FastAPI(title="BestBox ERP Gateway", version="0.1.0")

    if order_service is None:
        from bestbox.adapters.smarttrade.repositories.orders import SmartTradeOrderRepository
        from bestbox.adapters.smarttrade.repositories.inventory import SmartTradeInventoryRepository
        from bestbox.adapters.cache.redis_cache import CacheConfig, RedisCache
        from bestbox.adapters.cache.orders import CachedOrderRepository
        from bestbox.adapters.cache.inventory import CachedInventoryRepository

        config = CacheConfig()
        cache = RedisCache(config)
        if cache.ping():
            order_repo = CachedOrderRepository(SmartTradeOrderRepository(), cache, config)
            inv_repo   = CachedInventoryRepository(SmartTradeInventoryRepository(), cache, config)
        else:
            logger.warning("Redis unreachable at %s — running without cache", config.redis_url)
            order_repo = SmartTradeOrderRepository()
            inv_repo   = SmartTradeInventoryRepository()

        order_service     = OrderService(repo=order_repo)
        inventory_service = InventoryService(repo=inv_repo)

    orders_router_mod.set_service(order_service)
    inventory_router_mod.set_service(inventory_service)

    app.include_router(orders_router_mod.router, prefix="/api/v1")
    app.include_router(inventory_router_mod.router, prefix="/api/v1")

    return app


try:
    app = create_app()
except Exception:
    app = None  # type: ignore[assignment]
```

- [ ] **Step 2: Update `mcp/server.py`**

Replace the module-level service instantiation at lines 10–11 with:

```python
import logging
from decimal import Decimal
from mcp.server.fastmcp import FastMCP
from bestbox.services.orders import OrderService
from bestbox.services.inventory import InventoryService

logger = logging.getLogger(__name__)

mcp = FastMCP("BestBox")

def _build_services():
    from bestbox.adapters.smarttrade.repositories.orders import SmartTradeOrderRepository
    from bestbox.adapters.smarttrade.repositories.inventory import SmartTradeInventoryRepository
    from bestbox.adapters.cache.redis_cache import CacheConfig, RedisCache
    from bestbox.adapters.cache.orders import CachedOrderRepository
    from bestbox.adapters.cache.inventory import CachedInventoryRepository

    config = CacheConfig()
    cache  = RedisCache(config)
    if cache.ping():
        order_repo = CachedOrderRepository(SmartTradeOrderRepository(), cache, config)
        inv_repo   = CachedInventoryRepository(SmartTradeInventoryRepository(), cache, config)
    else:
        logger.warning("Redis unreachable at %s — running without cache", config.redis_url)
        order_repo = SmartTradeOrderRepository()
        inv_repo   = SmartTradeInventoryRepository()

    return (
        OrderService(repo=order_repo),
        InventoryService(repo=inv_repo),
    )

_order_service, _inventory_service = _build_services()
```

Keep all `@mcp.tool()` functions and the `if __name__ == "__main__": mcp.run()` block unchanged.

- [ ] **Step 3: Run existing unit tests**

```bash
pytest tests/unit/ -v
```

Expected: all pass — wiring changes only affect the default service construction path, not the injected path used by unit tests.

- [ ] **Step 4: Commit**

```bash
git add src/bestbox/rest/main.py src/bestbox/mcp/server.py
git commit -m "feat: wire Redis cache into REST app and MCP server with ping-based fallback"
```

---

## Task 5: Integration tests

**Files:**
- Create: `tests/integration/test_cache_integration.py`

These tests require both a live Redis instance (`REDIS_URL` set) and a live SmartTrade DB (`SMARTTRADE_*` env vars set). They are skipped if either is absent.

- [ ] **Step 1: Start Redis locally (if not already running)**

```bash
docker run -d --name bestbox-redis -p 6379:6379 redis:7-alpine
```

Add to `.env`:
```
REDIS_URL=redis://localhost:6379
```

- [ ] **Step 2: Write integration tests**

Create `tests/integration/test_cache_integration.py`:

```python
import os
import time
from decimal import Decimal
import pytest

REDIS_AVAILABLE = bool(os.environ.get("REDIS_URL"))


@pytest.fixture
def cache_and_config():
    from bestbox.adapters.cache.redis_cache import CacheConfig, RedisCache
    config = CacheConfig()
    cache = RedisCache(config)
    cache.invalidate("bestbox:*")   # flush before each test
    yield cache, config
    cache.invalidate("bestbox:*")   # flush after each test


@pytest.fixture
def order_repo(cache_and_config):
    from bestbox.adapters.smarttrade.repositories.orders import SmartTradeOrderRepository
    from bestbox.adapters.cache.orders import CachedOrderRepository
    cache, config = cache_and_config
    return CachedOrderRepository(SmartTradeOrderRepository(), cache, config)


@pytest.fixture
def inventory_repo(cache_and_config):
    from bestbox.adapters.smarttrade.repositories.inventory import SmartTradeInventoryRepository
    from bestbox.adapters.cache.inventory import CachedInventoryRepository
    cache, config = cache_and_config
    return CachedInventoryRepository(SmartTradeInventoryRepository(), cache, config)


@pytest.mark.integration
@pytest.mark.skipif(not REDIS_AVAILABLE, reason="REDIS_URL not set")
def test_list_sales_orders_second_call_returns_cached(order_repo):
    result1 = order_repo.list_sales_orders(limit=5)
    result2 = order_repo.list_sales_orders(limit=5)
    assert len(result1) == len(result2)
    assert [o.order_id for o in result1] == [o.order_id for o in result2]


@pytest.mark.integration
@pytest.mark.skipif(not REDIS_AVAILABLE, reason="REDIS_URL not set")
def test_list_sales_orders_ttl_expiry(cache_and_config, order_repo):
    cache, config = cache_and_config
    config.ttl_sales_order_list_sec = 1   # shorten TTL for this test

    result1 = order_repo.list_sales_orders(limit=3)
    time.sleep(1.1)
    result2 = order_repo.list_sales_orders(limit=3)

    # Both calls return valid results (second one hit SQL again)
    assert len(result1) > 0
    assert len(result2) > 0


@pytest.mark.integration
@pytest.mark.skipif(not REDIS_AVAILABLE, reason="REDIS_URL not set")
def test_list_low_stock_second_call_returns_cached(inventory_repo):
    result1 = inventory_repo.list_low_stock(Decimal("1000"))
    result2 = inventory_repo.list_low_stock(Decimal("1000"))
    assert len(result1) == len(result2)
```

- [ ] **Step 3: Run integration tests**

```bash
pytest tests/integration/test_cache_integration.py -v -m integration
```

Expected: 3 tests pass (requires Redis + SmartTrade DB).

- [ ] **Step 4: Run full test suite to confirm nothing regressed**

```bash
pytest tests/unit/ -v
```

Expected: all unit tests pass (integration tests excluded from default run).

- [ ] **Step 5: Commit**

```bash
git add tests/integration/test_cache_integration.py
git commit -m "test: add Redis cache integration tests with TTL expiry verification"
```

---

## Self-Review Notes

**Spec coverage check:**

| Spec requirement | Covered by |
|---|---|
| Decorator pattern for both repos | Tasks 2, 3 |
| `CacheConfig` with env-overridable TTLs | Task 1 |
| `RedisCache` with silent GET/SET fallback | Task 1 |
| `ping()` for startup connectivity check | Task 1, Task 4 |
| Per-query-type TTL (table of 7 queries) | Tasks 2, 3 |
| SHA-256 param hashing for list keys | Task 2 (`_list_cache_key`) |
| `model_dump_json` / `model_validate_json` serialisation | Tasks 2, 3 |
| REST app wiring with fallback | Task 4 |
| MCP server wiring with fallback | Task 4 |
| `redis` added to `pyproject.toml` | Task 1 |
| `REDIS_URL` in `.env.example` | Task 1 |
| Unit tests: cache hit skips repo | Tasks 2, 3 |
| Unit tests: cache miss calls repo + stores | Tasks 2, 3 |
| Unit tests: Redis error = silent miss | Task 1 (`test_redis_cache_get_returns_none_on_error`) |
| Integration tests: second call matches first | Task 5 |
| Integration tests: TTL expiry | Task 5 |
| `invalidate(pattern)` uses `scan_iter` | Task 1 |
