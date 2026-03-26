# BestBox ERP Gateway Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a read-only agentic gateway that exposes SmartTrade ERP data (orders + inventory) via REST API and MCP server, using a ports & adapters architecture extensible to future ERP systems.

**Architecture:** Hexagonal/ports-and-adapters — ERP-agnostic domain models and Protocol interfaces in `core/`, SmartTrade-specific SQL in `adapters/smarttrade/`, shared business logic in `services/`, thin transport layers in `rest/` and `mcp/`.

**Tech Stack:** Python 3.10+, FastAPI, uvicorn, pyodbc, pydantic, python-dotenv, mcp (FastMCP), pytest, httpx

---

## File Map

| File | Responsibility |
|---|---|
| `pyproject.toml` | Dependencies, build config, pytest settings |
| `.env` | DB credentials (gitignored) |
| `.env.example` | Credential template (committed) |
| `src/bestbox/core/domain/orders.py` | `OrderStatus`, `OrderItem`, `SalesOrder`, `PurchaseOrder` |
| `src/bestbox/core/domain/inventory.py` | `InventoryStatus`, `InventoryLot`, `ProductStock` |
| `src/bestbox/core/ports/orders.py` | `OrderRepositoryProtocol` |
| `src/bestbox/core/ports/inventory.py` | `InventoryRepositoryProtocol` |
| `src/bestbox/adapters/smarttrade/config.py` | `SmartTradeConfig` from env vars |
| `src/bestbox/adapters/smarttrade/db/connection.py` | pyodbc connection context manager |
| `src/bestbox/adapters/smarttrade/repositories/orders.py` | `SmartTradeOrderRepository` |
| `src/bestbox/adapters/smarttrade/repositories/inventory.py` | `SmartTradeInventoryRepository` |
| `src/bestbox/services/orders.py` | `OrderService` |
| `src/bestbox/services/inventory.py` | `InventoryService` |
| `src/bestbox/rest/main.py` | FastAPI app factory, dependency injection |
| `src/bestbox/rest/routers/orders.py` | Orders endpoints |
| `src/bestbox/rest/routers/inventory.py` | Inventory endpoints |
| `src/bestbox/mcp/server.py` | FastMCP server + tool definitions |
| `tests/unit/test_order_service.py` | Unit tests for `OrderService` |
| `tests/unit/test_inventory_service.py` | Unit tests for `InventoryService` |
| `tests/integration/test_smarttrade_orders.py` | Integration tests vs real SmartTrade DB |
| `tests/integration/test_smarttrade_inventory.py` | Integration tests vs real SmartTrade DB |
| `tests/conftest.py` | Shared fixtures |

---

## Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `.env`
- Create: `.env.example`
- Create: `src/bestbox/__init__.py` (and all sub-package `__init__.py` files)

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "bestbox"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "fastapi>=0.111.0",
    "uvicorn[standard]>=0.29.0",
    "pyodbc>=5.0.0",
    "pydantic>=2.0.0",
    "python-dotenv>=1.0.0",
    "mcp[cli]>=1.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "httpx>=0.27.0",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
markers = [
    "integration: requires live SmartTrade DB connection (deselect with -m 'not integration')",
]

[tool.hatch.build.targets.wheel]
packages = ["src/bestbox"]
```

- [ ] **Step 2: Update `.gitignore`**

```
.env
.venv/
__pycache__/
*.pyc
*.egg-info/
dist/
.pytest_cache/
```

- [ ] **Step 3: Create `.env` with SmartTrade credentials**

```
SMARTTRADE_SERVER=192.168.1.147
SMARTTRADE_PORT=20241
SMARTTRADE_DATABASE=SmartTrade_2024
SMARTTRADE_USER=YIBAO
SMARTTRADE_PASSWORD=Topvision_2026
SMARTTRADE_DRIVER=SQL Server
BESTBOX_ERP_ADAPTER=smarttrade
```

- [ ] **Step 4: Create `.env.example`**

```
SMARTTRADE_SERVER=
SMARTTRADE_PORT=20241
SMARTTRADE_DATABASE=
SMARTTRADE_USER=
SMARTTRADE_PASSWORD=
SMARTTRADE_DRIVER=SQL Server
BESTBOX_ERP_ADAPTER=smarttrade
```

- [ ] **Step 5: Create all `__init__.py` files**

```bash
mkdir -p src/bestbox/core/domain
mkdir -p src/bestbox/core/ports
mkdir -p src/bestbox/adapters/smarttrade/db
mkdir -p src/bestbox/adapters/smarttrade/repositories
mkdir -p src/bestbox/services
mkdir -p src/bestbox/rest/routers
mkdir -p src/bestbox/mcp
mkdir -p tests/unit
mkdir -p tests/integration
```

Create empty `__init__.py` in each:
`src/bestbox/__init__.py`, `src/bestbox/core/__init__.py`, `src/bestbox/core/domain/__init__.py`, `src/bestbox/core/ports/__init__.py`, `src/bestbox/adapters/__init__.py`, `src/bestbox/adapters/smarttrade/__init__.py`, `src/bestbox/adapters/smarttrade/db/__init__.py`, `src/bestbox/adapters/smarttrade/repositories/__init__.py`, `src/bestbox/services/__init__.py`, `src/bestbox/rest/__init__.py`, `src/bestbox/rest/routers/__init__.py`, `src/bestbox/mcp/__init__.py`, `tests/__init__.py`, `tests/unit/__init__.py`, `tests/integration/__init__.py`

- [ ] **Step 6: Install dependencies**

```bash
pip install -e ".[dev]"
```

Expected: packages install without error.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml .gitignore .env.example src/ tests/
git commit -m "chore: scaffold BestBox project structure"
```

