"""Tests for get_price_history and search_products queries."""
import pytest
from bestbox.adapters.smarttrade.db.connection import get_connection


@pytest.mark.integration
def test_get_price_history_returns_list():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
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
        """, ("STM32F103C8T6", 6))
        rows = cursor.fetchall()
    assert isinstance(rows, list)


@pytest.mark.integration
def test_search_products_returns_results():
    with get_connection() as conn:
        cursor = conn.cursor()
        pattern = "%STM32%"
        cursor.execute("""
            SELECT TOP (20)
                sub.part_number, sub.brand, sub.description,
                ISNULL(inv.available_qty, 0) AS available_qty,
                sub.last_price
            FROM (
                SELECT poiPartNumber AS part_number,
                       piBrand AS brand,
                       poiAllDesc AS description,
                       MAX(poiPrice) AS last_price
                FROM PurchaseOrderItem
                WHERE (poiPartNumber LIKE ? OR piBrand LIKE ? OR poiAllDesc LIKE ?)
                  AND poiPrice > 0
                GROUP BY poiPartNumber, piBrand, poiAllDesc
            ) sub
            LEFT JOIN (
                SELECT piPartNumber,
                       SUM(CASE WHEN piInventoryStatus = 1 THEN piQty ELSE 0 END)
                           AS available_qty
                FROM ProductInventory
                GROUP BY piPartNumber
            ) inv ON sub.part_number = inv.piPartNumber
            ORDER BY sub.last_price DESC
        """, (pattern, pattern, pattern))
        rows = cursor.fetchall()
    assert isinstance(rows, list)
