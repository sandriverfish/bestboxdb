# BestBox ERP Gateway

An agentic gateway that exposes on-premises ERP data to enterprise AI agents via REST API and MCP (Model Context Protocol).

**Current ERP:** SmartTrade 2024 (vendor: TopVision) via MS SQL Server

---

## Quickstart

### Prerequisites

- Python 3.10+
- ODBC Driver for SQL Server (`SQL Server` driver, included with Windows)
- Access to SmartTrade SQL Server **or** a local Docker SQL Server restored from a `.bak` backup (see [Local development](#local-development))

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

# Integration tests (requires live SmartTrade DB or local Docker SQL Server)
pytest tests/integration/ -m integration

# All tests
pytest
```

> Integration tests require a running SQL Server with the SmartTrade database.
> Use the local Docker setup below when the on-site ERP server is not accessible.

---

## Local Development

When the on-site SmartTrade ERP server is unavailable (e.g. working remotely), you can restore a `.bak` backup into a local Docker SQL Server instance and point BestBox at it.

### Requirements

- Docker Desktop with at least 4 GB RAM allocated to containers
- A SmartTrade `.bak` backup file (copy from `F:\yishang\SQLbackup\` or wherever the customer stores them)

### Start the local SQL Server

```bash
# Place the .bak file somewhere Docker can reach (e.g. E:\sqlserver\backup\)
# First time only — start the container and restore the database
docker run -d \
  --name bestbox-sqlserver \
  -e ACCEPT_EULA=Y \
  -e MSSQL_SA_PASSWORD=BestBox1Dev2026 \
  -p 1433:1433 \
  -v E:/sqlserver/data:/var/opt/mssql/data \
  -v E:/sqlserver/backup:/backup \
  mcr.microsoft.com/mssql/server:2022-latest

# Wait ~20s for SQL Server to initialize, then restore the database
# (replace the filename with the actual .bak you have)
MSYS_NO_PATHCONV=1 docker exec bestbox-sqlserver \
  /opt/mssql-tools18/bin/sqlcmd \
  -S localhost -U sa -P BestBox1Dev2026 -C \
  -Q "RESTORE DATABASE [SmartTrade_2024]
      FROM DISK='/backup/SmartTrade_2024_backup_2026_03_11_180001_8097112.bak'
      WITH MOVE 'FES'     TO '/var/opt/mssql/data/SmartTrade_2024.mdf',
           MOVE 'FES_log' TO '/var/opt/mssql/data/SmartTrade_2024_log.ldf',
           REPLACE"
```

> The logical file names inside the `.bak` are `FES` (data) and `FES_log` (log file).
> The restore takes ~30–60 seconds and processes ~112,000 pages.

### Configure BestBox to use the local instance

The `.env` file has two blocks — comment/uncomment as needed:

```env
# --- Local dev (Docker SQL Server) ---
SMARTTRADE_SERVER=localhost
SMARTTRADE_PORT=1433
SMARTTRADE_DATABASE=SmartTrade_2024
SMARTTRADE_USER=sa
SMARTTRADE_PASSWORD=BestBox1Dev2026
SMARTTRADE_DRIVER=SQL Server

# --- On-site (customer ERP server) --- uncomment when on field ---
# SMARTTRADE_SERVER=192.168.1.147
# SMARTTRADE_PORT=20241
# SMARTTRADE_DATABASE=SmartTrade_2024
# SMARTTRADE_USER=YIBAO
# SMARTTRADE_PASSWORD=Topvision_2026
# SMARTTRADE_DRIVER=SQL Server
```

### Verify connectivity

```bash
python - <<'EOF'
import pyodbc
conn = pyodbc.connect(
    "DRIVER={SQL Server};SERVER=localhost,1433;"
    "DATABASE=SmartTrade_2024;UID=sa;PWD=BestBox1Dev2026;"
)
print(conn.execute("SELECT COUNT(*) FROM dbo.SellOrder").fetchone()[0], "orders")
conn.close()
EOF
```

Expected output: `34234 orders` (or similar — exact count depends on the backup date).

### Subsequent starts

The database persists in `E:\sqlserver\data\` so restore is only needed once:

```bash
docker start bestbox-sqlserver
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
│   ├── user-guide.md               # End-user guide (Claude Code / MCP clients)
│   ├── faq.md                      # Common operational questions and quirks
│   ├── agentic-app.md              # How-to: LangGraph + local LLM agent
│   └── adding-erp-adapter.md       # Guide for adding new ERP systems
├── deploy/
│   ├── docker-compose.infra.yml    # SQL Server + Redis (stand up once)
│   ├── docker-compose.app.yml      # REST API + MCP SSE (redeploy on changes)
│   ├── init-db.sh                  # SQL Server entrypoint: auto-restore .bak on first boot
│   └── .env.server.example         # Environment template for the remote server
├── Dockerfile                      # BestBox image: python:3.12-slim + ODBC Driver 18
├── .dockerignore
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
| `SMARTTRADE_TRUST_CERT` | Trust self-signed TLS cert (`yes`/`no`) | `no` |
| `BESTBOX_ERP_ADAPTER` | Active adapter name | `smarttrade` |

> Set `SMARTTRADE_TRUST_CERT=yes` when connecting to a Docker SQL Server instance (self-signed certificate) or the on-site server if it uses a self-signed cert. Required when using `ODBC Driver 18 for SQL Server` on Linux.

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