---

## Task 2: Domain Models — Orders

**Files:**
- Create: `src/bestbox/core/domain/orders.py`
- Create: `tests/unit/test_domain_orders.py`

- [ ] **Step 1: Write failing test**

Create `tests/unit/test_domain_orders.py`:

```python
from decimal import Decimal
from datetime import datetime
from bestbox.core.domain.orders import (
    OrderStatus, OrderItem, SalesOrder, PurchaseOrder
)

def test_order_status_values():
    assert OrderStatus.PENDING == 0
    assert OrderStatus.APPROVED == 1
    assert OrderStatus.PARTIAL == 2
    assert OrderStatus.FULFILLED == 3
    assert OrderStatus.CANCELLED == 4

def test_sales_order_defaults():
    order = SalesOrder(
        order_id=1,
        order_sn="SO2024-00001",
        order_date=datetime(2024, 1, 15),
        customer_id=42,
        currency="CNY",
        total_amount=10000.0,
        delivery_date=None,
        status=OrderStatus.APPROVED,
        remark=None,
    )
    assert order.items == []
    assert order.total_amount == 10000.0

def test_sales_order_with_items():
    item = OrderItem(
        item_id=1, line_no=1, product_id=100,
        part_number="ABC123", brand="TI", description="IC",
        qty_ordered=Decimal("100"), qty_shipped=Decimal("0"),
        qty_available=Decimal("200"),
        unit_price=1.5,
        delivery_date=datetime(2024, 2, 1),
        status=OrderStatus.APPROVED,
    )
    order = SalesOrder(
        order_id=1, order_sn="SO2024-00001",
        order_date=datetime(2024, 1, 15), customer_id=42,
        currency="CNY", total_amount=150.0,
        delivery_date=None, status=OrderStatus.APPROVED,
        remark=None, items=[item],
    )
    assert len(order.items) == 1
    assert order.items[0].part_number == "ABC123"

def test_purchase_order_serializes():
    po = PurchaseOrder(
        order_id=1, order_sn="PO2024-00001",
        order_date=datetime(2024, 1, 15), supplier_id=10,
        currency="USD", total_amount=500.0,
        delivery_date=datetime(2024, 2, 15),
        status=OrderStatus.PENDING,
    )
    data = po.model_dump()
    assert data["order_sn"] == "PO2024-00001"
    assert data["status"] == OrderStatus.PENDING
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/unit/test_domain_orders.py -v
```

Expected: `ImportError` — module not found.

- [ ] **Step 3: Implement `src/bestbox/core/domain/orders.py`**

```python
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
    order_id:      int
    order_sn:      str
    order_date:    datetime
    customer_id:   int
    currency:      str
    total_amount:  float
    delivery_date: datetime | None
    status:        OrderStatus
    remark:        str | None
    items:         list[OrderItem] = []


class PurchaseOrder(BaseModel):
    order_id:      int
    order_sn:      str
    order_date:    datetime
    supplier_id:   int
    currency:      str
    total_amount:  float
    delivery_date: datetime | None
    status:        OrderStatus
    items:         list[OrderItem] = []
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/unit/test_domain_orders.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/bestbox/core/domain/orders.py tests/unit/test_domain_orders.py
git commit -m "feat: add order domain models"
```

---

## Task 3: Domain Models — Inventory

**Files:**
- Create: `src/bestbox/core/domain/inventory.py`
- Create: `tests/unit/test_domain_inventory.py`

- [ ] **Step 1: Write failing test**

Create `tests/unit/test_domain_inventory.py`:

```python
from decimal import Decimal
from bestbox.core.domain.inventory import (
    InventoryStatus, InventoryLot, ProductStock
)

def test_inventory_status_values():
    assert InventoryStatus.AVAILABLE  == 1
    assert InventoryStatus.HELD       == 2
    assert InventoryStatus.QUARANTINE == 3
    assert InventoryStatus.LOCKED     == 4

def test_product_stock_defaults():
    stock = ProductStock(
        product_id=1, part_number="ABC123", brand="TI",
        total_qty=Decimal("500"), available_qty=Decimal("400"),
        on_order_qty=Decimal("100"),
    )
    assert stock.lots == []

def test_product_stock_with_lots():
    lot = InventoryLot(
        lot_id=1, product_id=1, part_number="ABC123", brand="TI",
        quantity=Decimal("200"), stockroom_id=1,
        date_code="2401", unit_price=1.5,
        status=InventoryStatus.AVAILABLE,
    )
    stock = ProductStock(
        product_id=1, part_number="ABC123", brand="TI",
        total_qty=Decimal("200"), available_qty=Decimal("200"),
        on_order_qty=Decimal("0"), lots=[lot],
    )
    assert len(stock.lots) == 1
    assert stock.lots[0].status == InventoryStatus.AVAILABLE

def test_inventory_lot_serializes():
    lot = InventoryLot(
        lot_id=5, product_id=2, part_number=None, brand=None,
        quantity=Decimal("50"), stockroom_id=2,
        date_code=None, unit_price=None,
        status=InventoryStatus.HELD,
    )
    data = lot.model_dump()
    assert data["status"] == InventoryStatus.HELD
    assert data["part_number"] is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/unit/test_domain_inventory.py -v
```

Expected: `ImportError`.

- [ ] **Step 3: Implement `src/bestbox/core/domain/inventory.py`**

```python
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
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/unit/test_domain_inventory.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/bestbox/core/domain/inventory.py tests/unit/test_domain_inventory.py
git commit -m "feat: add inventory domain models"
```

---

## Task 4: Port Interfaces

