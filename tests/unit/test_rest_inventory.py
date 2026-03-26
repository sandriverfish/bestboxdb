import pytest
from httpx import AsyncClient, ASGITransport
from bestbox.rest.main import create_app
from bestbox.services.inventory import InventoryService
from decimal import Decimal


class MockInventoryRepo:
    def __init__(self, stock=None):
        self._stock = stock

    def get_product_stock(self, product_id):
        return self._stock if (self._stock and self._stock.product_id == product_id) else None

    def get_product_stock_by_part_number(self, part_number):
        return self._stock if (self._stock and self._stock.part_number == part_number) else None

    def list_low_stock(self, threshold):
        return [self._stock] if self._stock else []

    def list_lots(self, product_id):
        return self._stock.lots if self._stock else []


@pytest.mark.asyncio
async def test_get_stock_by_product_id(sample_stock):
    service = InventoryService(repo=MockInventoryRepo(stock=sample_stock))
    app = create_app(inventory_service=service)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/inventory/stock/1")
    assert response.status_code == 200
    assert response.json()["part_number"] == "P001"

@pytest.mark.asyncio
async def test_get_stock_by_part_number(sample_stock):
    service = InventoryService(repo=MockInventoryRepo(stock=sample_stock))
    app = create_app(inventory_service=service)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/inventory/stock/by-part/P001")
    assert response.status_code == 200
    assert response.json()["available_qty"] == "300"

@pytest.mark.asyncio
async def test_get_stock_not_found(sample_stock):
    service = InventoryService(repo=MockInventoryRepo(stock=sample_stock))
    app = create_app(inventory_service=service)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/inventory/stock/99")
    assert response.status_code == 404

@pytest.mark.asyncio
async def test_list_low_stock(sample_stock):
    service = InventoryService(repo=MockInventoryRepo(stock=sample_stock))
    app = create_app(inventory_service=service)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/inventory/low-stock?threshold=9999")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
