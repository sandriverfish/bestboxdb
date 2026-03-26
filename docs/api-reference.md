# REST API Reference

Base URL: `http://localhost:8000/api/v1`

Interactive docs (Swagger UI): `http://localhost:8000/docs`

All responses use clean domain field names — no ERP column names (`soOrderID`, `piQty`, etc.) appear in any response.

---

## Orders

### Get Sales Order

```
GET /orders/sales/{order_id}
```

Returns a single sales order with all line items.

**Path parameters:**

| Parameter | Type | Description |
|---|---|---|
| `order_id` | integer | SmartTrade internal order ID |

**Response `200`:**

```json
{
  "order_id": 12345,
  "order_sn": "SO2024-00123",
  "order_date": "2024-03-01T00:00:00",
  "customer_id": 42,
  "currency": "1",
  "total_amount": 15000.0,
  "delivery_date": "2024-04-15T00:00:00",
  "status": 1,
  "remark": null,
  "items": [
    {
      "item_id": 1001,
      "line_no": 1,
      "product_id": 500,
      "part_number": "TLV62130ADSGR",
      "brand": "TI",
      "description": "DC-DC Converter",
      "qty_ordered": "1000",
      "qty_shipped": "500",
      "qty_available": "800",
      "unit_price": 1.5,
      "delivery_date": "2024-04-15T00:00:00",
      "status": 2
    }
  ]
}
```

**Status codes:**
- `200` — order found
- `404` — order not found

**Status enum values:**

| Value | Meaning |
|---|---|
| 0 | PENDING — not yet approved |
| 1 | APPROVED — approved, not yet shipped |
| 2 | PARTIAL — partially shipped |
| 3 | FULFILLED — fully shipped |
| 4 | CANCELLED |

---

### List Sales Orders

```
GET /orders/sales
```

**Query parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `customer_id` | integer | — | Filter by customer |
| `date_from` | datetime | — | Order date from (ISO format: `2024-01-01`) |
| `date_to` | datetime | — | Order date to (ISO format: `2024-12-31`) |
| `status` | integer | — | Filter by status (0–4) |
| `limit` | integer | 50 | Max results (max 200) |

**Response `200`:** Array of sales order objects (same schema as above, items list is empty — use `GET /orders/sales/{id}` to fetch items).

**Examples:**

```bash
# Recent 10 orders for customer 42
GET /api/v1/orders/sales?customer_id=42&limit=10

# Approved orders in Q1 2024
GET /api/v1/orders/sales?status=1&date_from=2024-01-01&date_to=2024-03-31

# All pending orders
GET /api/v1/orders/sales?status=0
```

---

### Get Purchase Order

```
GET /orders/purchases/{order_id}
```

Returns a single purchase order with all line items.

**Response `200`:**

```json
{
  "order_id": 8001,
  "order_sn": "PO2024-00456",
  "order_date": "2024-02-10T00:00:00",
  "supplier_id": 15,
  "currency": "2",
  "total_amount": 8500.0,
  "delivery_date": "2024-03-20T00:00:00",
  "status": 1,
  "items": [
    {
      "item_id": 2001,
      "line_no": 1,
      "product_id": 500,
      "part_number": "TLV62130ADSGR",
      "brand": "TI",
      "description": "DC-DC Converter",
      "qty_ordered": "2000",
      "qty_shipped": "0",
      "qty_available": "0",
      "unit_price": 0.85,
      "delivery_date": "2024-03-20T00:00:00",
      "status": 1
    }
  ]
}
```

**Status codes:** `200` / `404`

> Note: `qty_shipped` on purchase order items represents received quantity (`poiInQty`). `qty_available` is always `0` for purchase order items (not applicable).

---

### List Purchase Orders

```
GET /orders/purchases
```

**Query parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `supplier_id` | integer | — | Filter by supplier |
| `date_from` | datetime | — | Order date from |
| `date_to` | datetime | — | Order date to |
| `limit` | integer | 50 | Max results (max 200) |

---

## Inventory

### Get Stock by Product ID

```
GET /inventory/stock/{product_id}
```

Returns aggregated stock for a product across all lots.

**Response `200`:**

```json
{
  "product_id": 500,
  "part_number": "TLV62130ADSGR",
  "brand": "TI",
  "total_qty": "3500",
  "available_qty": "2800",
  "on_order_qty": "2000",
  "lots": [
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
    },
    {
      "lot_id": 10002,
      "product_id": 500,
      "part_number": "TLV62130ADSGR",
      "brand": "TI",
      "quantity": "800",
      "stockroom_id": 1,
      "date_code": "2023-52",
      "unit_price": 0.88,
      "status": 2
    }
  ]
}
```

**Field notes:**
- `total_qty` — sum of all lot quantities regardless of status
- `available_qty` — sum of lots with `status=1` (AVAILABLE) only
- `on_order_qty` — sum of open purchase order quantities not yet received
- `lots` — individual lot detail including held and quarantine lots

**Lot status values:**

| Value | Meaning |
|---|---|
| 1 | AVAILABLE |
| 2 | HELD — reserved against a sales order |
| 3 | QUARANTINE — quality hold |
| 4 | LOCKED — stock-take in progress |

**Status codes:** `200` / `404`

---

### Get Stock by Part Number

```
GET /inventory/stock/by-part/{part_number}
```

Same response schema as above. Looks up by `piPartNumber` across all lots.

**Status codes:** `200` / `404`

**Example:**
```
GET /api/v1/inventory/stock/by-part/TLV62130ADSGR
```

---

### List Low Stock

```
GET /inventory/low-stock
```

Returns all products with `available_qty` below the threshold.

**Query parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `threshold` | decimal | 10 | Products with available_qty below this value are returned |

**Response `200`:** Array of `ProductStock` objects. The `lots` array is empty in this response (use `GET /inventory/lots/{product_id}` for lot detail).

**Example:**
```
GET /api/v1/inventory/low-stock?threshold=100
```

---

### List Inventory Lots

```
GET /inventory/lots/{product_id}
```

Returns all individual lots for a product. Useful when you need to see per-lot date codes, stockroom locations, or status breakdown.

**Response `200`:** Array of `InventoryLot` objects.

---

## Error Responses

All errors follow FastAPI's default format:

```json
{
  "detail": "Sales order not found"
}
```

| Status | Meaning |
|---|---|
| `404` | Resource not found |
| `422` | Validation error (invalid query parameter type) |
| `500` | Unexpected server error |
