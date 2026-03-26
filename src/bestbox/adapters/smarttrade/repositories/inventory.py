from decimal import Decimal
from bestbox.adapters.smarttrade.db.connection import get_connection
from bestbox.core.domain.inventory import (
    InventoryStatus, InventoryLot, ProductStock
)

_STATUS_MAP = {
    1: InventoryStatus.AVAILABLE,
    2: InventoryStatus.HELD,
    3: InventoryStatus.QUARANTINE,
    4: InventoryStatus.LOCKED,
}


def _row_to_lot(row) -> InventoryLot:
    date_code = "-".join(filter(None, [
        row.piDateCodeYear, row.piDateCodeMonth, row.piDateCodeWeek
    ])) or None
    return InventoryLot(
        lot_id       = row.piInventoryID,
        product_id   = row.piProductID,
        part_number  = row.piPartNumber,
        brand        = row.piBrand,
        quantity     = Decimal(str(row.piQty or 0)),
        stockroom_id = row.piStockroomID,
        date_code    = date_code,
        unit_price   = float(row.piPrice) if row.piPrice else None,
        status       = _STATUS_MAP.get(row.piInventoryStatus, InventoryStatus.AVAILABLE),
    )


def _on_order_qty(conn, product_id: int) -> Decimal:
    cursor = conn.cursor()
    cursor.execute("""
        SELECT SUM(poiQty - ISNULL(poiInQty, 0))
        FROM PurchaseOrderItem
        WHERE poiProductID = ?
          AND (poiExecuteTag IS NULL OR poiExecuteTag NOT IN (2, 3))
          AND poiQty > ISNULL(poiInQty, 0)
    """, product_id)
    row = cursor.fetchone()
    return Decimal(str(row[0] or 0))


class SmartTradeInventoryRepository:

    def list_lots(self, product_id: int) -> list[InventoryLot]:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM ProductInventory WHERE piProductID = ? ORDER BY piInventoryID",
                product_id,
            )
            return [_row_to_lot(r) for r in cursor.fetchall()]

    def get_product_stock(self, product_id: int) -> ProductStock | None:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM ProductInventory WHERE piProductID = ? ORDER BY piInventoryID",
                product_id,
            )
            rows = cursor.fetchall()
            if not rows:
                return None
            lots = [_row_to_lot(r) for r in rows]
            on_order = _on_order_qty(conn, product_id)

        total = sum(l.quantity for l in lots)
        available = sum(l.quantity for l in lots if l.status == InventoryStatus.AVAILABLE)
        first = rows[0]
        return ProductStock(
            product_id    = product_id,
            part_number   = first.piPartNumber,
            brand         = first.piBrand,
            total_qty     = total,
            available_qty = available,
            on_order_qty  = on_order,
            lots          = lots,
        )

    def get_product_stock_by_part_number(self, part_number: str) -> ProductStock | None:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM ProductInventory WHERE piPartNumber = ? ORDER BY piInventoryID",
                part_number,
            )
            rows = cursor.fetchall()
            if not rows:
                return None
            lots = [_row_to_lot(r) for r in rows]
            product_id = rows[0].piProductID
            on_order = _on_order_qty(conn, product_id)

        total = sum(l.quantity for l in lots)
        available = sum(l.quantity for l in lots if l.status == InventoryStatus.AVAILABLE)
        return ProductStock(
            product_id    = product_id,
            part_number   = part_number,
            brand         = rows[0].piBrand,
            total_qty     = total,
            available_qty = available,
            on_order_qty  = on_order,
            lots          = lots,
        )

    def list_low_stock(self, threshold: Decimal) -> list[ProductStock]:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT piProductID, piPartNumber, piBrand,
                       SUM(piQty) AS total_qty,
                       SUM(CASE WHEN piInventoryStatus = 1 THEN piQty ELSE 0 END) AS available_qty
                FROM ProductInventory
                GROUP BY piProductID, piPartNumber, piBrand
                HAVING SUM(CASE WHEN piInventoryStatus = 1 THEN piQty ELSE 0 END) < ?
            """, float(threshold))
            rows = cursor.fetchall()

        return [
            ProductStock(
                product_id    = r.piProductID,
                part_number   = r.piPartNumber,
                brand         = r.piBrand,
                total_qty     = Decimal(str(r.total_qty or 0)),
                available_qty = Decimal(str(r.available_qty or 0)),
                on_order_qty  = Decimal("0"),
            )
            for r in rows
        ]
