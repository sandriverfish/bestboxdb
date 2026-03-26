import pytest
from bestbox.adapters.smarttrade.repositories.orders import SmartTradeOrderRepository
from bestbox.core.domain.orders import SalesOrder, PurchaseOrder, OrderStatus

pytestmark = pytest.mark.integration


@pytest.fixture
def repo():
    return SmartTradeOrderRepository()


def test_list_sales_orders_returns_results(repo):
    orders = repo.list_sales_orders(limit=5)
    assert isinstance(orders, list)
    assert len(orders) <= 5
    for o in orders:
        assert isinstance(o, SalesOrder)
        assert o.order_id > 0
        assert o.order_sn != ""

def test_get_sales_order_with_items(repo):
    orders = repo.list_sales_orders(limit=1)
    assert orders, "No orders in DB — cannot test"
    order = repo.get_sales_order(orders[0].order_id)
    assert order is not None
    assert order.order_id == orders[0].order_id
    assert isinstance(order.items, list)

def test_get_sales_order_not_found(repo):
    result = repo.get_sales_order(-1)
    assert result is None

def test_sales_order_status_is_valid_enum(repo):
    orders = repo.list_sales_orders(limit=10)
    for o in orders:
        assert o.status in list(OrderStatus)

def test_list_purchase_orders_returns_results(repo):
    orders = repo.list_purchase_orders(limit=5)
    assert isinstance(orders, list)
    for o in orders:
        assert isinstance(o, PurchaseOrder)
        assert o.order_id > 0

def test_get_purchase_order_with_items(repo):
    orders = repo.list_purchase_orders(limit=1)
    assert orders, "No purchase orders in DB"
    po = repo.get_purchase_order(orders[0].order_id)
    assert po is not None
    assert isinstance(po.items, list)
