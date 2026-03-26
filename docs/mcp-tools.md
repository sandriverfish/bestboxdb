# MCP Tools Reference

BestBox exposes 7 tools via the Model Context Protocol. Claude agents (and any MCP-compatible LLM) can call these tools directly to query the ERP.

## Starting the MCP Server

```bash
python -m bestbox.mcp.server
```

Runs in stdio mode. To connect to Claude Desktop, add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "bestbox": {
      "command": "python",
      "args": ["-m", "bestbox.mcp.server"],
      "cwd": "/path/to/bestboxdb"
    }
  }
}
```

---

## Orders Tools

### `get_sales_order`

Get a sales order with all line items by order ID.

**Parameters:**

| Name | Type | Required | Description |
|---|---|---|---|
| `order_id` | integer | yes | SmartTrade sales order ID |

**Returns:** Sales order dict with items, or `{}` if not found.

**Example agent prompt:** *"Look up sales order 12345 and tell me the fulfillment status."*

---

### `list_sales_orders`

List sales orders with optional filters.

**Parameters:**

| Name | Type | Required | Description |
|---|---|---|---|
| `customer_id` | integer | no | Filter by customer ID |
| `date_from` | string | no | ISO date string, e.g. `"2024-01-01"` |
| `date_to` | string | no | ISO date string, e.g. `"2024-12-31"` |
| `status` | integer | no | 0=Pending, 1=Approved, 2=Partial, 3=Fulfilled, 4=Cancelled |
| `limit` | integer | no | Max results (default 20, max 100) |

**Returns:** Array of sales order dicts (without items — use `get_sales_order` for line items).

**Example agent prompt:** *"Show me all pending sales orders from this month."*

---

### `get_purchase_order`

Get a purchase order with all line items by order ID.

**Parameters:**

| Name | Type | Required | Description |
|---|---|---|---|
| `order_id` | integer | yes | SmartTrade purchase order ID |

**Returns:** Purchase order dict with items, or `{}` if not found.

---

### `list_purchase_orders`

List purchase orders with optional filters.

**Parameters:**

| Name | Type | Required | Description |
|---|---|---|---|
| `supplier_id` | integer | no | Filter by supplier ID |
| `date_from` | string | no | ISO date string |
| `date_to` | string | no | ISO date string |
| `limit` | integer | no | Max results (default 20, max 100) |

**Returns:** Array of purchase order dicts (without items).

---

## Inventory Tools

### `check_stock`

Get available inventory for a part number. This is the primary tool for agents asking "do we have this part in stock?"

**Parameters:**

| Name | Type | Required | Description |
|---|---|---|---|
| `part_number` | string | yes | Part number to look up |

**Returns:**

```json
{
  "product_id": 500,
  "part_number": "TLV62130ADSGR",
  "brand": "TI",
  "total_qty": "3500",
  "available_qty": "2800",
  "on_order_qty": "2000",
  "lots": [...]
}
```

Returns `{"available_qty": 0, "total_qty": 0, "on_order_qty": 0}` if part not found.

**Key fields for agents:**
- `available_qty` — what can actually be sold/allocated right now (excludes held, quarantine, locked lots)
- `on_order_qty` — what's coming in from open purchase orders
- `total_qty` — everything in the warehouse including held/reserved

**Example agent prompt:** *"Check if we have TLV62130ADSGR in stock and how many are available."*

---

### `list_low_stock`

List products whose available quantity is below a threshold. Useful for replenishment alerts.

**Parameters:**

| Name | Type | Required | Description |
|---|---|---|---|
| `threshold` | float | no | Available qty threshold (default 10.0) |

**Returns:** Array of `ProductStock` dicts (without lot detail).

**Example agent prompt:** *"Which products have fewer than 50 units available? We need to reorder."*

---

### `get_inventory_lots`

Get individual lot breakdown for a product. Use this when `check_stock` isn't enough detail — e.g., when date codes, stockroom locations, or per-lot status matter.

**Parameters:**

| Name | Type | Required | Description |
|---|---|---|---|
| `product_id` | integer | yes | Product ID |

**Returns:** Array of `InventoryLot` dicts:

```json
[
  {
    "lot_id": 10001,
    "product_id": 500,
    "part_number": "TLV62130ADSGR",
    "brand": "TI",
    "quantity": "2000",
    "stockroom_id": 1,
    "date_code": "2024-03",
    "unit_price": 0.92,
    "status": 1
  }
]
```

**Lot status values:** 1=Available, 2=Held, 3=Quarantine, 4=Locked

**Example agent prompt:** *"Show me all the lot details for product 500, including date codes."*

---

## Common Agent Workflows

### Check if an order can be fulfilled

1. Call `get_sales_order` to get line items and quantities
2. For each line item, call `check_stock` with the part number
3. Compare `available_qty` against `qty_ordered - qty_shipped`

### Inventory replenishment review

1. Call `list_low_stock(threshold=100)` to find products below minimum
2. Call `list_purchase_orders` to see what's already on order
3. Cross-reference to identify items that need new POs

### Order status summary

1. Call `list_sales_orders(status=2)` for partially shipped orders
2. Call `get_sales_order` on each for item-level detail
3. Compute remaining quantities per line item
