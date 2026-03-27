from datetime import datetime
from decimal import Decimal
from enum import IntEnum
from pydantic import BaseModel


class OrderStatus(IntEnum):
    PENDING   = 0
    APPROVED  = 1
    PARTIAL   = 2
    FULFILLED = 3
    CANCELLED = 4


class OrderItem(BaseModel):
    item_id:       int
    line_no:       int
    product_id:    int
    part_number:   str | None
    brand:         str | None
    description:   str | None
    qty_ordered:   Decimal
    qty_shipped:   Decimal
    qty_available: Decimal
    unit_price:    float
    delivery_date: datetime
    status:        OrderStatus


class SalesOrder(BaseModel):
    order_id:       int
    order_sn:       str
    order_date:     datetime
    customer_id:    int
    customer_name:  str | None = None
    currency:       str
    total_amount:   float
    delivery_date:  datetime | None
    status:         OrderStatus
    remark:         str | None
    items:          list[OrderItem] = []


class PurchaseOrder(BaseModel):
    order_id:       int
    order_sn:       str
    order_date:     datetime
    supplier_id:    int
    supplier_name:  str | None = None
    currency:       str
    total_amount:   float
    delivery_date:  datetime | None
    status:         OrderStatus
    items:          list[OrderItem] = []
