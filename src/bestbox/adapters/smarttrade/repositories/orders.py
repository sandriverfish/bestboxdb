from datetime import datetime
from decimal import Decimal
from bestbox.adapters.smarttrade.db.connection import get_connection
from bestbox.core.domain.orders import (
    OrderStatus, OrderItem, SalesOrder, PurchaseOrder
)

_EXECUTE_TAG_TO_STATUS = {
    1: OrderStatus.PARTIAL,
    2: OrderStatus.FULFILLED,
    3: OrderStatus.CANCELLED,
}


def _resolve_order_status(approve_tag, execute_tag) -> OrderStatus:
    if execute_tag in _EXECUTE_TAG_TO_STATUS:
        return _EXECUTE_TAG_TO_STATUS[execute_tag]
    if approve_tag == 1:
        return OrderStatus.APPROVED
    return OrderStatus.PENDING


def _row_to_order_item(row) -> OrderItem:
    status = _resolve_order_status(None, row.soiExecuteTag)
    return OrderItem(
        item_id       = row.soiItemID,
        line_no       = row.soiLineNO,
        product_id    = row.soiProductID,
        part_number   = row.soiPartNumber,
        brand         = row.soiBrand,
        description   = row.soiAllDesc,
        qty_ordered   = Decimal(str(row.soiQty or 0)),
        qty_shipped   = Decimal(str(row.soiOutQty or 0)),
        qty_available = Decimal(str(row.soiInventoryQty or 0)),
        unit_price    = float(row.soiPrice or 0),
        delivery_date = row.soiDeliveryDate,
        status        = status,
    )


def _row_to_po_item(row) -> OrderItem:
    status = _resolve_order_status(None, row.poiExecuteTag)
    return OrderItem(
        item_id       = row.poiItemID,
        line_no       = row.poiLineNO,
        product_id    = row.poiProductID,
        part_number   = row.poiPartNumber,
        brand         = row.poiBrand,
        description   = row.poiAllDesc,
        qty_ordered   = Decimal(str(row.poiQty or 0)),
        qty_shipped   = Decimal(str(row.poiInQty or 0)),
        qty_available = Decimal("0"),
        unit_price    = float(row.poiPrice or 0),
        delivery_date = row.poiDeliveryDate,
        status        = status,
    )


class SmartTradeOrderRepository:

    def get_sales_order(self, order_id: int) -> SalesOrder | None:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM SellOrder WHERE soOrderID = ?", order_id
            )
            header = cursor.fetchone()
            if not header:
                return None
            cursor.execute(
                "SELECT * FROM SellOrderItem WHERE soiOrderID = ? ORDER BY soiLineNO",
                order_id,
            )
            item_rows = cursor.fetchall()

        status = _resolve_order_status(header.soApproveTag, None)
        if item_rows:
            item_statuses = {
                _resolve_order_status(None, r.soiExecuteTag) for r in item_rows
            }
            if all(s == OrderStatus.FULFILLED for s in item_statuses):
                status = OrderStatus.FULFILLED
            elif any(s in (OrderStatus.PARTIAL, OrderStatus.FULFILLED) for s in item_statuses):
                status = OrderStatus.PARTIAL

        return SalesOrder(
            order_id      = header.soOrderID,
            order_sn      = header.soOrderSN,
            order_date    = header.soOrderDate,
            customer_id   = header.soCustomerID,
            currency      = str(header.soCurrencyID),
            total_amount  = float(header.soAmount or 0),
            delivery_date = header.soDeliveryDate,
            status        = status,
            remark        = header.soRemark,
            items         = [_row_to_order_item(r) for r in item_rows],
        )

    def list_sales_orders(
        self,
        customer_id: int | None = None,
        date_from:   datetime | None = None,
        date_to:     datetime | None = None,
        status:      int | None = None,
        limit:       int = 50,
    ) -> list[SalesOrder]:
        where, params = ["1=1"], []
        if customer_id is not None:
            where.append("soCustomerID = ?")
            params.append(customer_id)
        if date_from is not None:
            where.append("soOrderDate >= ?")
            params.append(date_from)
        if date_to is not None:
            where.append("soOrderDate <= ?")
            params.append(date_to)
        if status == OrderStatus.APPROVED:
            where.append("soApproveTag = 1")
        elif status == OrderStatus.PENDING:
            where.append("(soApproveTag IS NULL OR soApproveTag = 0)")

        sql = f"""
            SELECT TOP {int(limit)} *
            FROM SellOrder
            WHERE {' AND '.join(where)}
            ORDER BY soOrderDate DESC
        """
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            rows = cursor.fetchall()

        return [
            SalesOrder(
                order_id      = r.soOrderID,
                order_sn      = r.soOrderSN,
                order_date    = r.soOrderDate,
                customer_id   = r.soCustomerID,
                currency      = str(r.soCurrencyID),
                total_amount  = float(r.soAmount or 0),
                delivery_date = r.soDeliveryDate,
                status        = _resolve_order_status(r.soApproveTag, None),
                remark        = r.soRemark,
            )
            for r in rows
        ]

    def get_purchase_order(self, order_id: int) -> PurchaseOrder | None:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM PurchaseOrder WHERE poOrderID = ?", order_id
            )
            header = cursor.fetchone()
            if not header:
                return None
            cursor.execute(
                "SELECT * FROM PurchaseOrderItem WHERE poiOrderID = ? ORDER BY poiLineNO",
                order_id,
            )
            item_rows = cursor.fetchall()

        return PurchaseOrder(
            order_id      = header.poOrderID,
            order_sn      = header.poOrderSN,
            order_date    = header.poOrderDate,
            supplier_id   = header.poSupplierID,
            currency      = str(header.poCurrencyID),
            total_amount  = float(header.poAmount or 0),
            delivery_date = header.poDeliveryDate,
            status        = _resolve_order_status(header.poApproveTag, None),
            items         = [_row_to_po_item(r) for r in item_rows],
        )

    def list_purchase_orders(
        self,
        supplier_id: int | None = None,
        date_from:   datetime | None = None,
        date_to:     datetime | None = None,
        status:      int | None = None,
        limit:       int = 50,
    ) -> list[PurchaseOrder]:
        where, params = ["1=1"], []
        if supplier_id is not None:
            where.append("poSupplierID = ?")
            params.append(supplier_id)
        if date_from is not None:
            where.append("poOrderDate >= ?")
            params.append(date_from)
        if date_to is not None:
            where.append("poOrderDate <= ?")
            params.append(date_to)

        sql = f"""
            SELECT TOP {int(limit)} *
            FROM PurchaseOrder
            WHERE {' AND '.join(where)}
            ORDER BY poOrderDate DESC
        """
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            rows = cursor.fetchall()

        return [
            PurchaseOrder(
                order_id      = r.poOrderID,
                order_sn      = r.poOrderSN,
                order_date    = r.poOrderDate,
                supplier_id   = r.poSupplierID,
                currency      = str(r.poCurrencyID),
                total_amount  = float(r.poAmount or 0),
                delivery_date = r.poDeliveryDate,
                status        = _resolve_order_status(r.poApproveTag, None),
            )
            for r in rows
        ]
