import logging

from fastapi import FastAPI
from bestbox.services.orders import OrderService
from bestbox.services.inventory import InventoryService
from bestbox.rest.routers import orders as orders_router_mod
from bestbox.rest.routers import inventory as inventory_router_mod

logger = logging.getLogger(__name__)


def _build_default_services() -> tuple[OrderService, InventoryService]:
    from bestbox.adapters.smarttrade.repositories.orders import (
        SmartTradeOrderRepository,
    )
    from bestbox.adapters.smarttrade.repositories.inventory import (
        SmartTradeInventoryRepository,
    )

    order_repo = SmartTradeOrderRepository()
    inventory_repo = SmartTradeInventoryRepository()

    try:
        from bestbox.adapters.cache.inventory import CachedInventoryRepository
        from bestbox.adapters.cache.orders import CachedOrderRepository
        from bestbox.adapters.cache.redis_cache import CacheConfig, RedisCache

        config = CacheConfig()
        cache = RedisCache(config)
        if cache.ping():
            order_repo = CachedOrderRepository(order_repo, cache, config)
            inventory_repo = CachedInventoryRepository(
                inventory_repo,
                cache,
                config,
            )
        else:
            logger.warning(
                "Redis unreachable at %s; running without cache",
                config.redis_url,
            )
    except (ImportError, TypeError, ValueError) as exc:
        logger.warning(
            "Redis cache initialization failed; running without cache: %s", exc
        )

    return OrderService(repo=order_repo), InventoryService(repo=inventory_repo)


def create_app(
    order_service: OrderService | None = None,
    inventory_service: InventoryService | None = None,
) -> FastAPI:
    application = FastAPI(title="BestBox ERP Gateway", version="0.1.0")

    if order_service is None or inventory_service is None:
        default_order_service, default_inventory_service = _build_default_services()
        if order_service is None:
            order_service = default_order_service
        if inventory_service is None:
            inventory_service = default_inventory_service

    orders_router_mod.set_service(order_service)
    inventory_router_mod.set_service(inventory_service)

    application.include_router(orders_router_mod.router, prefix="/api/v1")
    application.include_router(inventory_router_mod.router, prefix="/api/v1")

    return application


# Entry point for `uvicorn bestbox.rest.main:app`
try:
    app = create_app()
except (ImportError, TypeError, ValueError):
    app = None  # type: ignore[assignment]
