import json
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock

from bestbox.adapters.cache.redis_cache import CacheConfig
from bestbox.core.domain.orders import (
    OrderItem,
    OrderStatus,
    PurchaseOrder,
    SalesOrder,
)


def _make_item(item_id: int = 1) -> OrderItem:
    return OrderItem(
        item_id=item_id,
        line_no=item_id,
        product_id=10,
        part_number="P001",
        brand="TI",
        description="IC",
        qty_ordered=Decimal("100"),
        qty_shipped=Decimal("0"),
        qty_available=Decimal("50"),
        unit_price=1.0,
        delivery_date=datetime(2026, 3, 1),
        status=OrderStatus.APPROVED,
    )


def _make_sales_order(order_id: int = 1) -> SalesOrder:
    return SalesOrder(
        order_id=order_id,
        order_sn=f"SO-{order_id:04d}",
        order_date=datetime(2026, 1, 1),
        customer_id=1,
        currency="CNY",
        total_amount=100.0,
        delivery_date=datetime(2026, 3, 1),
        status=OrderStatus.APPROVED,
        remark=None,
        items=[_make_item()],
    )


def _make_purchase_order(order_id: int = 1) -> PurchaseOrder:
    return PurchaseOrder(
        order_id=order_id,
        order_sn=f"PO-{order_id:04d}",
        order_date=datetime(2026, 1, 1),
        supplier_id=5,
        currency="CNY",
        total_amount=100.0,
        delivery_date=datetime(2026, 3, 1),
        status=OrderStatus.APPROVED,
        items=[],
    )


def _make_cache(hit_value=None):
    cache = MagicMock()
    cache.get.return_value = hit_value
    return cache


def _make_config() -> CacheConfig:
    config = CacheConfig()
    config.ttl_sales_order_sec = 60
    config.ttl_sales_order_list_sec = 180
    config.ttl_purchase_order_sec = 300
    config.ttl_purchase_order_list_sec = 300
    return config


def test_get_sales_order_cache_hit_skips_repo():
    from bestbox.adapters.cache.orders import CachedOrderRepository

    order = _make_sales_order(order_id=42)
    cache = _make_cache(hit_value=order.model_dump_json())
    repo = MagicMock()

    cached_repo = CachedOrderRepository(repo, cache, _make_config())
    result = cached_repo.get_sales_order(42)

    assert result is not None
    assert result.order_id == 42
    repo.get_sales_order.assert_not_called()


def test_get_sales_order_cache_miss_calls_repo_and_stores():
    from bestbox.adapters.cache.orders import CachedOrderRepository

    order = _make_sales_order(order_id=42)
    cache = _make_cache(hit_value=None)
    repo = MagicMock()
    repo.get_sales_order.return_value = order

    cached_repo = CachedOrderRepository(repo, cache, _make_config())
    result = cached_repo.get_sales_order(42)

    assert result is not None
    assert result.order_id == 42
    repo.get_sales_order.assert_called_once_with(42)
    cache.set.assert_called_once()
    key, value, ttl = cache.set.call_args[0]
    assert key == "bestbox:so:42"
    assert ttl == 60
    assert json.loads(value)["order_id"] == 42


def test_get_sales_order_not_found_does_not_cache():
    from bestbox.adapters.cache.orders import CachedOrderRepository

    cache = _make_cache(hit_value=None)
    repo = MagicMock()
    repo.get_sales_order.return_value = None

    cached_repo = CachedOrderRepository(repo, cache, _make_config())

    assert cached_repo.get_sales_order(99) is None
    cache.set.assert_not_called()


def test_get_sales_order_cache_error_falls_back_to_repo():
    from bestbox.adapters.cache.orders import CachedOrderRepository

    order = _make_sales_order(order_id=42)
    cache = MagicMock()
    cache.get.side_effect = ConnectionError("redis down")
    repo = MagicMock()
    repo.get_sales_order.return_value = order

    cached_repo = CachedOrderRepository(repo, cache, _make_config())
    result = cached_repo.get_sales_order(42)

    assert result is not None
    assert result.order_id == 42
    repo.get_sales_order.assert_called_once_with(42)


