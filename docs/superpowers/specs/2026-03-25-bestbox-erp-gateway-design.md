# BestBox ERP Gateway — Design Spec

**Date:** 2026-03-25
**Status:** Approved
**Scope:** Read-only gateway for SmartTrade ERP (vendor: TopVision), extensible to other ERP systems

---

## Overview

BestBox is an agentic gateway that exposes on-premises ERP data to enterprise AI agents. It connects to ERP systems via their native database access method and presents a clean, ERP-agnostic domain API over two transports:

- **REST API** (FastAPI) — for conventional HTTP consumers and integration testing
- **MCP Server** — for native Claude agent tool use

Initial focus: **Orders** (sales orders, purchase orders) and **Inventory** domains of SmartTrade 2024 (TopVision), accessed via MS SQL Server on `192.168.1.147:20241`, database `SmartTrade_2024`.

---

## Architecture

BestBox uses a **ports & adapters** (hexagonal) pattern. The core is ERP-agnostic. Each ERP system is a pluggable adapter that implements common port interfaces.

```
MCP Server ──┐
             ├── Services (orders, inventory)
REST API   ──┘       └── Ports (Protocol interfaces)
                              └── Adapters
                                    └── SmartTrade (TopVision)
                                          └── pyodbc → SQL Server
```

Adding a second ERP (e.g. SAP, Kingdee) means creating a new adapter under `adapters/` that satisfies the same port protocols. REST and MCP layers remain unchanged.

---

## Project Structure

```
bestboxdb/
├── src/
│   └── bestbox/
│       ├── core/
│       │   ├── domain/
│       │   │   ├── orders.py        # SalesOrder, PurchaseOrder, OrderItem, OrderStatus
│       │   │   └── inventory.py     # InventoryLot, ProductStock
│       │   └── ports/
│       │       ├── orders.py        # OrderRepositoryProtocol
│       │       └── inventory.py     # InventoryRepositoryProtocol
│       ├── adapters/
│       │   └── smarttrade/          # Vendor: TopVision
│       │       ├── db/
│       │       │   └── connection.py   # pyodbc connection pool + context manager
│       │       ├── repositories/
│       │       │   ├── orders.py       # Maps so*/poi* columns → domain models
│       │       │   └── inventory.py    # Maps pi* columns → domain models
│       │       └── config.py          # SmartTrade connection settings from .env
│       ├── services/
│       │   ├── orders.py            # OrderService: fulfillment status, filtering
│       │   └── inventory.py         # InventoryService: lot aggregation, low-stock
│       ├── rest/
│       │   ├── main.py              # FastAPI app, wires adapter at startup
│       │   └── routers/
│       │       ├── orders.py
│       │       └── inventory.py
│       └── mcp/
│           └── server.py            # FastMCP server, shares services with REST
├── tests/
│   ├── unit/                        # Tests against mock repositories
│   └── integration/                 # Tests against real SmartTrade DB
├── pyproject.toml
├── .env                             # DB credentials — never committed
└── .gitignore                       # Must include .env
```

---

## Domain Models (`core/domain/`)

All models are Pydantic `BaseModel`. They are ERP-agnostic — no SmartTrade column names appear here.

### Orders

```python
class OrderStatus(IntEnum):
    PENDING   = 0   # not yet approved
    APPROVED  = 1   # approved, not yet shipped
    PARTIAL   = 2   # partially shipped
    FULFILLED = 3   # fully shipped
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
    qty_available: Decimal        # inventory on hand at query time
    unit_price:    float
    delivery_date: datetime
    status:        OrderStatus

class SalesOrder(BaseModel):
    order_id:      int
    order_sn:      str            # e.g. "SO2024-00123"
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

### Inventory

```python
class InventoryStatus(IntEnum):
    AVAILABLE  = 1
    HELD       = 2    # reserved against a sales order
    QUARANTINE = 3    # quality hold
    LOCKED     = 4    # stock-take in progress

class InventoryLot(BaseModel):
    lot_id:      int
    product_id:  int
    part_number: str | None
    brand:       str | None
    quantity:    Decimal
    stockroom_id: int
    date_code:   str | None       # manufacturing date code
    unit_price:  float | None
    status:      InventoryStatus

class ProductStock(BaseModel):
    """Aggregated view across all lots — primary agent-facing model."""
    product_id:    int
    part_number:   str | None
    brand:         str | None
    total_qty:     Decimal
    available_qty: Decimal        # excludes held/reserved lots
    on_order_qty:  Decimal        # from open purchase order items
    lots:          list[InventoryLot] = []
```

---

## Port Interfaces (`core/ports/`)

Python `Protocol` — structural typing, no inheritance required.

### `OrderRepositoryProtocol`

```python
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

### `InventoryRepositoryProtocol`

```python
class InventoryRepositoryProtocol(Protocol):
    def get_product_stock(self, product_id: int) -> ProductStock | None: ...
    def get_product_stock_by_part_number(self, part_number: str) -> ProductStock | None: ...
    def list_low_stock(self, threshold: Decimal) -> list[ProductStock]: ...
    def list_lots(self, product_id: int) -> list[InventoryLot]: ...
```

Note: `on_order_qty` in `ProductStock` is populated by the repository by summing open `PurchaseOrderItem.poiQty - poiInQty` where `poiExecuteTag` is not FULFILLED/CANCELLED. This query runs in the same repository call as the lot fetch.

