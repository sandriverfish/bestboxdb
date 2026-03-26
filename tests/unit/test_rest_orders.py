import pytest
from httpx import AsyncClient, ASGITransport
from bestbox.rest.main import create_app
from bestbox.services.orders import OrderService


class MockOrderRepo:
    def __init__(self, order=None, po=None):
        self._order = order
        self._po = po

    def get_sales_order(self, order_id):
        return self._order if (self._order and self._order.order_id == order_id) else None

    def list_sales_orders(self, **kwargs):
        return [self._order] if self._order else []

    def get_purchase_order(self, order_id):
        return self._po if (self._po and self._po.order_id == order_id) else None

    def list_purchase_orders(self, **kwargs):
        return [self._po] if self._po else []


@pytest.mark.asyncio
async def test_get_sales_order_found(sample_sales_order):
    service = OrderService(repo=MockOrderRepo(order=sample_sales_order))
    app = create_app(order_service=service)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/orders/sales/1")
    assert response.status_code == 200
    data = response.json()
    assert data["order_id"] == 1
    assert data["order_sn"] == "SO2024-00001"
    assert len(data["items"]) == 1

@pytest.mark.asyncio
async def test_get_sales_order_not_found(sample_sales_order):
    service = OrderService(repo=MockOrderRepo(order=sample_sales_order))
    app = create_app(order_service=service)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/orders/sales/99")
    assert response.status_code == 404

@pytest.mark.asyncio
async def test_list_sales_orders(sample_sales_order):
    service = OrderService(repo=MockOrderRepo(order=sample_sales_order))
    app = create_app(order_service=service)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/orders/sales")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

@pytest.mark.asyncio
async def test_get_purchase_order_found(sample_purchase_order):
    service = OrderService(repo=MockOrderRepo(po=sample_purchase_order))
    app = create_app(order_service=service)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/orders/purchases/1")
    assert response.status_code == 200
    assert response.json()["supplier_id"] == 10
