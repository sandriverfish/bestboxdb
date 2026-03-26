from decimal import Decimal
from enum import IntEnum
from pydantic import BaseModel


class InventoryStatus(IntEnum):
    AVAILABLE  = 1
    HELD       = 2
    QUARANTINE = 3
    LOCKED     = 4


class InventoryLot(BaseModel):
    lot_id:       int
    product_id:   int
    part_number:  str | None
    brand:        str | None
    quantity:     Decimal
    stockroom_id: int
    date_code:    str | None
    unit_price:   float | None
    status:       InventoryStatus


class ProductStock(BaseModel):
    product_id:    int
    part_number:   str | None
    brand:         str | None
    total_qty:     Decimal
    available_qty: Decimal
    on_order_qty:  Decimal
    lots:          list[InventoryLot] = []
