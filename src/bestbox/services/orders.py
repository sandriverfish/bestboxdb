from datetime import datetime
from bestbox.core.domain.orders import SalesOrder, PurchaseOrder
from bestbox.core.ports.orders import OrderRepositoryProtocol


class OrderService:
    def __init__(self, repo: OrderRepositoryProtocol):
        self._repo = repo

    def get_sales_order(self, order_id: int) -> SalesOrder | None:
        return self._repo.get_sales_order(order_id)

    def list_sales_orders(
        self,
        customer_id: int | None = None,
        date_from:   datetime | None = None,
        date_to:     datetime | None = None,
        status:      int | None = None,
        limit:       int = 50,
    ) -> list[SalesOrder]:
        return self._repo.list_sales_orders(
            customer_id=customer_id,
            date_from=date_from,
            date_to=date_to,
            status=status,
            limit=limit,
        )

    def get_purchase_order(self, order_id: int) -> PurchaseOrder | None:
        return self._repo.get_purchase_order(order_id)

    def list_purchase_orders(
        self,
        supplier_id: int | None = None,
        date_from:   datetime | None = None,
        date_to:     datetime | None = None,
        status:      int | None = None,
        limit:       int = 50,
    ) -> list[PurchaseOrder]:
        return self._repo.list_purchase_orders(
            supplier_id=supplier_id,
            date_from=date_from,
            date_to=date_to,
            status=status,
            limit=limit,
        )

    def get_fulfillment_status(self, order_id: int) -> dict | None:
        order = self._repo.get_sales_order(order_id)
        if order is None:
            return None
        total_ordered = sum(i.qty_ordered for i in order.items)
        total_shipped = sum(i.qty_shipped for i in order.items)
        if total_ordered == 0:
            pct = 0.0
        else:
            pct = float(total_shipped / total_ordered * 100)
        return {
            "order_id":      order.order_id,
            "order_sn":      order.order_sn,
            "total_ordered": float(total_ordered),
            "total_shipped": float(total_shipped),
            "fulfilled_pct": round(pct, 1),
        }
