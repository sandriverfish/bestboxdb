from datetime import datetime
from decimal import Decimal
import pytest
from bestbox.core.domain.orders import (
    OrderStatus, OrderItem, SalesOrder, PurchaseOrder
)
from bestbox.services.orders import OrderService


def _make_item(item_id=1, qty_ordered=100, qty_shipped=0, status=OrderStatus.APPROVED):
    return OrderItem(
        item_id=item_id, line_no=item_id, product_id=10,
        part_number="P001", brand="TI", description="IC",
        qty_ordered=Decimal(str(qty_ordered)),
        qty_shipped=Decimal(str(qty_shipped)),
        qty_available=Decimal("50"),
        unit_price=1.0,
        delivery_date=datetime(2024, 3, 1),
        status=status,
    )


def _make_order(order_id=1, items=None, status=OrderStatus.APPROVED):
    return SalesOrder(
        order_id=order_id, order_sn=f"SO-{order_id:04d}",
        order_date=datetime(2024, 1, 1), customer_id=1,
        currency="CNY", total_amount=1000.0,
        delivery_date=datetime(2024, 3, 1),
        status=status, remark=None,
        items=items or [],
    )


class MockOrderRepository:
    def __init__(self, orders=None, purchase_orders=None):
        self._orders = {o.order_id: o for o in (orders or [])}
        self._pos = {o.order_id: o for o in (purchase_orders or [])}

    def get_sales_order(self, order_id):
        return self._orders.get(order_id)

    def list_sales_orders(self, customer_id=None, date_from=None,
                          date_to=None, status=None, limit=50):
        results = list(self._orders.values())
        if customer_id is not None:
            results = [o for o in results if o.customer_id == customer_id]
        return results[:limit]

    def get_purchase_order(self, order_id):
        return self._pos.get(order_id)

    def list_purchase_orders(self, supplier_id=None, date_from=None,
                             date_to=None, status=None, limit=50):
        return list(self._pos.values())[:limit]


def test_get_sales_order_found():
    order = _make_order(order_id=1)
    service = OrderService(repo=MockOrderRepository(orders=[order]))
    result = service.get_sales_order(1)
    assert result is not None
    assert result.order_id == 1

def test_get_sales_order_not_found():
    service = OrderService(repo=MockOrderRepository())
    assert service.get_sales_order(99) is None

def test_list_sales_orders_by_customer():
    orders = [_make_order(order_id=i) for i in range(1, 4)]
    service = OrderService(repo=MockOrderRepository(orders=orders))
    result = service.list_sales_orders(customer_id=1)
    assert len(result) == 3

def test_fulfillment_status_fully_shipped():
    items = [
        _make_item(item_id=1, qty_ordered=100, qty_shipped=100),
        _make_item(item_id=2, qty_ordered=50,  qty_shipped=50),
    ]
    order = _make_order(items=items)
    service = OrderService(repo=MockOrderRepository(orders=[order]))
    status = service.get_fulfillment_status(1)
    assert status["fulfilled_pct"] == 100.0

def test_fulfillment_status_partially_shipped():
    items = [
        _make_item(item_id=1, qty_ordered=100, qty_shipped=60),
        _make_item(item_id=2, qty_ordered=100, qty_shipped=0),
    ]
    order = _make_order(items=items)
    service = OrderService(repo=MockOrderRepository(orders=[order]))
    status = service.get_fulfillment_status(1)
    assert status["fulfilled_pct"] == 30.0

def test_fulfillment_status_order_not_found():
    service = OrderService(repo=MockOrderRepository())
    assert service.get_fulfillment_status(99) is None
