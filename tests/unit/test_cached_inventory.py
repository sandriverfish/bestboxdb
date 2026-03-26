import json
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock

from bestbox.adapters.cache.redis_cache import CacheConfig
from bestbox.core.domain.inventory import (
    InventoryLot,
    InventoryStatus,
    ProductStock,
)


def _make_lot(
    lot_id: int = 1, product_id: int = 10, quantity: int = 1000
) -> InventoryLot:
    return InventoryLot(
        lot_id=lot_id,
        product_id=product_id,
        part_number="GRM188",
        brand="Murata",
        quantity=Decimal(str(quantity)),
        stockroom_id=1,
        date_code=datetime(2026, 1, 1).strftime("%y%W"),
        unit_price=0.5,
        status=InventoryStatus.AVAILABLE,
    )


def _make_stock(product_id: int = 10, part_number: str = "GRM188") -> ProductStock:
    return ProductStock(
        product_id=product_id,
        part_number=part_number,
        brand="Murata",
        total_qty=Decimal("1000"),
        available_qty=Decimal("1000"),
        on_order_qty=Decimal("500"),
        lots=[_make_lot(product_id=product_id)],
    )


def _make_cache(hit_value=None):
    cache = MagicMock()
    cache.get.return_value = hit_value
    return cache


def _make_config() -> CacheConfig:
    config = CacheConfig()
    config.ttl_stock_sec = 120
    config.ttl_lots_sec = 120
    config.ttl_low_stock_sec = 300
    return config


def test_check_stock_cache_hit_skips_repo():
    from bestbox.adapters.cache.inventory import CachedInventoryRepository

    stock = _make_stock(part_number="GRM188")
    cache = _make_cache(hit_value=stock.model_dump_json())
    repo = MagicMock()

    cached_repo = CachedInventoryRepository(repo, cache, _make_config())
    result = cached_repo.get_product_stock_by_part_number("GRM188")

    assert result is not None
    assert result.part_number == "GRM188"
    repo.get_product_stock_by_part_number.assert_not_called()


def test_check_stock_cache_miss_calls_repo_and_stores():
    from bestbox.adapters.cache.inventory import CachedInventoryRepository

    stock = _make_stock(part_number="GRM188")
    cache = _make_cache(hit_value=None)
    repo = MagicMock()
    repo.get_product_stock_by_part_number.return_value = stock

    cached_repo = CachedInventoryRepository(repo, cache, _make_config())
    result = cached_repo.get_product_stock_by_part_number("GRM188")

    assert result is not None
    assert result.part_number == "GRM188"
    repo.get_product_stock_by_part_number.assert_called_once_with("GRM188")
    key, _, ttl = cache.set.call_args[0]
    assert key == "bestbox:inv:stock:GRM188"
    assert ttl == 120


def test_check_stock_not_found_does_not_cache():
    from bestbox.adapters.cache.inventory import CachedInventoryRepository

    cache = _make_cache(hit_value=None)
    repo = MagicMock()
    repo.get_product_stock_by_part_number.return_value = None

    cached_repo = CachedInventoryRepository(repo, cache, _make_config())

    assert cached_repo.get_product_stock_by_part_number("NOTFOUND") is None
    cache.set.assert_not_called()


def test_check_stock_cache_error_falls_back_to_repo():
    from bestbox.adapters.cache.inventory import CachedInventoryRepository

    stock = _make_stock(part_number="GRM188")
    cache = MagicMock()
    cache.get.side_effect = ConnectionError("redis down")
    repo = MagicMock()
    repo.get_product_stock_by_part_number.return_value = stock

    cached_repo = CachedInventoryRepository(repo, cache, _make_config())
    result = cached_repo.get_product_stock_by_part_number("GRM188")

    assert result is not None
    assert result.part_number == "GRM188"
    repo.get_product_stock_by_part_number.assert_called_once_with("GRM188")


def test_get_product_stock_cache_hit_skips_repo():
    from bestbox.adapters.cache.inventory import CachedInventoryRepository

    stock = _make_stock(product_id=42)
    cache = _make_cache(hit_value=stock.model_dump_json())
    repo = MagicMock()

    cached_repo = CachedInventoryRepository(repo, cache, _make_config())
    result = cached_repo.get_product_stock(42)

    assert result is not None
    assert result.product_id == 42
    repo.get_product_stock.assert_not_called()


def test_get_product_stock_cache_miss_calls_repo_and_stores():
    from bestbox.adapters.cache.inventory import CachedInventoryRepository

    stock = _make_stock(product_id=42)
    cache = _make_cache(hit_value=None)
    repo = MagicMock()
    repo.get_product_stock.return_value = stock

    cached_repo = CachedInventoryRepository(repo, cache, _make_config())
    result = cached_repo.get_product_stock(42)

    assert result is not None
    assert result.product_id == 42
    key, _, ttl = cache.set.call_args[0]
    assert key == "bestbox:inv:stock:id:42"
    assert ttl == 120


def test_list_lots_cache_hit_skips_repo():
    from bestbox.adapters.cache.inventory import CachedInventoryRepository

    lots = [_make_lot(lot_id=index, product_id=10) for index in range(1, 4)]
    cached_json = json.dumps([lot.model_dump(mode="json") for lot in lots])
    cache = _make_cache(hit_value=cached_json)
    repo = MagicMock()

    cached_repo = CachedInventoryRepository(repo, cache, _make_config())
    result = cached_repo.list_lots(10)

    assert len(result) == 3
    repo.list_lots.assert_not_called()


def test_list_lots_cache_miss_calls_repo_and_stores():
    from bestbox.adapters.cache.inventory import CachedInventoryRepository

    lots = [_make_lot(lot_id=index, product_id=10) for index in range(1, 3)]
    cache = _make_cache(hit_value=None)
    repo = MagicMock()
    repo.list_lots.return_value = lots

    cached_repo = CachedInventoryRepository(repo, cache, _make_config())
    result = cached_repo.list_lots(10)

    assert len(result) == 2
    key, _, ttl = cache.set.call_args[0]
    assert key == "bestbox:inv:lots:10"
    assert ttl == 120


def test_list_low_stock_cache_hit_skips_repo():
    from bestbox.adapters.cache.inventory import CachedInventoryRepository

    stocks = [_make_stock(product_id=index) for index in range(1, 4)]
    cached_json = json.dumps([stock.model_dump(mode="json") for stock in stocks])
    cache = _make_cache(hit_value=cached_json)
    repo = MagicMock()

    cached_repo = CachedInventoryRepository(repo, cache, _make_config())
    result = cached_repo.list_low_stock(Decimal("100"))

    assert len(result) == 3
    repo.list_low_stock.assert_not_called()


def test_list_low_stock_cache_miss_calls_repo_and_stores():
    from bestbox.adapters.cache.inventory import CachedInventoryRepository

    stocks = [_make_stock(product_id=index) for index in range(1, 3)]
    cache = _make_cache(hit_value=None)
    repo = MagicMock()
    repo.list_low_stock.return_value = stocks

    cached_repo = CachedInventoryRepository(repo, cache, _make_config())
    result = cached_repo.list_low_stock(Decimal("500"))

    assert len(result) == 2
    key, _, ttl = cache.set.call_args[0]
    assert key == "bestbox:inv:lowstock:500"
    assert ttl == 300