def test_list_sales_orders_cache_hit_skips_repo():
    from bestbox.adapters.cache.orders import CachedOrderRepository

    orders = [_make_sales_order(index) for index in range(1, 4)]
    cached_json = json.dumps([order.model_dump(mode="json") for order in orders])
    cache = _make_cache(hit_value=cached_json)
    repo = MagicMock()

    cached_repo = CachedOrderRepository(repo, cache, _make_config())
    result = cached_repo.list_sales_orders(limit=20)

    assert len(result) == 3
    repo.list_sales_orders.assert_not_called()


def test_list_sales_orders_cache_miss_calls_repo_and_stores():
    from bestbox.adapters.cache.orders import CachedOrderRepository

    orders = [_make_sales_order(index) for index in range(1, 3)]
    cache = _make_cache(hit_value=None)
    repo = MagicMock()
    repo.list_sales_orders.return_value = orders

    cached_repo = CachedOrderRepository(repo, cache, _make_config())
    result = cached_repo.list_sales_orders(customer_id=1, limit=10)

    assert len(result) == 2
    repo.list_sales_orders.assert_called_once_with(
        customer_id=1,
        date_from=None,
        date_to=None,
        status=None,
        limit=10,
    )
    key, _, ttl = cache.set.call_args[0]
    assert key.startswith("bestbox:so:list:")
    assert ttl == 180


def test_list_sales_orders_different_params_different_keys():
    from bestbox.adapters.cache.orders import _list_cache_key

    key_one = _list_cache_key("bestbox:so:list", {"customer_id": 1, "limit": 20})
    key_two = _list_cache_key("bestbox:so:list", {"customer_id": 2, "limit": 20})

    assert key_one != key_two


def test_get_purchase_order_cache_hit_skips_repo():
    from bestbox.adapters.cache.orders import CachedOrderRepository

    order = _make_purchase_order(order_id=7)
    cache = _make_cache(hit_value=order.model_dump_json())
    repo = MagicMock()

    cached_repo = CachedOrderRepository(repo, cache, _make_config())
    result = cached_repo.get_purchase_order(7)

    assert result is not None
    assert result.order_id == 7
    repo.get_purchase_order.assert_not_called()


def test_get_purchase_order_cache_miss_calls_repo_and_stores():
    from bestbox.adapters.cache.orders import CachedOrderRepository

    order = _make_purchase_order(order_id=7)
    cache = _make_cache(hit_value=None)
    repo = MagicMock()
    repo.get_purchase_order.return_value = order

    cached_repo = CachedOrderRepository(repo, cache, _make_config())
    result = cached_repo.get_purchase_order(7)

    assert result is not None
    assert result.order_id == 7
    key, _, ttl = cache.set.call_args[0]
    assert key == "bestbox:po:7"
    assert ttl == 300


def test_list_purchase_orders_cache_hit_skips_repo():
    from bestbox.adapters.cache.orders import CachedOrderRepository

    orders = [_make_purchase_order(index) for index in range(1, 3)]
    cached_json = json.dumps([order.model_dump(mode="json") for order in orders])
    cache = _make_cache(hit_value=cached_json)
    repo = MagicMock()

    cached_repo = CachedOrderRepository(repo, cache, _make_config())
    result = cached_repo.list_purchase_orders(limit=10)

    assert len(result) == 2
    repo.list_purchase_orders.assert_not_called()


def test_list_purchase_orders_cache_miss_calls_repo_and_stores():
    from bestbox.adapters.cache.orders import CachedOrderRepository

    orders = [_make_purchase_order(index) for index in range(1, 3)]
    cache = _make_cache(hit_value=None)
    repo = MagicMock()
    repo.list_purchase_orders.return_value = orders

    cached_repo = CachedOrderRepository(repo, cache, _make_config())
    result = cached_repo.list_purchase_orders(supplier_id=5, limit=10)

    assert len(result) == 2
    repo.list_purchase_orders.assert_called_once_with(
        supplier_id=5,
        date_from=None,
        date_to=None,
        status=None,
        limit=10,
    )
    key, _, ttl = cache.set.call_args[0]
    assert key.startswith("bestbox:po:list:")
    assert ttl == 300
