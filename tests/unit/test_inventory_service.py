from decimal import Decimal
import pytest
from bestbox.core.domain.inventory import (
    InventoryStatus, InventoryLot, ProductStock
)
from bestbox.services.inventory import InventoryService


def _make_lot(lot_id, qty, status=InventoryStatus.AVAILABLE):
    return InventoryLot(
        lot_id=lot_id, product_id=1, part_number="P001", brand="TI",
        quantity=Decimal(str(qty)), stockroom_id=1,
        date_code="2401", unit_price=1.5, status=status,
    )


class MockInventoryRepository:
    def __init__(self, stocks=None):
        self._stocks = {s.product_id: s for s in (stocks or [])}
        self._by_part = {s.part_number: s for s in (stocks or []) if s.part_number}

    def get_product_stock(self, product_id):
        return self._stocks.get(product_id)

    def get_product_stock_by_part_number(self, part_number):
        return self._by_part.get(part_number)

    def list_low_stock(self, threshold):
        return [s for s in self._stocks.values() if s.available_qty < threshold]

    def list_lots(self, product_id):
        s = self._stocks.get(product_id)
        return s.lots if s else []


def test_get_stock_summary_by_part_number():
    lots = [
        _make_lot(1, 200, InventoryStatus.AVAILABLE),
        _make_lot(2, 100, InventoryStatus.HELD),
    ]
    stock = ProductStock(
        product_id=1, part_number="P001", brand="TI",
        total_qty=Decimal("300"), available_qty=Decimal("200"),
        on_order_qty=Decimal("50"), lots=lots,
    )
    service = InventoryService(repo=MockInventoryRepository(stocks=[stock]))
    result = service.get_stock_summary("P001")
    assert result is not None
    assert result.available_qty == Decimal("200")

def test_get_stock_summary_not_found():
    service = InventoryService(repo=MockInventoryRepository())
    assert service.get_stock_summary("UNKNOWN") is None

def test_list_low_stock():
    stocks = [
        ProductStock(product_id=1, part_number="P001", brand="TI",
                     total_qty=Decimal("10"), available_qty=Decimal("5"),
                     on_order_qty=Decimal("0")),
        ProductStock(product_id=2, part_number="P002", brand="ST",
                     total_qty=Decimal("500"), available_qty=Decimal("400"),
                     on_order_qty=Decimal("0")),
    ]
    service = InventoryService(repo=MockInventoryRepository(stocks=stocks))
    result = service.list_low_stock(threshold=Decimal("100"))
    assert len(result) == 1
    assert result[0].part_number == "P001"

def test_available_qty_excludes_held_lots():
    lots = [
        _make_lot(1, 300, InventoryStatus.AVAILABLE),
        _make_lot(2, 100, InventoryStatus.HELD),
        _make_lot(3, 50,  InventoryStatus.QUARANTINE),
    ]
    stock = ProductStock(
        product_id=1, part_number="P001", brand="TI",
        total_qty=Decimal("450"), available_qty=Decimal("0"),
        on_order_qty=Decimal("0"), lots=lots,
    )
    service = InventoryService(repo=MockInventoryRepository(stocks=[stock]))
    result = service.get_stock_summary("P001")
    # Service recomputes available_qty from lot statuses
    assert result.available_qty == Decimal("300")