**Files:**
- Create: `src/bestbox/core/ports/orders.py`
- Create: `src/bestbox/core/ports/inventory.py`

No tests needed — Protocols are verified by the type checker and implicitly by tests of the adapters that must satisfy them.

- [ ] **Step 1: Implement `src/bestbox/core/ports/orders.py`**

```python
from datetime import datetime
from decimal import Decimal
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
```

- [ ] **Step 2: Implement `src/bestbox/core/ports/inventory.py`**

```python
from decimal import Decimal
from typing import Protocol
from bestbox.core.domain.inventory import ProductStock, InventoryLot


class InventoryRepositoryProtocol(Protocol):
    def get_product_stock(self, product_id: int) -> ProductStock | None: ...
    def get_product_stock_by_part_number(self, part_number: str) -> ProductStock | None: ...
    def list_low_stock(self, threshold: Decimal) -> list[ProductStock]: ...
    def list_lots(self, product_id: int) -> list[InventoryLot]: ...
```

- [ ] **Step 3: Commit**

```bash
git add src/bestbox/core/ports/
git commit -m "feat: add repository port protocols"
```

---

## Task 5: OrderService with Unit Tests

**Files:**
- Create: `src/bestbox/services/orders.py`
- Create: `tests/unit/test_order_service.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_order_service.py`:

```python
from datetime import datetime
from decimal import Decimal
import pytest
from bestbox.core.domain.orders import (
    OrderStatus, OrderItem, SalesOrder, PurchaseOrder
)
from bestbox.services.orders import OrderService


def _make_item(item_id=1, qty_ordered=100, qty_shipped=0, status=OrderStatus.APPROVED):
    return OrderItem(
        item_id=item_id, line_no=item_id, product_id=10,
        part_number="P001", brand="TI", description="IC",
        qty_ordered=Decimal(str(qty_ordered)),
        qty_shipped=Decimal(str(qty_shipped)),
        qty_available=Decimal("50"),
        unit_price=1.0,
        delivery_date=datetime(2024, 3, 1),
        status=status,
    )


def _make_order(order_id=1, items=None, status=OrderStatus.APPROVED):
    return SalesOrder(
        order_id=order_id, order_sn=f"SO-{order_id:04d}",
        order_date=datetime(2024, 1, 1), customer_id=1,
        currency="CNY", total_amount=1000.0,
        delivery_date=datetime(2024, 3, 1),
        status=status, remark=None,
        items=items or [],
    )


class MockOrderRepository:
    def __init__(self, orders=None, purchase_orders=None):
        self._orders = {o.order_id: o for o in (orders or [])}
        self._pos = {o.order_id: o for o in (purchase_orders or [])}

    def get_sales_order(self, order_id):
        return self._orders.get(order_id)

    def list_sales_orders(self, customer_id=None, date_from=None,
                          date_to=None, status=None, limit=50):
        results = list(self._orders.values())
        if customer_id is not None:
            results = [o for o in results if o.customer_id == customer_id]
        return results[:limit]

    def get_purchase_order(self, order_id):
        return self._pos.get(order_id)

    def list_purchase_orders(self, supplier_id=None, date_from=None,
                             date_to=None, status=None, limit=50):
        return list(self._pos.values())[:limit]


def test_get_sales_order_found():
    order = _make_order(order_id=1)
    service = OrderService(repo=MockOrderRepository(orders=[order]))
    result = service.get_sales_order(1)
    assert result is not None
    assert result.order_id == 1

def test_get_sales_order_not_found():
    service = OrderService(repo=MockOrderRepository())
    assert service.get_sales_order(99) is None

def test_list_sales_orders_by_customer():
    orders = [_make_order(order_id=i) for i in range(1, 4)]
    service = OrderService(repo=MockOrderRepository(orders=orders))
    result = service.list_sales_orders(customer_id=1)
    assert len(result) == 3

def test_fulfillment_status_fully_shipped():
    items = [
        _make_item(item_id=1, qty_ordered=100, qty_shipped=100),
        _make_item(item_id=2, qty_ordered=50,  qty_shipped=50),
    ]
    order = _make_order(items=items)
    service = OrderService(repo=MockOrderRepository(orders=[order]))
    status = service.get_fulfillment_status(1)
    assert status["fulfilled_pct"] == 100.0

def test_fulfillment_status_partially_shipped():
    items = [
        _make_item(item_id=1, qty_ordered=100, qty_shipped=60),
        _make_item(item_id=2, qty_ordered=100, qty_shipped=0),
    ]
    order = _make_order(items=items)
    service = OrderService(repo=MockOrderRepository(orders=[order]))
    status = service.get_fulfillment_status(1)
    assert status["fulfilled_pct"] == 30.0

def test_fulfillment_status_order_not_found():
    service = OrderService(repo=MockOrderRepository())
    assert service.get_fulfillment_status(99) is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/unit/test_order_service.py -v
```

Expected: `ImportError` — `bestbox.services.orders` not found.

- [ ] **Step 3: Implement `src/bestbox/services/orders.py`**

```python
from datetime import datetime
from decimal import Decimal
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
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/unit/test_order_service.py -v
```

Expected: 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/bestbox/services/orders.py tests/unit/test_order_service.py
git commit -m "feat: add OrderService with fulfillment status"
```

---

## Task 6: InventoryService with Unit Tests

**Files:**
- Create: `src/bestbox/services/inventory.py`
- Create: `tests/unit/test_inventory_service.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_inventory_service.py`:

```python
from decimal import Decimal
import pytest
from bestbox.core.domain.inventory import (
    InventoryStatus, InventoryLot, ProductStock
)
from bestbox.services.inventory import InventoryService