---

## SmartTrade Adapter (`adapters/smarttrade/`)

### Column Mapping Convention

SmartTrade uses a table-prefix naming convention for all columns:

| ERP Column | Domain Field | Table |
|---|---|---|
| `soOrderID` | `order_id` | SellOrder |
| `soOrderSN` | `order_sn` | SellOrder |
| `soCustomerID` | `customer_id` | SellOrder |
| `soApproveTag` | → `status` (combined with `soiExecuteTag`) | SellOrder |
| `soiQty` | `qty_ordered` | SellOrderItem |
| `soiOutQty` | `qty_shipped` | SellOrderItem |
| `soiInventoryQty` | `qty_available` | SellOrderItem |
| `piInventoryID` | `lot_id` | ProductInventory |
| `piQty` | `quantity` | ProductInventory |
| `piProductID` | `product_id` | ProductInventory |
| `piInventoryStatus` | `status` | ProductInventory |

All column-to-field mapping is confined to `adapters/smarttrade/repositories/`. Nothing above this layer references ERP column names.

### Status Mapping

SmartTrade encodes order status across two fields:

```
soApproveTag=None               → PENDING
soApproveTag=1                  → APPROVED
soiExecuteTag=1                 → PARTIAL
soiExecuteTag=2                 → FULFILLED
soiExecuteTag=3                 → CANCELLED
```

The repository resolves these into a single `OrderStatus` enum value.

### Key ERP Tables Used

**Orders domain:**
- `SellOrder` + `SellOrderItem` — sales order header and lines
- `SellOrderItemDelivery` — split delivery schedules
- `SellReturn` + `SellReturnItem` — sales returns
- `PurchaseOrder` + `PurchaseOrderItem` — purchase order header and lines

**Inventory domain:**
- `ProductInventory` — lot-level inventory (one row per lot)
- `StockIn` + `StockInItem` — stock receipts
- `StockOut` + `StockOutItem` — stock issues
- `ProductOnOrder` — quantities on open purchase orders

---

## Services (`services/`)

Services contain business logic that spans multiple repository calls or requires computation beyond raw data retrieval.

### `OrderService`
- `get_sales_order(order_id)` — fetches order with items
- `list_sales_orders(...)` — delegates to repo with filters
- `get_fulfillment_status(order_id)` — computes shipped vs. ordered ratio across all items

### `InventoryService`
- `get_stock_summary(part_number)` — fetches lots, computes `available_qty` (excludes held/reserved)
- `list_low_stock(threshold)` — returns products with `available_qty < threshold`

Services depend only on port protocols. The concrete adapter is injected at application startup.

---

## REST API Endpoints

Base path: `/api/v1`

### Orders

| Method | Path | Description |
|---|---|---|
| GET | `/orders/sales/{order_id}` | Single sales order with line items |
| GET | `/orders/sales` | List sales orders (filters: `customer_id`, `date_from`, `date_to`, `status`, `limit`) |
| GET | `/orders/purchases/{order_id}` | Single purchase order with line items |
| GET | `/orders/purchases` | List purchase orders (filters: `supplier_id`, `date_from`, `date_to`, `limit`) |

### Inventory

| Method | Path | Description |
|---|---|---|
| GET | `/inventory/stock/{product_id}` | Aggregated stock for a product |
| GET | `/inventory/stock/by-part/{part_number}` | Aggregated stock by part number |
| GET | `/inventory/low-stock` | Products below threshold (query param: `threshold`) |
| GET | `/inventory/lots/{product_id}` | All individual lots for a product |

All responses return domain model JSON. No raw ERP column names in responses.

---

## MCP Server Tools

Server name: `BestBox`
Transport: stdio (switchable to SSE for networked deployment)

| Tool | Description (agent-facing) |
|---|---|
| `get_sales_order` | Get a sales order with all line items by order ID |
| `list_sales_orders` | List sales orders with optional filters by customer, date range, or status |
| `get_purchase_order` | Get a purchase order with all line items by order ID |
| `list_purchase_orders` | List purchase orders with optional filters by supplier and date range |
| `check_stock` | Get available inventory quantity for a part number |
| `list_low_stock` | List products with available quantity below a given threshold |
| `get_inventory_lots` | Get individual inventory lot detail for a product |

MCP tools share the same service instances as the REST API. No business logic is duplicated.

---

## Configuration

All secrets loaded from `.env` (never committed):

```
SMARTTRADE_SERVER=192.168.1.147
SMARTTRADE_PORT=20241
SMARTTRADE_DATABASE=SmartTrade_2024
SMARTTRADE_USER=YIBAO
SMARTTRADE_PASSWORD=<redacted>
SMARTTRADE_DRIVER=SQL Server
```

Active ERP adapter is selected at startup via env var:

```
BESTBOX_ERP_ADAPTER=smarttrade
```

---

## Deferred (Out of Scope for v1)

- Write operations (create/update orders) — requires separate auth model and SQL user with write permissions
- Currency code resolution (currently passes raw `currencyID` integer)
- Customer/supplier name denormalization into order responses
- Second ERP adapter (SAP, Kingdee, etc.)
- API key authentication
- Response caching / materialized read models
