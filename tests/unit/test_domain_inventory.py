from decimal import Decimal
from bestbox.core.domain.inventory import (
    InventoryStatus, InventoryLot, ProductStock
)

def test_inventory_status_values():
    assert InventoryStatus.AVAILABLE  == 1
    assert InventoryStatus.HELD       == 2
    assert InventoryStatus.QUARANTINE == 3
    assert InventoryStatus.LOCKED     == 4

def test_product_stock_defaults():
    stock = ProductStock(
        product_id=1, part_number="ABC123", brand="TI",
        total_qty=Decimal("500"), available_qty=Decimal("400"),
        on_order_qty=Decimal("100"),
    )
    assert stock.lots == []

def test_product_stock_with_lots():
    lot = InventoryLot(
        lot_id=1, product_id=1, part_number="ABC123", brand="TI",
        quantity=Decimal("200"), stockroom_id=1,
        date_code="2401", unit_price=1.5,
        status=InventoryStatus.AVAILABLE,
    )
    stock = ProductStock(
        product_id=1, part_number="ABC123", brand="TI",
        total_qty=Decimal("200"), available_qty=Decimal("200"),
        on_order_qty=Decimal("0"), lots=[lot],
    )
    assert len(stock.lots) == 1
    assert stock.lots[0].status == InventoryStatus.AVAILABLE

def test_inventory_lot_serializes():
    lot = InventoryLot(
        lot_id=5, product_id=2, part_number=None, brand=None,
        quantity=Decimal("50"), stockroom_id=2,
        date_code=None, unit_price=None,
        status=InventoryStatus.HELD,
    )
    data = lot.model_dump()
    assert data["status"] == InventoryStatus.HELD
    assert data["part_number"] is None