def _make_lot(lot_id, qty, status=InventoryStatus.AVAILABLE):
    return InventoryLot(
        lot_id=lot_id, product_id=1, part_number="P001", brand="TI",
        quantity=Decimal(str(qty)), stockroom_id=1,
        date_code="2401", unit_price=1.5, status=status,
    )


class MockInventoryRepository:
    def __init__(self, stocks=None):
        self._stocks = {s.product_id: s for s in (stocks or [])}
        self._by_part = {s.part_number: s for s in (stocks or []) if s.part_number}

    def get_product_stock(self, product_id):
        return self._stocks.get(product_id)

    def get_product_stock_by_part_number(self, part_number):
        return self._by_part.get(part_number)

    def list_low_stock(self, threshold):
        return [s for s in self._stocks.values() if s.available_qty < threshold]

    def list_lots(self, product_id):
        s = self._stocks.get(product_id)
        return s.lots if s else []


def test_get_stock_summary_by_part_number():
    lots = [
        _make_lot(1, 200, InventoryStatus.AVAILABLE),
        _make_lot(2, 100, InventoryStatus.HELD),
    ]
    stock = ProductStock(
        product_id=1, part_number="P001", brand="TI",
        total_qty=Decimal("300"), available_qty=Decimal("200"),
        on_order_qty=Decimal("50"), lots=lots,
    )
    service = InventoryService(repo=MockInventoryRepository(stocks=[stock]))
    result = service.get_stock_summary("P001")
    assert result is not None
    assert result.available_qty == Decimal("200")

def test_get_stock_summary_not_found():
    service = InventoryService(repo=MockInventoryRepository())
    assert service.get_stock_summary("UNKNOWN") is None

def test_list_low_stock():
    stocks = [
        ProductStock(product_id=1, part_number="P001", brand="TI",
                     total_qty=Decimal("10"), available_qty=Decimal("5"),
                     on_order_qty=Decimal("0")),
        ProductStock(product_id=2, part_number="P002", brand="ST",
                     total_qty=Decimal("500"), available_qty=Decimal("400"),
                     on_order_qty=Decimal("0")),
    ]
    service = InventoryService(repo=MockInventoryRepository(stocks=stocks))
    result = service.list_low_stock(threshold=Decimal("100"))
    assert len(result) == 1
    assert result[0].part_number == "P001"

def test_available_qty_excludes_held_lots():
    lots = [
        _make_lot(1, 300, InventoryStatus.AVAILABLE),
        _make_lot(2, 100, InventoryStatus.HELD),
        _make_lot(3, 50,  InventoryStatus.QUARANTINE),
    ]
    stock = ProductStock(
        product_id=1, part_number="P001", brand="TI",
        total_qty=Decimal("450"), available_qty=Decimal("0"),
        on_order_qty=Decimal("0"), lots=lots,
    )
    service = InventoryService(repo=MockInventoryRepository(stocks=[stock]))
    result = service.get_stock_summary("P001")
    # Service recomputes available_qty from lot statuses
    assert result.available_qty == Decimal("300")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/unit/test_inventory_service.py -v
```

Expected: `ImportError`.

- [ ] **Step 3: Implement `src/bestbox/services/inventory.py`**

```python
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
        # Recompute available_qty from actual lot statuses
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
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/unit/test_inventory_service.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 5: Run all unit tests together**

```bash
pytest tests/unit/ -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/bestbox/services/inventory.py tests/unit/test_inventory_service.py
git commit -m "feat: add InventoryService with lot aggregation"
```

---

## Task 7: SmartTrade Config + DB Connection

**Files:**
- Create: `src/bestbox/adapters/smarttrade/config.py`
- Create: `src/bestbox/adapters/smarttrade/db/connection.py`

- [ ] **Step 1: Implement `src/bestbox/adapters/smarttrade/config.py`**

```python
import os
from dotenv import load_dotenv

load_dotenv()


class SmartTradeConfig:
    server:   str = os.environ["SMARTTRADE_SERVER"]
    port:     str = os.environ["SMARTTRADE_PORT"]
    database: str = os.environ["SMARTTRADE_DATABASE"]
    user:     str = os.environ["SMARTTRADE_USER"]
    password: str = os.environ["SMARTTRADE_PASSWORD"]
    driver:   str = os.environ.get("SMARTTRADE_DRIVER", "SQL Server")

    @classmethod
    def connection_string(cls) -> str:
        return (
            f"DRIVER={{{cls.driver}}};"
            f"SERVER={cls.server},{cls.port};"
            f"DATABASE={cls.database};"
            f"UID={cls.user};"
            f"PWD={cls.password};"
        )
```

- [ ] **Step 2: Implement `src/bestbox/adapters/smarttrade/db/connection.py`**

```python
from contextlib import contextmanager
import pyodbc
from bestbox.adapters.smarttrade.config import SmartTradeConfig


@contextmanager
def get_connection():
    conn = pyodbc.connect(SmartTradeConfig.connection_string(), timeout=15)
    try:
        yield conn
    finally:
        conn.close()
```

- [ ] **Step 3: Verify connection manually**

```bash
python -c "
from bestbox.adapters.smarttrade.db.connection import get_connection
with get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute('SELECT @@VERSION')
    print(cursor.fetchone()[0][:50])
print('Connection OK')
"
```

Expected: prints SQL Server version string and `Connection OK`.

- [ ] **Step 4: Commit**

```bash
git add src/bestbox/adapters/smarttrade/config.py src/bestbox/adapters/smarttrade/db/connection.py
git commit -m "feat: add SmartTrade config and DB connection"
```

---

## Task 8: SmartTrade Order Repository

