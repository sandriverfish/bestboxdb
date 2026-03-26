from decimal import Decimal
from bestbox.core.domain.inventory import (
    ProductStock, InventoryLot, InventoryStatus
)
from bestbox.core.ports.inventory import InventoryRepositoryProtocol


class InventoryService:
    def __init__(self, repo: InventoryRepositoryProtocol):
        self._repo = repo

    def get_stock_summary(self, part_number: str) -> ProductStock | None:
        stock = self._repo.get_product_stock_by_part_number(part_number)
        if stock is None:
            return None
        stock.available_qty = sum(
            lot.quantity for lot in stock.lots
            if lot.status == InventoryStatus.AVAILABLE
        )
        return stock

    def get_stock_by_product_id(self, product_id: int) -> ProductStock | None:
        stock = self._repo.get_product_stock(product_id)
        if stock is None:
            return None
        stock.available_qty = sum(
            lot.quantity for lot in stock.lots
            if lot.status == InventoryStatus.AVAILABLE
        )
        return stock

    def list_low_stock(self, threshold: Decimal) -> list[ProductStock]:
        return self._repo.list_low_stock(threshold)

    def list_lots(self, product_id: int) -> list[InventoryLot]:
        return self._repo.list_lots(product_id)
