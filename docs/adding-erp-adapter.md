# Adding a New ERP Adapter

BestBox uses a ports & adapters architecture. Adding a second ERP system (SAP, Kingdee, Oracle, etc.) means implementing two Python classes that satisfy existing Protocol interfaces. The REST API and MCP server require zero changes.

---

## Overview

What you need to implement:

| Class | Interface | File location |
|---|---|---|
| `YourERPOrderRepository` | `OrderRepositoryProtocol` | `src/bestbox/adapters/<erp>/repositories/orders.py` |
| `YourERPInventoryRepository` | `InventoryRepositoryProtocol` | `src/bestbox/adapters/<erp>/repositories/inventory.py` |

Optionally:

| File | Purpose |
|---|---|
| `src/bestbox/adapters/<erp>/config.py` | Connection settings from env vars |
| `src/bestbox/adapters/<erp>/db/connection.py` | Database connection context manager |

---

## Step 1: Create the adapter package

```bash
mkdir -p src/bestbox/adapters/<erp>/db
mkdir -p src/bestbox/adapters/<erp>/repositories
touch src/bestbox/adapters/<erp>/__init__.py
touch src/bestbox/adapters/<erp>/db/__init__.py
touch src/bestbox/adapters/<erp>/repositories/__init__.py
```

---

## Step 2: Implement the Order Repository

Your repository must implement all four methods of `OrderRepositoryProtocol`:

```python
# src/bestbox/adapters/<erp>/repositories/orders.py

from datetime import datetime
from bestbox.core.domain.orders import SalesOrder, PurchaseOrder, OrderItem, OrderStatus


class YourERPOrderRepository:

    def get_sales_order(self, order_id: int) -> SalesOrder | None:
        # Query your ERP, map to domain model
        # Return None if not found
        ...

    def list_sales_orders(
        self,
        customer_id: int | None = None,
        date_from:   datetime | None = None,
        date_to:     datetime | None = None,
        status:      int | None = None,
        limit:       int = 50,
    ) -> list[SalesOrder]:
        # Return list of SalesOrder (without items — header only)
        ...

    def get_purchase_order(self, order_id: int) -> PurchaseOrder | None:
        ...

    def list_purchase_orders(
        self,
        supplier_id: int | None = None,
        date_from:   datetime | None = None,
        date_to:     datetime | None = None,
        status:      int | None = None,
        limit:       int = 50,
    ) -> list[PurchaseOrder]:
        ...
```

**Key rules:**
- Return domain models (`SalesOrder`, `PurchaseOrder`, `OrderItem`) — never raw DB rows
- Map ERP-specific status codes to `OrderStatus` enum values
- `list_*` methods return headers only (no items list) for performance
- `get_*` methods return full objects with items populated
- Return `None` (not raise) when a record is not found

---

## Step 3: Implement the Inventory Repository

```python
# src/bestbox/adapters/<erp>/repositories/inventory.py

from decimal import Decimal
from bestbox.core.domain.inventory import ProductStock, InventoryLot, InventoryStatus


class YourERPInventoryRepository:

    def get_product_stock(self, product_id: int) -> ProductStock | None:
        # Return ProductStock with lots populated and all qty fields computed
        # available_qty = sum of AVAILABLE lots
        # on_order_qty = open purchase order quantities not yet received
        ...

    def get_product_stock_by_part_number(self, part_number: str) -> ProductStock | None:
        ...

    def list_low_stock(self, threshold: Decimal) -> list[ProductStock]:
        # Return products where available_qty < threshold
        # lots list may be empty in this response
        ...

    def list_lots(self, product_id: int) -> list[InventoryLot]:
        # Return all individual lots for the product
        ...
```

**Key rules:**
- `available_qty` must exclude HELD, QUARANTINE, and LOCKED lots — only count `InventoryStatus.AVAILABLE`
- `on_order_qty` should reflect quantities on open, unfulfilled purchase orders
- Map ERP lot/stock status to `InventoryStatus` enum values
- `list_low_stock` may omit the `lots` array for performance (the service layer doesn't need it for this use case)

---

## Step 4: Write Integration Tests

```python
# tests/integration/test_<erp>_orders.py

import pytest
from bestbox.adapters.<erp>.repositories.orders import YourERPOrderRepository
from bestbox.core.domain.orders import SalesOrder, OrderStatus

pytestmark = pytest.mark.integration


@pytest.fixture
def repo():
    return YourERPOrderRepository()


def test_list_sales_orders_returns_results(repo):
    orders = repo.list_sales_orders(limit=5)
    assert isinstance(orders, list)
    for o in orders:
        assert isinstance(o, SalesOrder)
        assert o.order_id > 0

def test_get_sales_order_not_found(repo):
    assert repo.get_sales_order(-1) is None

def test_status_is_valid_enum(repo):
    orders = repo.list_sales_orders(limit=10)
    for o in orders:
        assert o.status in list(OrderStatus)
```

Run with:
```bash
pytest tests/integration/test_<erp>_orders.py -v -m integration
```

---

## Step 5: Wire into the App

In `src/bestbox/rest/main.py`, the adapter is selected at startup. Add a branch for your new ERP:

```python
def create_app(...) -> FastAPI:
    ...
    adapter = os.environ.get("BESTBOX_ERP_ADAPTER", "smarttrade")

    if adapter == "smarttrade":
        from bestbox.adapters.smarttrade.repositories.orders import SmartTradeOrderRepository
        from bestbox.adapters.smarttrade.repositories.inventory import SmartTradeInventoryRepository
        order_repo = SmartTradeOrderRepository()
        inventory_repo = SmartTradeInventoryRepository()
    elif adapter == "<erp>":
        from bestbox.adapters.<erp>.repositories.orders import YourERPOrderRepository
        from bestbox.adapters.<erp>.repositories.inventory import YourERPInventoryRepository
        order_repo = YourERPOrderRepository()
        inventory_repo = YourERPInventoryRepository()

    order_service = OrderService(repo=order_repo)
    inventory_service = InventoryService(repo=inventory_repo)
    ...
```

Do the same in `src/bestbox/mcp/server.py`.

Then set in `.env`:
```
BESTBOX_ERP_ADAPTER=<erp>
```

---

## Checklist

- [ ] `adapters/<erp>/repositories/orders.py` — implements all 4 `OrderRepositoryProtocol` methods
- [ ] `adapters/<erp>/repositories/inventory.py` — implements all 4 `InventoryRepositoryProtocol` methods
- [ ] Domain models returned (no raw DB rows above the repository)
- [ ] `available_qty` excludes non-AVAILABLE lots
- [ ] `get_*` returns `None` on not-found, never raises
- [ ] Integration tests written and passing
- [ ] `rest/main.py` and `mcp/server.py` updated with adapter selection
- [ ] `.env.example` updated with new adapter's env vars