**Files:**
- Create: `src/bestbox/adapters/smarttrade/repositories/orders.py`
- Create: `tests/integration/test_smarttrade_orders.py`

- [ ] **Step 1: Write failing integration tests**

Create `tests/integration/test_smarttrade_orders.py`:

```python
import pytest
from bestbox.adapters.smarttrade.repositories.orders import SmartTradeOrderRepository
from bestbox.core.domain.orders import SalesOrder, PurchaseOrder, OrderStatus

pytestmark = pytest.mark.integration


@pytest.fixture
def repo():
    return SmartTradeOrderRepository()


def test_list_sales_orders_returns_results(repo):
    orders = repo.list_sales_orders(limit=5)
    assert isinstance(orders, list)
    assert len(orders) <= 5
    for o in orders:
        assert isinstance(o, SalesOrder)
        assert o.order_id > 0
        assert o.order_sn != ""

def test_get_sales_order_with_items(repo):
    orders = repo.list_sales_orders(limit=1)
    assert orders, "No orders in DB — cannot test"
    order = repo.get_sales_order(orders[0].order_id)
    assert order is not None
    assert order.order_id == orders[0].order_id
    # Items may be empty for some orders but list must exist
    assert isinstance(order.items, list)

def test_get_sales_order_not_found(repo):
    result = repo.get_sales_order(-1)
    assert result is None

def test_sales_order_status_is_valid_enum(repo):
    orders = repo.list_sales_orders(limit=10)
    for o in orders:
        assert o.status in list(OrderStatus)

def test_list_purchase_orders_returns_results(repo):
    orders = repo.list_purchase_orders(limit=5)
    assert isinstance(orders, list)
    for o in orders:
        assert isinstance(o, PurchaseOrder)
        assert o.order_id > 0

def test_get_purchase_order_with_items(repo):
    orders = repo.list_purchase_orders(limit=1)
    assert orders, "No purchase orders in DB"
    po = repo.get_purchase_order(orders[0].order_id)
    assert po is not None
    assert isinstance(po.items, list)
```

- [ ] **Step 2: Run to verify fail**

```bash
pytest tests/integration/test_smarttrade_orders.py -v -m integration
```

Expected: `ImportError`.

- [ ] **Step 3: Implement `src/bestbox/adapters/smarttrade/repositories/orders.py`**

```python
from datetime import datetime
from decimal import Decimal
from bestbox.adapters.smarttrade.db.connection import get_connection
from bestbox.core.domain.orders import (
    OrderStatus, OrderItem, SalesOrder, PurchaseOrder
)

# soApproveTag=None → PENDING, 1 → APPROVED
# soiExecuteTag=1 → PARTIAL, 2 → FULFILLED, 3 → CANCELLED
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
        # Derive overall status from item execute tags if items exist
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
```

- [ ] **Step 4: Run integration tests**

```bash
pytest tests/integration/test_smarttrade_orders.py -v -m integration
```

Expected: 6 tests PASS against live SmartTrade DB.

- [ ] **Step 5: Commit**

```bash
git add src/bestbox/adapters/smarttrade/repositories/orders.py tests/integration/test_smarttrade_orders.py
git commit -m "feat: add SmartTrade order repository"
```

---

## Task 9: SmartTrade Inventory Repository

**Files:**
- Create: `src/bestbox/adapters/smarttrade/repositories/inventory.py`
- Create: `tests/integration/test_smarttrade_inventory.py`

- [ ] **Step 1: Write failing integration tests**

Create `tests/integration/test_smarttrade_inventory.py`:

```python
import pytest
from decimal import Decimal
from bestbox.adapters.smarttrade.repositories.inventory import SmartTradeInventoryRepository
from bestbox.core.domain.inventory import ProductStock, InventoryLot, InventoryStatus

pytestmark = pytest.mark.integration


@pytest.fixture
def repo():
    return SmartTradeInventoryRepository()


def test_list_lots_returns_results(repo):
    # Get a product_id that has inventory
    lots = repo.list_lots(product_id=1)
    assert isinstance(lots, list)
    for lot in lots:
        assert isinstance(lot, InventoryLot)
        assert lot.quantity >= 0

def test_get_product_stock_aggregates_lots(repo):
    stock = repo.get_product_stock(product_id=1)
    if stock is None:
        pytest.skip("Product 1 has no inventory")
    assert isinstance(stock, ProductStock)
    assert stock.total_qty == sum(l.quantity for l in stock.lots)

def test_get_product_stock_not_found(repo):
    result = repo.get_product_stock(product_id=-1)
    assert result is None

def test_get_product_stock_by_part_number(repo):
    # Fetch any lot to get a real part number
    with __import__('bestbox.adapters.smarttrade.db.connection', fromlist=['get_connection']).get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT TOP 1 piPartNumber FROM ProductInventory WHERE piPartNumber IS NOT NULL AND piPartNumber != ''")
        row = cursor.fetchone()
    if not row:
        pytest.skip("No part numbers in ProductInventory")
    part_number = row[0]
    stock = repo.get_product_stock_by_part_number(part_number)
    assert stock is not None
    assert stock.part_number == part_number

def test_list_low_stock_returns_products_below_threshold(repo):
    results = repo.list_low_stock(threshold=Decimal("9999999"))
    assert isinstance(results, list)
    for s in results:
        assert s.available_qty < Decimal("9999999")

def test_on_order_qty_is_non_negative(repo):
    stock = repo.get_product_stock(product_id=1)
    if stock is None:
        pytest.skip("Product 1 has no inventory")
    assert stock.on_order_qty >= 0
```

- [ ] **Step 2: Run to verify fail**

```bash
pytest tests/integration/test_smarttrade_inventory.py -v -m integration
```

