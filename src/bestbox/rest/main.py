from fastapi import FastAPI
from bestbox.services.orders import OrderService
from bestbox.services.inventory import InventoryService
from bestbox.rest.routers import orders as orders_router_mod
from bestbox.rest.routers import inventory as inventory_router_mod


def create_app(
    order_service: OrderService | None = None,
    inventory_service: InventoryService | None = None,
) -> FastAPI:
    app = FastAPI(title="BestBox ERP Gateway", version="0.1.0")

    if order_service is None:
        from bestbox.adapters.smarttrade.repositories.orders import SmartTradeOrderRepository
        order_service = OrderService(repo=SmartTradeOrderRepository())

    if inventory_service is None:
        from bestbox.adapters.smarttrade.repositories.inventory import SmartTradeInventoryRepository
        inventory_service = InventoryService(repo=SmartTradeInventoryRepository())

    orders_router_mod.set_service(order_service)
    inventory_router_mod.set_service(inventory_service)

    app.include_router(orders_router_mod.router, prefix="/api/v1")
    app.include_router(inventory_router_mod.router, prefix="/api/v1")

    return app


# Entry point for `uvicorn bestbox.rest.main:app`
try:
    app = create_app()
except Exception:
    app = None  # type: ignore[assignment]
