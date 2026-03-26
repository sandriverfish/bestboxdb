import pytest
from decimal import Decimal
from bestbox.adapters.smarttrade.repositories.inventory import SmartTradeInventoryRepository
from bestbox.core.domain.inventory import ProductStock, InventoryLot, InventoryStatus

pytestmark = pytest.mark.integration


@pytest.fixture
def repo():
    return SmartTradeInventoryRepository()


def test_list_lots_returns_results(repo):
    # Get a product_id that has inventory by querying DB directly
    from bestbox.adapters.smarttrade.db.connection import get_connection
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT TOP 1 piProductID FROM ProductInventory WHERE piQty > 0")
        row = cursor.fetchone()
    if not row:
        pytest.skip("No inventory in DB")
    product_id = row[0]
    lots = repo.list_lots(product_id=product_id)
    assert isinstance(lots, list)
    assert len(lots) > 0
    for lot in lots:
        assert isinstance(lot, InventoryLot)
        assert lot.quantity >= 0

def test_get_product_stock_aggregates_lots(repo):
    from bestbox.adapters.smarttrade.db.connection import get_connection
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT TOP 1 piProductID FROM ProductInventory WHERE piQty > 0")
        row = cursor.fetchone()
    if not row:
        pytest.skip("No inventory in DB")
    stock = repo.get_product_stock(product_id=row[0])
    assert stock is not None
    assert isinstance(stock, ProductStock)
    assert stock.total_qty == sum(l.quantity for l in stock.lots)

def test_get_product_stock_not_found(repo):
    result = repo.get_product_stock(product_id=-1)
    assert result is None

def test_get_product_stock_by_part_number(repo):
    from bestbox.adapters.smarttrade.db.connection import get_connection
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT TOP 1 piPartNumber FROM ProductInventory WHERE piPartNumber IS NOT NULL AND piPartNumber != '' AND piQty > 0")
        row = cursor.fetchone()
    if not row:
        pytest.skip("No part numbers in ProductInventory")
    part_number = row[0]
    stock = repo.get_product_stock_by_part_number(part_number)
    assert stock is not None
    assert stock.part_number == part_number

def test_list_low_stock_returns_products_below_threshold(repo):
    results = repo.list_low_stock(threshold=Decimal("9999999"))
    assert isinstance(results, list)
    for s in results:
        assert s.available_qty < Decimal("9999999")

def test_on_order_qty_is_non_negative(repo):
    from bestbox.adapters.smarttrade.db.connection import get_connection
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT TOP 1 piProductID FROM ProductInventory WHERE piQty > 0")
        row = cursor.fetchone()
    if not row:
        pytest.skip("No inventory in DB")
    stock = repo.get_product_stock(product_id=row[0])
    assert stock is not None
    assert stock.on_order_qty >= 0
