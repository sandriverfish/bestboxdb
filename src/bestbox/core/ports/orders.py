from datetime import datetime
from typing import Protocol
from bestbox.core.domain.orders import SalesOrder, PurchaseOrder


class OrderRepositoryProtocol(Protocol):
    def get_sales_order(self, order_id: int) -> SalesOrder | None: ...

    def list_sales_orders(
        self,
        customer_id: int | None = None,
        date_from:   datetime | None = None,
        date_to:     datetime | None = None,
        status:      int | None = None,
        limit:       int = 50,
    ) -> list[SalesOrder]: ...

    def get_purchase_order(self, order_id: int) -> PurchaseOrder | None: ...

    def list_purchase_orders(
        self,
        supplier_id: int | None = None,
        date_from:   datetime | None = None,
        date_to:     datetime | None = None,
        status:      int | None = None,
        limit:       int = 50,
    ) -> list[PurchaseOrder]: ...
