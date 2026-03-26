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
