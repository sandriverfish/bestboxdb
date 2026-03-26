from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
from bestbox.services.orders import OrderService

router = APIRouter(prefix="/orders", tags=["orders"])
_service: OrderService | None = None


def set_service(service: OrderService):
    global _service
    _service = service


@router.get("/sales/{order_id}")
def get_sales_order(order_id: int):
    order = _service.get_sales_order(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Sales order not found")
    return order.model_dump(mode="json")


@router.get("/sales")
def list_sales_orders(
    customer_id: int | None = Query(default=None),
    date_from:   datetime | None = Query(default=None),
    date_to:     datetime | None = Query(default=None),
    status:      int | None = Query(default=None),
    limit:       int = Query(default=50, le=200),
):
    orders = _service.list_sales_orders(
        customer_id=customer_id, date_from=date_from,
        date_to=date_to, status=status, limit=limit,
    )
    return [o.model_dump(mode="json") for o in orders]


@router.get("/purchases/{order_id}")
def get_purchase_order(order_id: int):
    order = _service.get_purchase_order(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    return order.model_dump(mode="json")


@router.get("/purchases")
def list_purchase_orders(
    supplier_id: int | None = Query(default=None),
    date_from:   datetime | None = Query(default=None),
    date_to:     datetime | None = Query(default=None),
    limit:       int = Query(default=50, le=200),
):
    orders = _service.list_purchase_orders(
        supplier_id=supplier_id, date_from=date_from,
        date_to=date_to, limit=limit,
    )
    return [o.model_dump(mode="json") for o in orders]
