import logging
from decimal import Decimal

from mcp.server.fastmcp import FastMCP
from bestbox.services.orders import OrderService
from bestbox.services.inventory import InventoryService

logger = logging.getLogger(__name__)

mcp = FastMCP("BestBox")


def _build_services() -> tuple[OrderService, InventoryService]:
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


_order_service, _inventory_service = _build_services()


@mcp.tool()
def get_sales_order(order_id: int) -> dict:
    """Get a sales order with all line items by order ID."""
    order = _order_service.get_sales_order(order_id)
    return order.model_dump() if order else {}


@mcp.tool()
def list_sales_orders(
    customer_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    status: int | None = None,
    limit: int = 20,
) -> list[dict]:
    """List sales orders with optional customer, date, and status filters."""
    from datetime import datetime

    df = datetime.fromisoformat(date_from) if date_from else None
    dt = datetime.fromisoformat(date_to) if date_to else None
    orders = _order_service.list_sales_orders(
        customer_id=customer_id,
        date_from=df,
        date_to=dt,
        status=status,
        limit=min(limit, 100),
    )
    return [o.model_dump() for o in orders]


@mcp.tool()
def get_purchase_order(order_id: int) -> dict:
    """Get a purchase order with all line items by order ID."""
    order = _order_service.get_purchase_order(order_id)
    return order.model_dump() if order else {}


@mcp.tool()
def list_purchase_orders(
    supplier_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 20,
) -> list[dict]:
    """List purchase orders with optional supplier and date filters."""
    from datetime import datetime

    df = datetime.fromisoformat(date_from) if date_from else None
    dt = datetime.fromisoformat(date_to) if date_to else None
    orders = _order_service.list_purchase_orders(
        supplier_id=supplier_id,
        date_from=df,
        date_to=dt,
        limit=min(limit, 100),
    )
    return [o.model_dump() for o in orders]


@mcp.tool()
def check_stock(part_number: str) -> dict:
    """Get inventory summary for a part number."""
    stock = _inventory_service.get_stock_summary(part_number)
    return (
        stock.model_dump()
        if stock
        else {"available_qty": 0, "total_qty": 0, "on_order_qty": 0}
    )


@mcp.tool()
def list_low_stock(threshold: float = 10.0) -> list[dict]:
    """List products with available quantity below the threshold."""
    stocks = _inventory_service.list_low_stock(Decimal(str(threshold)))
    return [s.model_dump() for s in stocks]


@mcp.tool()
def get_inventory_lots(product_id: int) -> list[dict]:
    """Get inventory lot details for a product."""
    lots = _inventory_service.list_lots(product_id)
    return [lot.model_dump() for lot in lots]


if __name__ == "__main__":
    import os
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    if transport == "sse":
        mcp.settings.host = os.environ.get("FASTMCP_HOST", "0.0.0.0")
        mcp.settings.port = int(os.environ.get("FASTMCP_PORT", "8001"))
        mcp.settings.transport_security = None  # allow remote access; host is not localhost
    mcp.run(transport=transport)