Expected: `ImportError`.

- [ ] **Step 3: Implement `src/bestbox/adapters/smarttrade/repositories/inventory.py`**

```python
from decimal import Decimal
from bestbox.adapters.smarttrade.db.connection import get_connection
from bestbox.core.domain.inventory import (
    InventoryStatus, InventoryLot, ProductStock
)

# SmartTrade piInventoryStatus → InventoryStatus
# Values verified against sdefInventoryStatus lookup table
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
                on_order_qty  = Decimal("0"),  # not fetched in bulk query
            )
            for r in rows
        ]
```

- [ ] **Step 4: Run integration tests**

```bash
pytest tests/integration/test_smarttrade_inventory.py -v -m integration
```

Expected: tests PASS (some may skip if DB has no data for product_id=1).

- [ ] **Step 5: Commit**

```bash
git add src/bestbox/adapters/smarttrade/repositories/inventory.py tests/integration/test_smarttrade_inventory.py
git commit -m "feat: add SmartTrade inventory repository"
```

---

## Task 10: REST API

**Files:**
- Create: `src/bestbox/rest/main.py`
- Create: `src/bestbox/rest/routers/orders.py`
- Create: `src/bestbox/rest/routers/inventory.py`
- Create: `tests/unit/test_rest_orders.py`
- Create: `tests/unit/test_rest_inventory.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Write failing REST tests**

Create `tests/conftest.py`:

```python
import pytest
from decimal import Decimal
from datetime import datetime
from bestbox.core.domain.orders import OrderStatus, OrderItem, SalesOrder, PurchaseOrder
from bestbox.core.domain.inventory import InventoryStatus, InventoryLot, ProductStock


def _make_item(item_id=1):
    return OrderItem(
        item_id=item_id, line_no=item_id, product_id=10,
        part_number="P001", brand="TI", description="IC",
        qty_ordered=Decimal("100"), qty_shipped=Decimal("50"),
        qty_available=Decimal("200"), unit_price=1.5,
        delivery_date=datetime(2024, 3, 1),
        status=OrderStatus.PARTIAL,
    )


@pytest.fixture
def sample_sales_order():
    return SalesOrder(
        order_id=1, order_sn="SO2024-00001",
        order_date=datetime(2024, 1, 15), customer_id=42,
        currency="CNY", total_amount=150.0,
        delivery_date=datetime(2024, 3, 1),
        status=OrderStatus.PARTIAL, remark=None,
        items=[_make_item(1)],
    )


@pytest.fixture
def sample_purchase_order():
    return PurchaseOrder(
        order_id=1, order_sn="PO2024-00001",
        order_date=datetime(2024, 1, 15), supplier_id=10,
        currency="USD", total_amount=500.0,
        delivery_date=datetime(2024, 2, 15),
        status=OrderStatus.APPROVED,
        items=[_make_item(1)],
    )


@pytest.fixture
def sample_stock():
    lot = InventoryLot(
        lot_id=1, product_id=1, part_number="P001", brand="TI",
        quantity=Decimal("300"), stockroom_id=1,
        date_code="2401", unit_price=1.5,
        status=InventoryStatus.AVAILABLE,
    )
    return ProductStock(
        product_id=1, part_number="P001", brand="TI",
        total_qty=Decimal("300"), available_qty=Decimal("300"),
        on_order_qty=Decimal("100"), lots=[lot],
    )
```

Create `tests/unit/test_rest_orders.py`:

```python
import pytest
from httpx import AsyncClient, ASGITransport
from bestbox.rest.main import create_app
from bestbox.services.orders import OrderService


class MockOrderRepo:
    def __init__(self, order=None, po=None):
        self._order = order
        self._po = po

    def get_sales_order(self, order_id):
        return self._order if (self._order and self._order.order_id == order_id) else None

    def list_sales_orders(self, **kwargs):
        return [self._order] if self._order else []

    def get_purchase_order(self, order_id):
        return self._po if (self._po and self._po.order_id == order_id) else None

    def list_purchase_orders(self, **kwargs):
        return [self._po] if self._po else []


@pytest.mark.asyncio
async def test_get_sales_order_found(sample_sales_order):
    service = OrderService(repo=MockOrderRepo(order=sample_sales_order))
    app = create_app(order_service=service)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/orders/sales/1")
    assert response.status_code == 200
    data = response.json()
    assert data["order_id"] == 1
    assert data["order_sn"] == "SO2024-00001"
    assert len(data["items"]) == 1

@pytest.mark.asyncio
async def test_get_sales_order_not_found(sample_sales_order):
    service = OrderService(repo=MockOrderRepo(order=sample_sales_order))
    app = create_app(order_service=service)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/orders/sales/99")
    assert response.status_code == 404

@pytest.mark.asyncio
async def test_list_sales_orders(sample_sales_order):
    service = OrderService(repo=MockOrderRepo(order=sample_sales_order))
    app = create_app(order_service=service)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/orders/sales")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

@pytest.mark.asyncio
async def test_get_purchase_order_found(sample_purchase_order):
    service = OrderService(repo=MockOrderRepo(po=sample_purchase_order))
    app = create_app(order_service=service)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/orders/purchases/1")
    assert response.status_code == 200
    assert response.json()["supplier_id"] == 10
```

Create `tests/unit/test_rest_inventory.py`:

```python
import pytest
from httpx import AsyncClient, ASGITransport
from bestbox.rest.main import create_app
from bestbox.services.inventory import InventoryService
from decimal import Decimal


