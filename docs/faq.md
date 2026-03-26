# BestBox FAQ

Answers to common questions when using BestBox to query SmartTrade ERP data. Organised by topic — jump to the section most relevant to you.

1. [Order Management](#1-order-management)
2. [Inventory](#2-inventory)
3. [Fulfillment & Shipping](#3-fulfillment--shipping)
4. [Data & Limits](#4-data--limits)

---

## 1. Order Management

### How do I find all orders placed this month?

```
list_sales_orders(date_from="2026-03-01", date_to="2026-03-31")
```

Use ISO date strings. The tool defaults to the 20 most recent results — add `limit=100` if you need more. For a full export beyond 100 records use the REST API (`GET /orders/sales`).

---

### How do I find all pending orders for a specific customer?

```
list_sales_orders(customer_id=838, status=0)
```

Combine `customer_id` with a date range to narrow further:

```
list_sales_orders(customer_id=838, date_from="2026-01-01", date_to="2026-03-31", status=0)
```

---

### How do I find orders that are approved but haven't shipped yet?

```
list_sales_orders(status=1)
```

Status `1` means the order is approved but no items have been dispatched. These are your actionable backlog. Note that some of these orders may be old — add a `date_from` filter if you only want recent ones:

```
list_sales_orders(status=1, date_from="2026-01-01")
```

> **Important:** Status filtering only works reliably for `0` (Pending) and `1` (Approved). Filtering by `status=2`, `3`, or `4` has no effect in list calls — all orders are returned regardless. To find partial or fulfilled orders, fetch individual orders with `get_sales_order` and check the status field there.

---

### How do I look up an order by its order number (e.g. YSTX-SO26030405)?

There is no direct order-number search via MCP. The order number (`order_sn`) encodes the date: `YSTX-SO` + `YY` + `MM` + sequence. Use that to narrow the date range, then scan the results:

```
# YSTX-SO26030405 was placed in March 2026
list_sales_orders(date_from="2026-03-01", date_to="2026-03-31", limit=100)
```

Then ask the AI to find the matching `order_sn` in the results. Alternatively, if you already know the `order_id`, call `get_sales_order` directly.

---

### Why does the same order show a different status when I look at it in detail?

`list_sales_orders` computes status from the order header only. `get_sales_order` refines it by also checking each line item's shipment state. So an order that appears as `Pending (0)` or `Approved (1)` in a list may show as `Partial (2)` when fetched individually, once some items have been dispatched.

**Always use `get_sales_order` when you need an accurate fulfillment status.** The list view is for browsing; the detail view is authoritative.

---

### What do the order status codes mean?

| Code | Status | Meaning |
|---|---|---|
| `0` | Pending | Created, not yet approved |
| `1` | Approved | Approved, no items shipped yet |
| `2` | Partial | At least one line item has been dispatched |
| `3` | Fulfilled | All line items fully shipped |
| `4` | Cancelled | Order cancelled |

> Status `2` and `3` are only reliably visible via `get_sales_order`, not `list_sales_orders` (see above).

---

## 2. Inventory

### What is the difference between `total_qty`, `available_qty`, and `on_order_qty`?

| Field | What it counts | Can you sell it? |
|---|---|---|
| `total_qty` | Every lot in the warehouse, regardless of status | Not necessarily |
| `available_qty` | Lots with status `Available (1)` only — excludes Held, Quarantine, Locked | Yes |
| `on_order_qty` | Open purchase order quantities not yet received | Not yet — it's incoming |

**Use `available_qty` for any commitment to a customer.** `total_qty` includes stock that may be reserved or under quality hold.

---

### Stock shows a quantity but it says "Held" — can we sell it?

No — not until the hold is released. A lot with status `Held (2)` is reserved against a sales order or an internal allocation. It is excluded from `available_qty` for this reason.

To see which lots are held versus available for a product:

```
get_inventory_lots(product_id=18349)
```

Look at the `status` field per lot:

| Code | Meaning | Sellable? |
|---|---|---|
| `1` | Available | Yes |
| `2` | Held | No — reserved |
| `3` | Quarantine | No — quality hold |
| `4` | Locked | No — stock-take in progress |

Contact your warehouse team to release a hold if the reservation is no longer valid.

---

### `check_stock` returns zero but I know we have stock — what's happening?

Two possible causes:

**1. The part number isn't in the inventory product master.**
`check_stock` looks up the part number in the product catalogue. If the part was received under a different number or the product master hasn't been updated, it won't find the stock. Example: part `V104K0201X5R6R3NAT` shows on order line items with 13.4M units available but `check_stock` returns zero because the product master doesn't carry that exact part number.

Workaround: if you know the `product_id` from a sales or purchase order line item, use `get_inventory_lots` directly:

```
get_inventory_lots(product_id=18349)
```

**2. All lots have zero quantity.**
The product exists in the master but all lots have been fully consumed or returned. The `lots` array in the response will show the lot history — if every `quantity` is `"0"`, the product is genuinely out of stock.

---

### Can I promise `on_order_qty` to a customer?

Not directly. `on_order_qty` is stock on open purchase orders that has not yet been received into the warehouse. It has no guaranteed arrival date visible through BestBox. To assess when it might arrive, check the purchase order:

```
list_purchase_orders(date_from="2026-03-01", date_to="2026-04-30")
```

Find the relevant PO and check its `delivery_date`. Only commit to a customer once the stock lands and `available_qty` increases.

---

### How do I find which stockroom a product is stored in?

Use `get_inventory_lots` — each lot includes a `stockroom_id`:

```
get_inventory_lots(product_id=18349)
```

Each lot entry shows:

```json
{
  "lot_id": 63921,
  "product_id": 18349,
  "quantity": "12510000.000",
  "stockroom_id": 1,
  "date_code": null,
  "status": 1
}
```

`stockroom_id` is the SmartTrade internal warehouse location ID. If you need the stockroom name, check your SmartTrade configuration or ask your warehouse manager.

---

## 3. Fulfillment & Shipping

### Can we ship this order today?

1. Fetch the order to get the line items:
   ```
   get_sales_order(order_id=35171)
   ```

2. For each line item, check available stock:
   ```
   check_stock(part_number="V104K0201X5R6R3NAT")
   ```
   If `check_stock` returns zero, try `get_inventory_lots(product_id=<id>)` using the `product_id` from the line item (see inventory FAQ above).

3. Compare `available_qty` against the outstanding quantity (`qty_ordered − qty_shipped`) per line.

4. If stock is short, check whether a purchase order covers the gap:
   ```
   list_purchase_orders(date_from="2026-03-25", date_to="2026-04-30")
   ```

---

### How do I find what's still outstanding on a partial order?

Fetch the order detail and compute outstanding per line:

```
get_sales_order(order_id=31716)
```

For each item: **outstanding = `qty_ordered` − `qty_shipped`**

Example from a live partial order (YSTX-SO25080203):

```json
{
  "part_number": "RSFM1801A",
  "qty_ordered": "21000.000",
  "qty_shipped": "0",
  "status": 2
}
```

Here `qty_shipped` is `0` but the item status is `2` (Partial) — meaning the shipment process has started at the order level but this specific line hasn't been dispatched yet. Outstanding: 21,000 units.

---

### What does `qty_shipped` mean on a purchase order?

On purchase orders, `qty_shipped` represents the **received quantity** — how much of the ordered stock has physically arrived and been booked into the warehouse. It does not mean "shipped by us"; it means "received by us from the supplier."

```json
{
  "part_number": "HMK316B7105KLHT",
  "qty_ordered": "30000.000",
  "qty_shipped": "0"
}
```

If `qty_shipped` is `0` on a PO line, the goods have not yet been received. If it equals `qty_ordered`, the line is fully received.

---

### How do I find all partial orders for a customer?

Due to a current limitation, `list_sales_orders(status=2)` does not filter by partial status (see [Data & Limits](#4-data--limits)). The workaround is to fetch all orders for the customer and let the AI identify the partial ones:

```
list_sales_orders(customer_id=1035, limit=100)
```

Then ask: *"Which of these orders have status 2 (Partial)?"* The AI will filter the results. For a thorough review, follow up with `get_sales_order` on each match.

---

## 4. Data & Limits

### Why am I only seeing 20 results — are there more?

All list tools default to `limit=20`. Increase it up to the maximum of `100`:

```
list_sales_orders(date_from="2026-03-01", date_to="2026-03-31", limit=100)
```

For more than 100 records, use the REST API which supports `limit=200`:

```
GET /api/v1/orders/sales?date_from=2026-03-01&date_to=2026-03-31&limit=200
```

---

### `list_low_stock` returned too much data — what do I do?

A low threshold means many products qualify, producing a very large response. Keep the threshold tight and work upwards:

```
list_low_stock(threshold=10)    # Start here
list_low_stock(threshold=50)    # Widen if needed
list_low_stock(threshold=100)   # Safe upper limit for MCP
```

Above `threshold=100`, the response can exceed MCP limits. For a full low-stock export, use the REST API:

```
GET /api/v1/inventory/low-stock?threshold=500
```

---

### `list_sales_orders` status filter — which values actually work?

Only `status=0` (Pending) and `status=1` (Approved) are supported as list filters. Passing `status=2`, `3`, or `4` has no effect — all orders are returned as if no status filter was applied.

This is a current limitation of the list endpoint. To work with partial, fulfilled, or cancelled orders, fetch individual orders by ID with `get_sales_order` and read the `status` field there.

---

### Why can't I search by partial part number?

`check_stock` performs an exact, case-sensitive match. `check_stock(part_number="GRM188R60")` will not match `GRM188R60J475KE19D`. Use the full part number exactly as it appears in the ERP.

For wildcard or fuzzy search, use the ERP directly or query the REST API with your own filtering logic.

---

### What do the currency codes mean?

The `currency` field is a SmartTrade internal ID:

| Code | Currency |
|---|---|
| `2` | USD |
| `3` | CNY |

These are observed mappings from live data. If you see an unfamiliar code, check your SmartTrade currency configuration.

---

### What time zone are the order dates in?

Order dates are stored and returned in the SmartTrade server's local time (no UTC offset in the response). For this installation, that is **China Standard Time (CST, UTC+8)**. Date-only queries (`"2026-03-01"`) are treated as midnight local time.
