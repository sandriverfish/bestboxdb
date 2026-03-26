# BestBox ERP Gateway

An agentic gateway that exposes on-premises ERP data to enterprise AI agents via REST API and MCP (Model Context Protocol).

**Current ERP:** SmartTrade 2024 (vendor: TopVision) via MS SQL Server

---

## Quickstart

### Prerequisites

- Python 3.10+
- ODBC Driver for SQL Server (`SQL Server` driver, included with Windows)
- Access to SmartTrade SQL Server

### Setup

```bash
# Install dependencies
pip install -e ".[dev]"

# Configure credentials
cp .env.example .env
# Edit .env with your SmartTrade connection details
```

### Run the REST API

```bash
uvicorn bestbox.rest.main:app --reload
```

API available at `http://localhost:8000`
Interactive docs at `http://localhost:8000/docs`

### Run the MCP Server

```bash
python -m bestbox.mcp.server
```

The MCP server runs in stdio mode and can be connected to Claude Desktop or any MCP-compatible agent.

### Run Tests

```bash
# Unit tests only (no DB required)
pytest tests/unit/

# Integration tests (requires live SmartTrade DB)
pytest tests/integration/ -m integration

# All tests
pytest
```

---

## Architecture

BestBox uses a **ports & adapters** (hexagonal) pattern. The core domain is ERP-agnostic. Each ERP system is a pluggable adapter.

```
MCP Server ──┐
             ├── Services (orders, inventory)
REST API   ──┘       └── Ports (Protocol interfaces)
                              └── Adapters
                                    └── SmartTrade (TopVision)
                                          └── pyodbc → SQL Server
```

### Layer Responsibilities

| Layer | Package | Responsibility |
|---|---|---|
| Domain | `bestbox.core.domain` | ERP-agnostic Pydantic models |
| Ports | `bestbox.core.ports` | Protocol interfaces any adapter must satisfy |
| Adapters | `bestbox.adapters.smarttrade` | SmartTrade SQL → domain model mapping |
| Services | `bestbox.services` | Business logic (aggregation, status computation) |
| REST | `bestbox.rest` | FastAPI HTTP transport |
| MCP | `bestbox.mcp` | MCP tool transport |

### Key Design Decisions

- **Services never import adapters.** The concrete adapter is injected at startup in `rest/main.py` and `mcp/server.py`. This makes services independently testable with mock repositories.
- **All ERP column mapping happens in the adapter.** SmartTrade's `soOrderID`, `piQty`, etc. are translated to clean domain field names (`order_id`, `quantity`) at the repository boundary. Nothing above the adapter sees ERP column names.
- **REST and MCP share the same service instances.** No business logic is duplicated between transports.

---

## Project Structure

```
bestboxdb/
├── src/
│   └── bestbox/
│       ├── core/
│       │   ├── domain/
│       │   │   ├── orders.py       # SalesOrder, PurchaseOrder, OrderItem, OrderStatus
│       │   │   └── inventory.py    # ProductStock, InventoryLot, InventoryStatus
│       │   └── ports/
│       │       ├── orders.py       # OrderRepositoryProtocol
│       │       └── inventory.py    # InventoryRepositoryProtocol
│       ├── adapters/
│       │   └── smarttrade/
│       │       ├── config.py       # Connection settings from .env
│       │       ├── db/
│       │       │   └── connection.py   # pyodbc context manager
│       │       └── repositories/
│       │           ├── orders.py       # SmartTradeOrderRepository
│       │           └── inventory.py    # SmartTradeInventoryRepository
│       ├── services/
│       │   ├── orders.py           # OrderService
│       │   └── inventory.py        # InventoryService
│       ├── rest/
│       │   ├── main.py             # FastAPI app factory
│       │   └── routers/
│       │       ├── orders.py       # /api/v1/orders/*
│       │       └── inventory.py    # /api/v1/inventory/*
│       └── mcp/
│           └── server.py           # FastMCP server, 7 tools
├── tests/
│   ├── unit/                       # Mock-based, no DB required
│   └── integration/                # Live SmartTrade DB required
├── docs/
│   ├── README.md                   # This file
│   ├── api-reference.md            # REST API endpoint reference
│   ├── mcp-tools.md                # MCP tool reference
│   └── adding-erp-adapter.md       # Guide for adding new ERP systems
├── pyproject.toml
├── .env                            # Credentials (not committed)
└── .env.example                    # Credential template
```

---

## Configuration

All configuration is via environment variables, loaded from `.env`:

| Variable | Description | Default |
|---|---|---|
| `SMARTTRADE_SERVER` | SQL Server host | required |
| `SMARTTRADE_PORT` | SQL Server port | required |
| `SMARTTRADE_DATABASE` | Database name | required |
| `SMARTTRADE_USER` | SQL login username | required |
| `SMARTTRADE_PASSWORD` | SQL login password | required |
| `SMARTTRADE_DRIVER` | ODBC driver name | `SQL Server` |
| `BESTBOX_ERP_ADAPTER` | Active adapter name | `smarttrade` |

---

## Domain Model Overview

### Orders

- **`OrderStatus`** — `PENDING(0)`, `APPROVED(1)`, `PARTIAL(2)`, `FULFILLED(3)`, `CANCELLED(4)`
- **`SalesOrder`** — header with customer, currency, amount, delivery date, status
- **`PurchaseOrder`** — header with supplier, currency, amount, delivery date, status
- **`OrderItem`** — line item with product, quantities (ordered/shipped/available), price, delivery date

### Inventory

- **`InventoryStatus`** — `AVAILABLE(1)`, `HELD(2)`, `QUARANTINE(3)`, `LOCKED(4)`
- **`InventoryLot`** — individual stock lot with quantity, stockroom, date code, status
- **`ProductStock`** — aggregated view: `total_qty`, `available_qty` (AVAILABLE lots only), `on_order_qty` (open POs)

---

## Roadmap

- [ ] Write operations (requires separate auth + write-capable DB user)
- [ ] Currency code resolution (currently passes raw `currencyID`)
- [ ] Customer/supplier name denormalization in order responses
- [ ] Second ERP adapter (SAP, Kingdee)
- [ ] API key authentication
- [ ] Response caching for high-traffic deployments
