from decimal import Decimal
from datetime import datetime
from bestbox.core.domain.orders import (
    OrderStatus, OrderItem, SalesOrder, PurchaseOrder
)

def test_order_status_values():
    assert OrderStatus.PENDING == 0
    assert OrderStatus.APPROVED == 1
    assert OrderStatus.PARTIAL == 2
    assert OrderStatus.FULFILLED == 3
    assert OrderStatus.CANCELLED == 4

def test_sales_order_defaults():
    order = SalesOrder(
        order_id=1,
        order_sn="SO2024-00001",
        order_date=datetime(2024, 1, 15),
        customer_id=42,
        currency="CNY",
        total_amount=10000.0,
        delivery_date=None,
        status=OrderStatus.APPROVED,
        remark=None,
    )
    assert order.items == []
    assert order.total_amount == 10000.0

def test_sales_order_with_items():
    item = OrderItem(
        item_id=1, line_no=1, product_id=100,
        part_number="ABC123", brand="TI", description="IC",
        qty_ordered=Decimal("100"), qty_shipped=Decimal("0"),
        qty_available=Decimal("200"),
        unit_price=1.5,
        delivery_date=datetime(2024, 2, 1),
        status=OrderStatus.APPROVED,
    )
    order = SalesOrder(
        order_id=1, order_sn="SO2024-00001",
        order_date=datetime(2024, 1, 15), customer_id=42,
        currency="CNY", total_amount=150.0,
        delivery_date=None, status=OrderStatus.APPROVED,
        remark=None, items=[item],
    )
    assert len(order.items) == 1
    assert order.items[0].part_number == "ABC123"

def test_purchase_order_serializes():
    po = PurchaseOrder(
        order_id=1, order_sn="PO2024-00001",
        order_date=datetime(2024, 1, 15), supplier_id=10,
        currency="USD", total_amount=500.0,
        delivery_date=datetime(2024, 2, 15),
        status=OrderStatus.PENDING,
    )
    data = po.model_dump()
    assert data["order_sn"] == "PO2024-00001"
    assert data["status"] == OrderStatus.PENDING


def test_purchase_order_supplier_name_defaults_to_none():
    po = PurchaseOrder(
        order_id=1, order_sn="PO-001",
        order_date=datetime(2024, 1, 15), supplier_id=10,
        currency="USD", total_amount=500.0,
        delivery_date=None, status=OrderStatus.PENDING,
    )
    assert po.supplier_name is None


def test_purchase_order_supplier_name_populated():
    po = PurchaseOrder(
        order_id=1, order_sn="PO-001",
        order_date=datetime(2024, 1, 15), supplier_id=10,
        supplier_name="深圳聚成达电子",
        currency="USD", total_amount=500.0,
        delivery_date=None, status=OrderStatus.PENDING,
    )
    assert po.supplier_name == "深圳聚成达电子"
    data = po.model_dump()
    assert data["supplier_name"] == "深圳聚成达电子"


def test_sales_order_customer_name_defaults_to_none():
    so = SalesOrder(
        order_id=1, order_sn="SO-001",
        order_date=datetime(2024, 1, 15), customer_id=42,
        currency="CNY", total_amount=1000.0,
        delivery_date=None, status=OrderStatus.PENDING, remark=None,
    )
    assert so.customer_name is None


def test_sales_order_customer_name_populated():
    so = SalesOrder(
        order_id=1, order_sn="SO-001",
        order_date=datetime(2024, 1, 15), customer_id=42,
        customer_name="上海示例客户",
        currency="CNY", total_amount=1000.0,
        delivery_date=None, status=OrderStatus.PENDING, remark=None,
    )
    assert so.customer_name == "上海示例客户"
    data = so.model_dump()
    assert data["customer_name"] == "上海示例客户"
