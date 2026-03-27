from decimal import Decimal
from fastapi import APIRouter, HTTPException, Query
from bestbox.services.inventory import InventoryService

router = APIRouter(prefix="/inventory", tags=["inventory"])
_service: InventoryService | None = None


def set_service(service: InventoryService):
    global _service
    _service = service


@router.get("/stock/{product_id}")
def get_stock_by_product(product_id: int):
    stock = _service.get_stock_by_product_id(product_id)
    if stock is None:
        raise HTTPException(status_code=404, detail="Product not found in inventory")
    return stock.model_dump(mode="json")


@router.get("/stock/by-part/{part_number}")
def get_stock_by_part_number(part_number: str):
    stock = _service.get_stock_summary(part_number)
    if stock is None:
        raise HTTPException(status_code=404, detail="Part number not found in inventory")
    return stock.model_dump(mode="json")


@router.get("/low-stock")
def list_low_stock(threshold: Decimal = Query(default=Decimal("10"))):
    return [s.model_dump(mode="json") for s in _service.list_low_stock(threshold)]


@router.get("/lots/{product_id}")
def list_lots(product_id: int):
    return [l.model_dump(mode="json") for l in _service.list_lots(product_id)]


@router.get("/price-history/{part_number}")
def get_price_history_endpoint(part_number: str, months: int = 6):
    """Monthly purchase price history for a part number."""
    from bestbox.adapters.smarttrade.db.connection import get_connection

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT FORMAT(po.poOrderDate, 'yyyy-MM') AS month,
                   AVG(CAST(poi.poiPrice AS FLOAT)) AS avg_price,
                   MIN(poi.poiPrice) AS min_price,
                   MAX(poi.poiPrice) AS max_price,
                   COUNT(*) AS order_count
            FROM PurchaseOrderItem poi
            JOIN PurchaseOrder po ON poi.poiOrderID = po.poOrderID
            WHERE poi.poiPartNumber = ?
              AND po.poOrderDate >= DATEADD(MONTH, -?, GETDATE())
              AND poi.poiPrice > 0
            GROUP BY FORMAT(po.poOrderDate, 'yyyy-MM')
            ORDER BY month ASC
            """,
            part_number,
            months,
        )
        rows = cursor.fetchall()

    return [
        {
            "month": r.month,
            "avg_price": round(r.avg_price, 4) if r.avg_price else None,
            "min_price": float(r.min_price) if r.min_price else None,
            "max_price": float(r.max_price) if r.max_price else None,
            "order_count": r.order_count,
        }
        for r in rows
    ]


@router.get("/search")
def search_products_endpoint(q: str, limit: int = 20):
    """Search products by part number, brand, or description."""
    from bestbox.adapters.smarttrade.db.connection import get_connection

    with get_connection() as conn:
        cursor = conn.cursor()
        pattern = f"%{q}%"
        cursor.execute(
            """
            SELECT TOP (?)
                sub.part_number, sub.brand, sub.description,
                ISNULL(inv.available_qty, 0) AS available_qty,
                sub.last_price
            FROM (
                SELECT poiPartNumber AS part_number,
                       poiBrand AS brand,
                       poiAllDesc AS description,
                       MAX(poiPrice) AS last_price
                FROM PurchaseOrderItem
                WHERE (poiPartNumber LIKE ? OR poiBrand LIKE ? OR poiAllDesc LIKE ?)
                  AND poiPrice > 0
                GROUP BY poiPartNumber, poiBrand, poiAllDesc
            ) sub
            LEFT JOIN (
                SELECT piPartNumber,
                       SUM(CASE WHEN piInventoryStatus = 1 THEN piQty ELSE 0 END)
                           AS available_qty
                FROM ProductInventory
                GROUP BY piPartNumber
            ) inv ON sub.part_number = inv.piPartNumber
            ORDER BY sub.last_price DESC
            """,
            min(limit, 50),
            pattern,
            pattern,
            pattern,
        )
        rows = cursor.fetchall()

    return [
        {
            "part_number": r.part_number,
            "brand": r.brand,
            "description": r.description,
            "available_qty": float(r.available_qty or 0),
            "last_price": float(r.last_price) if r.last_price else None,
        }
        for r in rows
    ]
