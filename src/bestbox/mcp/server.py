from decimal import Decimal
from mcp.server.fastmcp import FastMCP
from bestbox.adapters.smarttrade.repositories.orders import SmartTradeOrderRepository
from bestbox.adapters.smarttrade.repositories.inventory import SmartTradeInventoryRepository
from bestbox.services.orders import OrderService
from bestbox.services.inventory import InventoryService

mcp = FastMCP("BestBox")

_order_service = OrderService(repo=SmartTradeOrderRepository())
_inventory_service = InventoryService(repo=SmartTradeInventoryRepository())


@mcp.tool()
def get_sales_order(order_id: int) -> dict:
    """Get a sales order with all line items by order ID."""
    order = _order_service.get_sales_order(order_id)
    return order.model_dump() if order else {}


@mcp.tool()
def list_sales_orders(
    customer_id: int | None = None,
    date_from:   str | None = None,
    date_to:     str | None = None,
    status:      int | None = None,
    limit:       int = 20,
) -> list[dict]:
    """List sales orders with optional filters by customer ID, date range (ISO format), or status (0=Pending,1=Approved,2=Partial,3=Fulfilled,4=Cancelled)."""
    from datetime import datetime
    df = datetime.fromisoformat(date_from) if date_from else None
    dt = datetime.fromisoformat(date_to)   if date_to   else None
    orders = _order_service.list_sales_orders(
        customer_id=customer_id, date_from=df, date_to=dt,
        status=status, limit=min(limit, 100),
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
    date_from:   str | None = None,
    date_to:     str | None = None,
    limit:       int = 20,
) -> list[dict]:
    """List purchase orders with optional filters by supplier ID and date range (ISO format)."""
    from datetime import datetime
    df = datetime.fromisoformat(date_from) if date_from else None
    dt = datetime.fromisoformat(date_to)   if date_to   else None
    orders = _order_service.list_purchase_orders(
        supplier_id=supplier_id, date_from=df, date_to=dt,
        limit=min(limit, 100),
    )
    return [o.model_dump() for o in orders]


@mcp.tool()
def check_stock(part_number: str) -> dict:
    """Get available inventory quantity for a part number. Returns total_qty, available_qty (excludes held/quarantine), and on_order_qty from open purchase orders."""
    stock = _inventory_service.get_stock_summary(part_number)
    return stock.model_dump() if stock else {"available_qty": 0, "total_qty": 0, "on_order_qty": 0}


@mcp.tool()
def list_low_stock(threshold: float = 10.0) -> list[dict]:
    """List products with available inventory quantity below the given threshold."""
    stocks = _inventory_service.list_low_stock(Decimal(str(threshold)))
    return [s.model_dump() for s in stocks]


@mcp.tool()
def get_inventory_lots(product_id: int) -> list[dict]:
    """Get individual inventory lot details for a product, including lot ID, quantity, date code, stockroom, and status."""
    lots = _inventory_service.list_lots(product_id)
    return [l.model_dump() for l in lots]
