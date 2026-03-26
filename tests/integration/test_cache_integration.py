import os
import time
from decimal import Decimal

import pytest

from bestbox.adapters.cache.orders import _list_cache_key

pytestmark = pytest.mark.integration

REDIS_CONFIGURED = bool(os.environ.get("REDIS_URL"))
SMARTTRADE_CONFIGURED = all(
    os.environ.get(name) for name in ("SMARTTRADE_SERVER", "SMARTTRADE_DATABASE")
)


@pytest.fixture
def cache_bundle():
    from bestbox.adapters.cache.redis_cache import CacheConfig, RedisCache

    config = CacheConfig()
    cache = RedisCache(config)
    if not cache.ping():
        pytest.skip("Redis is unreachable")

    cache.invalidate("bestbox:*")
    yield cache, config
    cache.invalidate("bestbox:*")


@pytest.fixture
def order_repo(cache_bundle):
    from bestbox.adapters.cache.orders import CachedOrderRepository
    from bestbox.adapters.smarttrade.repositories.orders import (
        SmartTradeOrderRepository,
    )

    cache, config = cache_bundle
    return CachedOrderRepository(SmartTradeOrderRepository(), cache, config)


@pytest.fixture
def inventory_repo(cache_bundle):
    from bestbox.adapters.cache.inventory import CachedInventoryRepository
    from bestbox.adapters.smarttrade.repositories.inventory import (
        SmartTradeInventoryRepository,
    )

    cache, config = cache_bundle
    return CachedInventoryRepository(
        SmartTradeInventoryRepository(),
        cache,
        config,
    )


@pytest.mark.skipif(
    not (REDIS_CONFIGURED and SMARTTRADE_CONFIGURED),
    reason="Redis or SmartTrade DB is not configured",
)
def test_list_sales_orders_second_call_returns_cached(cache_bundle, order_repo):
    cache, _ = cache_bundle

    first = order_repo.list_sales_orders(limit=5)
    second = order_repo.list_sales_orders(limit=5)
    key = _list_cache_key(
        "bestbox:so:list",
        {
            "customer_id": None,
            "date_from": None,
            "date_to": None,
            "status": None,
            "limit": 5,
        },
    )

    assert cache.get(key) is not None
    assert [order.order_id for order in first] == [order.order_id for order in second]


@pytest.mark.skipif(
    not (REDIS_CONFIGURED and SMARTTRADE_CONFIGURED),
    reason="Redis or SmartTrade DB is not configured",
)
def test_list_sales_orders_ttl_expiry(cache_bundle):
    from bestbox.adapters.cache.orders import CachedOrderRepository
    from bestbox.adapters.smarttrade.repositories.orders import (
        SmartTradeOrderRepository,
    )

    cache, config = cache_bundle
    config.ttl_sales_order_list_sec = 1
    repo = CachedOrderRepository(SmartTradeOrderRepository(), cache, config)
    key = _list_cache_key(
        "bestbox:so:list",
        {
            "customer_id": None,
            "date_from": None,
            "date_to": None,
            "status": None,
            "limit": 3,
        },
    )

    first = repo.list_sales_orders(limit=3)
    assert cache.get(key) is not None

    time.sleep(1.1)

    assert cache.get(key) is None
    second = repo.list_sales_orders(limit=3)
    assert first
    assert second


@pytest.mark.skipif(
    not (REDIS_CONFIGURED and SMARTTRADE_CONFIGURED),
    reason="Redis or SmartTrade DB is not configured",
)
def test_list_low_stock_second_call_returns_cached(cache_bundle, inventory_repo):
    cache, _ = cache_bundle

    first = inventory_repo.list_low_stock(Decimal("1000"))
    second = inventory_repo.list_low_stock(Decimal("1000"))

    assert cache.get("bestbox:inv:lowstock:1000") is not None
    assert [stock.product_id for stock in first] == [
        stock.product_id for stock in second
    ]
