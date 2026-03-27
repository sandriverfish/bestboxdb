import pytest
from dotenv import load_dotenv
load_dotenv()
from decimal import Decimal
from datetime import datetime
from bestbox.core.domain.orders import OrderStatus, OrderItem, SalesOrder, PurchaseOrder
from bestbox.core.domain.inventory import InventoryStatus, InventoryLot, ProductStock


def _make_item(item_id=1):
    return OrderItem(
        item_id=item_id, line_no=item_id, product_id=10,
        part_number="P001", brand="TI", description="IC",
        qty_ordered=Decimal("100"), qty_shipped=Decimal("50"),
        qty_available=Decimal("200"), unit_price=1.5,
        delivery_date=datetime(2024, 3, 1),
        status=OrderStatus.PARTIAL,
    )


@pytest.fixture
def sample_sales_order():
    return SalesOrder(
        order_id=1, order_sn="SO2024-00001",
        order_date=datetime(2024, 1, 15), customer_id=42,
        customer_name="上海示例客户",
        currency="CNY", total_amount=150.0,
        delivery_date=datetime(2024, 3, 1),
        status=OrderStatus.PARTIAL, remark=None,
        items=[_make_item(1)],
    )


@pytest.fixture
def sample_purchase_order():
    return PurchaseOrder(
        order_id=1, order_sn="PO2024-00001",
        order_date=datetime(2024, 1, 15), supplier_id=10,
        supplier_name="深圳聚成达电子",
        currency="USD", total_amount=500.0,
        delivery_date=datetime(2024, 2, 15),
        status=OrderStatus.APPROVED,
        items=[_make_item(1)],
    )


@pytest.fixture
def sample_stock():
    lot = InventoryLot(
        lot_id=1, product_id=1, part_number="P001", brand="TI",
        quantity=Decimal("300"), stockroom_id=1,
        date_code="2401", unit_price=1.5,
        status=InventoryStatus.AVAILABLE,
    )
    return ProductStock(
        product_id=1, part_number="P001", brand="TI",
        total_qty=Decimal("300"), available_qty=Decimal("300"),
        on_order_qty=Decimal("100"), lots=[lot],
    )