class MockInventoryRepo:
    def __init__(self, stock=None):
        self._stock = stock

    def get_product_stock(self, product_id):
        return self._stock if (self._stock and self._stock.product_id == product_id) else None

    def get_product_stock_by_part_number(self, part_number):
        return self._stock if (self._stock and self._stock.part_number == part_number) else None

    def list_low_stock(self, threshold):
        return [self._stock] if self._stock else []

    def list_lots(self, product_id):
        return self._stock.lots if self._stock else []


@pytest.mark.asyncio
async def test_get_stock_by_product_id(sample_stock):
    service = InventoryService(repo=MockInventoryRepo(stock=sample_stock))
    app = create_app(inventory_service=service)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/inventory/stock/1")
    assert response.status_code == 200
    assert response.json()["part_number"] == "P001"

@pytest.mark.asyncio
async def test_get_stock_by_part_number(sample_stock):
    service = InventoryService(repo=MockInventoryRepo(stock=sample_stock))
    app = create_app(inventory_service=service)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/inventory/stock/by-part/P001")
    assert response.status_code == 200
    assert response.json()["available_qty"] == "300"

@pytest.mark.asyncio
async def test_get_stock_not_found(sample_stock):
    service = InventoryService(repo=MockInventoryRepo(stock=sample_stock))
    app = create_app(inventory_service=service)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/inventory/stock/99")
    assert response.status_code == 404

@pytest.mark.asyncio
async def test_list_low_stock(sample_stock):
    service = InventoryService(repo=MockInventoryRepo(stock=sample_stock))
    app = create_app(inventory_service=service)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/inventory/low-stock?threshold=9999")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
```

- [ ] **Step 2: Run tests to verify fail**

```bash
pytest tests/unit/test_rest_orders.py tests/unit/test_rest_inventory.py -v
```

Expected: `ImportError` — `bestbox.rest.main` not found.

- [ ] **Step 3: Implement `src/bestbox/rest/routers/orders.py`**

```python
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
    return order.model_dump()


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
    return [o.model_dump() for o in orders]


