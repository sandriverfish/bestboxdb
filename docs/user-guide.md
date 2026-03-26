# BestBox MCP User Guide

BestBox exposes your SmartTrade ERP data to AI agents through the Model Context Protocol (MCP). Once connected, any MCP-compatible AI client (Claude Code, Claude Desktop, custom agents) can query live orders and inventory by asking natural-language questions — no SQL, no ERP credentials needed by the agent.

---

## Table of Contents

1. [Connecting to BestBox](#1-connecting-to-bestbox)
2. [Available Tools](#2-available-tools)
3. [Orders — Sales](#3-orders--sales)
4. [Orders — Purchase](#4-orders--purchase)
5. [Inventory](#5-inventory)
6. [Practical Workflows](#6-practical-workflows)
7. [Tips & Limits](#7-tips--limits)

> For common operational questions see **[FAQ](faq.md)** — covering order management, inventory, fulfillment, and data limits.

---

## 1. Connecting to BestBox

### Claude Code (CLI / IDE extension)

The server is pre-registered in your Claude Code settings. It starts automatically when you open any session inside the `E:\MyCode\bestboxdb` directory (project-level `.mcp.json`) or globally via `~/.claude/settings.json`.

Verify the server loaded in a Claude Code session:

> **You:** Is the BestBox MCP server connected?

Claude will confirm the 7 available tools if the server is running.

### Verifying the server manually

```bash
cd E:\MyCode\bestboxdb
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1"}}}' \
  | .venv/Scripts/python.exe -m bestbox.mcp.server
```

A valid JSON response with `"name":"BestBox"` confirms the server is operational.

### Troubleshooting

| Symptom | Fix |
|---|---|
| Tools not available in session | Restart Claude Code (MCP servers load at startup) |
| `KeyError: SMARTTRADE_SERVER` | Ensure `.env` exists in `E:\MyCode\bestboxdb` |
| Connection timeout | Check VPN / network access to `192.168.1.147:20241` |

---

## 2. Available Tools

| Tool | What it does |
|---|---|
| `list_sales_orders` | List sales orders with optional date / customer / status filters |
| `get_sales_order` | Full detail of one sales order including all line items |
| `list_purchase_orders` | List purchase orders with optional date / supplier filters |
| `get_purchase_order` | Full detail of one purchase order including all line items |
| `check_stock` | Available inventory for a part number (instant availability check) |
| `list_low_stock` | All products whose available qty is below a threshold |
| `get_inventory_lots` | Individual lot breakdown for a product (date code, stockroom, status) |

---

## 3. Orders — Sales

### List recent sales orders

**Natural language:**
> Show me all sales orders placed in March 2026.

**Tool call:**
```
list_sales_orders(date_from="2026-03-01", date_to="2026-03-31")
```

**Sample result (abridged):**
```json
[
  {
    "order_id": 35171,
    "order_sn": "YSTX-SO26030405",
    "order_date": "2026-03-26T12:01:00",
    "customer_id": 1035,
    "currency": "3",
    "total_amount": 724.5,
    "status": 0
  },
  ...
]
```

### Filter by customer

> Show pending orders for customer 838 this month.

```
list_sales_orders(customer_id=838, date_from="2026-03-01", date_to="2026-03-31", status=0)
```

### Get full order detail with line items

> What parts are on order YSTX-SO26030405?

```
get_sales_order(order_id=35171)
```

**Sample result:**
```json
{
  "order_id": 35171,
  "order_sn": "YSTX-SO26030405",
  "order_date": "2026-03-26T12:01:00",
  "customer_id": 1035,
  "currency": "3",
  "total_amount": 724.5,
  "status": 2,
  "items": [
    {
      "item_id": 103169,
      "line_no": 1,
      "product_id": 18349,
      "part_number": "V104K0201X5R6R3NAT",
      "brand": "VIIYONG",
      "qty_ordered": "525000.000",
      "qty_shipped": "0",
      "qty_available": "13440000.000000",
      "unit_price": 0.00138,
      "status": 2
    }
  ]
}
```

### Order status values

| Code | Meaning | Description |
|---|---|---|
| `0` | Pending | Created, not yet approved |
| `1` | Approved | Approved, fulfilment not started |
| `2` | Partial | Some lines shipped |
| `3` | Fulfilled | All lines shipped |
| `4` | Cancelled | Order cancelled |

### Useful queries

```
# Large orders (manual review after fetching)
list_sales_orders(date_from="2026-03-01", date_to="2026-03-31", limit=50)

# Orders needing action (approved but not shipped)
list_sales_orders(status=1, limit=50)

# Specific customer's outstanding orders
list_sales_orders(customer_id=760, status=0)
```

---

## 4. Orders — Purchase

### List incoming purchase orders

> What purchase orders are arriving this month?

```
list_purchase_orders(date_from="2026-03-01", date_to="2026-03-31")
```

### Filter by supplier

```
list_purchase_orders(supplier_id=42, date_from="2026-01-01", date_to="2026-03-31")
```

### Get full PO with line items

```
get_purchase_order(order_id=12345)
```

**Sample result:**
```json
{
  "order_id": 12345,
  "order_sn": "YSTX-PO26030001",
  "supplier_id": 42,
  "currency": "3",
  "total_amount": 58000.0,
  "delivery_date": "2026-03-01T00:00:00",
  "status": 1,
  "items": [
    {
      "item_id": 9001,
      "line_no": 1,
      "product_id": 18349,
      "part_number": "GRM188R60J475KE19D",
      "brand": "MURATA",
      "description": "",
      "qty_ordered": "200000.000",
      "qty_shipped": "0",
      "qty_available": "0",
      "unit_price": 0.29,
      "delivery_date": "2026-03-01T00:00:00",
      "status": 1
    }
  ]
}
```

---

## 5. Inventory

### Check stock for a part number

> Do we have GRM188R60J475KE19D in stock?

```
check_stock(part_number="GRM188R60J475KE19D")
```

**Sample result:**
```json
{
  "product_id": 18349,
  "part_number": "GRM188R60J475KE19D",
  "brand": "MURATA",
  "total_qty": 450000,
  "available_qty": 320000,
  "on_order_qty": 200000,
  "lots": [
    {
      "lot_id": 77201,
      "product_id": 18349,
      "part_number": "GRM188R60J475KE19D",
      "brand": "MURATA",
      "quantity": 120000,
      "stockroom_id": 3,
      "date_code": "2024-11-W3",
      "unit_price": 0.29,
      "status": 1
    }
  ]
}
```

| Field | Meaning |
|---|---|
| `total_qty` | All lots in warehouse (including held/quarantine) |
| `available_qty` | Ready-to-ship stock only (excludes held, quarantine, locked) |
| `on_order_qty` | Quantity on open purchase orders not yet received |
| `lots` | Individual lot breakdown — same data as `get_inventory_lots`, embedded for convenience |

> **Note:** `check_stock` already includes the full lot breakdown in its response. Calling `get_inventory_lots` separately is only necessary if you need lots by `product_id` rather than part number.

### Find low-stock products

> Which products are running low (under 500 units)?

```
list_low_stock(threshold=500)
```

> **Tip:** Keep the threshold specific. `list_low_stock(threshold=100)` is safe for most queries; `threshold=1000` can already return enough rows to overflow MCP response limits. Start narrow and widen as needed. For bulk exports, use the REST API (`GET /inventory/stock`) instead.

### Inspect lot-level detail

> Show me the individual lots for product 18349 — I need date codes and stockroom locations.

```
get_inventory_lots(product_id=18349)
```

**Sample result:**
```json
[
  {
    "lot_id": 77201,
    "product_id": 18349,
    "part_number": "GRM188R60J475KE19D",
    "brand": "MURATA",
    "quantity": 120000,
    "stockroom_id": 3,
    "date_code": "2024-11-W3",
    "unit_price": 0.29,
    "status": 1
  },
  ...
]
```

### Lot status values

| Code | Meaning |
|---|---|
| `1` | Available |
| `2` | Held |
| `3` | Quarantine |
| `4` | Locked |

---

## 6. Practical Workflows

### Can we ship this order today?

1. Fetch the order to get part numbers:
   ```
   get_sales_order(order_id=35171)
   ```
2. Check stock for each line item:
   ```
   check_stock(part_number="V104K0201X5R6R3NAT")
   ```
3. If stock is short, check incoming POs:
   ```
   list_purchase_orders(date_from="2026-03-25", date_to="2026-04-30")
   ```

### Daily stock health check

```
list_low_stock(threshold=100)
```

Cross-reference results with open purchase orders to identify gaps with no replenishment planned. Increase the threshold incrementally if needed — see the tip in [Tips & Limits](#7-tips--limits) about response size.

### Fulfillment status across a customer's orders

```
list_sales_orders(customer_id=1035, status=2)   # Partial — in progress
list_sales_orders(customer_id=1035, status=0)   # Pending — not yet started
```

### Trace a part from PO to lot

1. Find the PO receiving this part:
   ```
   list_purchase_orders(supplier_id=42)
   ```
2. Confirm stock landed in warehouse:
   ```
   check_stock(part_number="GRM188R60J475KE19D")
   ```
3. Inspect date codes and stockroom placement:
   ```
   get_inventory_lots(product_id=18349)
   ```

---

## 7. Tips & Limits

### Default and maximum limits

All list tools default to `limit=20`. Maximum is `100` per call. For full exports use the REST API (`GET /orders/sales` or `GET /inventory/stock`).

### Currency codes

The `currency` field is a SmartTrade internal ID. Common mappings observed in live data:

| Code | Currency |
|---|---|
| `2` | USD |
| `3` | CNY |

### Date format

All dates must be ISO 8601 strings: `"2026-03-01"`. Datetime strings (`"2026-03-01T00:00:00"`) are also accepted.

### Items not loaded in list calls

`list_sales_orders` and `list_purchase_orders` return header-level data only (`items: []`). Call `get_sales_order` / `get_purchase_order` with the specific `order_id` to load line items.

### Order status can differ between list and detail

`list_sales_orders` computes status from the order header only (`soApproveTag`). `get_sales_order` refines it by also inspecting each line item's execute tag — so the same order may appear as `Pending (0)` in a list but `Partial (2)` in the detail view once items have been partially shipped.

Always call `get_sales_order` if you need an accurate fulfillment status.

### Part number search is exact

`check_stock(part_number=...)` performs an exact match. Use the part number exactly as it appears in the ERP (case-sensitive). Partial search is not supported via MCP — use the REST API or the ERP directly for wildcard lookups.

### The server reads live ERP data

Every tool call hits the SmartTrade SQL Server in real time. There is no cache. Results always reflect current ERP state.