@router.get("/purchases/{order_id}")
def get_purchase_order(order_id: int):
    order = _service.get_purchase_order(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    return order.model_dump()


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
    return [o.model_dump() for o in orders]
```

- [ ] **Step 4: Implement `src/bestbox/rest/routers/inventory.py`**

```python
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
    return stock.model_dump()


@router.get("/stock/by-part/{part_number}")
def get_stock_by_part_number(part_number: str):
    stock = _service.get_stock_summary(part_number)
    if stock is None:
        raise HTTPException(status_code=404, detail="Part number not found in inventory")
    return stock.model_dump()


@router.get("/low-stock")
def list_low_stock(threshold: Decimal = Query(default=Decimal("10"))):
    return [s.model_dump() for s in _service.list_low_stock(threshold)]


@router.get("/lots/{product_id}")
def list_lots(product_id: int):
    return [l.model_dump() for l in _service.list_lots(product_id)]
```

- [ ] **Step 5: Implement `src/bestbox/rest/main.py`**

```python
from fastapi import FastAPI
from bestbox.services.orders import OrderService
from bestbox.services.inventory import InventoryService
from bestbox.rest.routers import orders as orders_router_mod
from bestbox.rest.routers import inventory as inventory_router_mod


def create_app(
    order_service: OrderService | None = None,
    inventory_service: InventoryService | None = None,
) -> FastAPI:
    app = FastAPI(title="BestBox ERP Gateway", version="0.1.0")

    if order_service is None:
        from bestbox.adapters.smarttrade.repositories.orders import SmartTradeOrderRepository
        order_service = OrderService(repo=SmartTradeOrderRepository())

    if inventory_service is None:
        from bestbox.adapters.smarttrade.repositories.inventory import SmartTradeInventoryRepository
        inventory_service = InventoryService(repo=SmartTradeInventoryRepository())

    orders_router_mod.set_service(order_service)
    inventory_router_mod.set_service(inventory_service)

    app.include_router(orders_router_mod.router, prefix="/api/v1")
    app.include_router(inventory_router_mod.router, prefix="/api/v1")

    return app


# Entry point for `uvicorn bestbox.rest.main:app`
app = create_app()
```

- [ ] **Step 6: Run all unit tests**

```bash
pytest tests/unit/ -v
```

Expected: all tests PASS.

- [ ] **Step 7: Commit**

```bash
git add src/bestbox/rest/ tests/unit/test_rest_orders.py tests/unit/test_rest_inventory.py tests/conftest.py
git commit -m "feat: add REST API with FastAPI"
```

---

## Task 11: MCP Server

**Files:**
- Create: `src/bestbox/mcp/server.py`

- [ ] **Step 1: Implement `src/bestbox/mcp/server.py`**

```python
from decimal import Decimal
from mcp.server.fastmcp import FastMCP
from bestbox.adapters.smarttrade.repositories.orders import SmartTradeOrderRepository
from bestbox.adapters.smarttrade.repositories.inventory import SmartTradeInventoryRepository
from bestbox.services.orders import OrderService
from bestbox.services.inventory import InventoryService

mcp = FastMCP("BestBox")

_order_service = OrderService(repo=SmartTradeOrderRepository())
_inventory_service = InventoryService(repo=SmartTradeInventoryRepository())


@mcp.tool()
def get_sales_order(order_id: int) -> dict:
    """Get a sales order with all line items by order ID."""
    order = _order_service.get_sales_order(order_id)
    return order.model_dump() if order else {}


@mcp.tool()
def list_sales_orders(
    customer_id: int | None = None,
    date_from:   str | None = None,
    date_to:     str | None = None,
    status:      int | None = None,
    limit:       int = 20,
) -> list[dict]:
    """List sales orders with optional filters by customer ID, date range (ISO format), or status (0=Pending,1=Approved,2=Partial,3=Fulfilled,4=Cancelled)."""
    from datetime import datetime
    df = datetime.fromisoformat(date_from) if date_from else None
    dt = datetime.fromisoformat(date_to)   if date_to   else None
    orders = _order_service.list_sales_orders(
        customer_id=customer_id, date_from=df, date_to=dt,
        status=status, limit=min(limit, 100),
    )
    return [o.model_dump() for o in orders]


@mcp.tool()
def get_purchase_order(order_id: int) -> dict:
    """Get a purchase order with all line items by order ID."""
    order = _order_service.get_purchase_order(order_id)
    return order.model_dump() if order else {}


@mcp.tool()
def list_purchase_orders(
    supplier_id: int | None = None,
    date_from:   str | None = None,
    date_to:     str | None = None,
    limit:       int = 20,
) -> list[dict]:
    """List purchase orders with optional filters by supplier ID and date range (ISO format)."""
    from datetime import datetime
    df = datetime.fromisoformat(date_from) if date_from else None
    dt = datetime.fromisoformat(date_to)   if date_to   else None
    orders = _order_service.list_purchase_orders(
        supplier_id=supplier_id, date_from=df, date_to=dt,
        limit=min(limit, 100),
    )
    return [o.model_dump() for o in orders]


@mcp.tool()
def check_stock(part_number: str) -> dict:
    """Get available inventory quantity for a part number. Returns total_qty, available_qty (excludes held/quarantine), and on_order_qty from open purchase orders."""
    stock = _inventory_service.get_stock_summary(part_number)
    return stock.model_dump() if stock else {"available_qty": 0, "total_qty": 0, "on_order_qty": 0}


@mcp.tool()
def list_low_stock(threshold: float = 10.0) -> list[dict]:
    """List products with available inventory quantity below the given threshold."""
    stocks = _inventory_service.list_low_stock(Decimal(str(threshold)))
    return [s.model_dump() for s in stocks]


@mcp.tool()
def get_inventory_lots(product_id: int) -> list[dict]:
    """Get individual inventory lot details for a product, including lot ID, quantity, date code, stockroom, and status."""
    lots = _inventory_service.list_lots(product_id)
    return [l.model_dump() for l in lots]
```

- [ ] **Step 2: Verify MCP server starts**

```bash
python -c "from bestbox.mcp.server import mcp; print('MCP server OK:', mcp.name)"
```

Expected: `MCP server OK: BestBox`

- [ ] **Step 3: Commit**

```bash
git add src/bestbox/mcp/server.py
git commit -m "feat: add MCP server with 7 ERP tools"
```

---

## Task 12: Smoke Test + Final Wiring

**Files:**
- No new files

- [ ] **Step 1: Run all unit tests**

```bash
pytest tests/unit/ -v
```

Expected: all PASS.

- [ ] **Step 2: Run all integration tests**

```bash
pytest tests/integration/ -v -m integration
```

Expected: all PASS (some skips are acceptable if product has no data).

- [ ] **Step 3: Start the REST API**

```bash
uvicorn bestbox.rest.main:app --reload
```

Expected: server starts on `http://127.0.0.1:8000`. Visit `http://127.0.0.1:8000/docs` to see Swagger UI.

- [ ] **Step 4: Smoke test REST API**

In a second terminal:

```bash
# List 3 sales orders
curl "http://127.0.0.1:8000/api/v1/orders/sales?limit=3"

# Check inventory by part number (replace with a real part number from your DB)
curl "http://127.0.0.1:8000/api/v1/inventory/stock/by-part/ABC123"

# List low stock items
curl "http://127.0.0.1:8000/api/v1/inventory/low-stock?threshold=100"
```

Expected: JSON responses with clean domain field names (no `so*`, `pi*` prefixes).

- [ ] **Step 5: Test MCP server (stdio mode)**

```bash
python -m bestbox.mcp.server
```

Expected: server starts and waits for MCP protocol input on stdin.

- [ ] **Step 6: Final commit**

```bash
git add -A
git commit -m "feat: BestBox ERP gateway v0.1.0 — SmartTrade orders + inventory via REST and MCP"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Task |
|---|---|
| ERP-agnostic domain models | Tasks 2, 3 |
| Port Protocol interfaces | Task 4 |
| SmartTrade column mapping (so*, pi*) | Tasks 8, 9 |
| Status resolution (soApproveTag + soiExecuteTag) | Task 8 |
| OrderService with fulfillment status | Task 5 |
| InventoryService with lot aggregation | Task 6 |
| REST: GET /orders/sales/{id} | Task 10 |
| REST: GET /orders/sales (filtered) | Task 10 |
| REST: GET /orders/purchases/{id} | Task 10 |
| REST: GET /orders/purchases (filtered) | Task 10 |
| REST: GET /inventory/stock/{product_id} | Task 10 |
| REST: GET /inventory/stock/by-part/{part_number} | Task 10 |
| REST: GET /inventory/low-stock | Task 10 |
| REST: GET /inventory/lots/{product_id} | Task 10 |
| MCP: get_sales_order | Task 11 |
| MCP: list_sales_orders | Task 11 |
| MCP: get_purchase_order | Task 11 |
| MCP: list_purchase_orders | Task 11 |
| MCP: check_stock | Task 11 |
| MCP: list_low_stock | Task 11 |
| MCP: get_inventory_lots | Task 11 |
| on_order_qty from PurchaseOrderItem | Task 9 |
| .env config, never committed | Task 1 |
| Extensible adapter structure | Tasks 1, 7, 8, 9 |

All spec requirements covered. No placeholders. Types consistent across tasks.
