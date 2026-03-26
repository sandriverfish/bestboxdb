# Analytics Layer Design

**Date:** 2026-03-25
**Status:** Approved
**Scope:** Add a data analysis layer to BestBox exposing KPI, trend, and anomaly-detection functions via both MCP tools and REST endpoints, backed by SQL aggregation against SmartTrade.

---

## Context

BestBox currently exposes raw ERP data (individual orders, inventory lots) to AI agents. This design adds a pre-computed analytics layer so agents and dashboards can ask higher-level questions: "What is our revenue trend?", "Which customers drove the most orders?", "What stock is oversold?".

This is sub-project 1 of 2. Sub-project 2 (ad-hoc NL query capability) depends on this layer being in place first.

---

## Architecture

New vertical slice following the existing hexagonal pattern. No existing files change structurally.

```
MCP tools (analyze_*)      REST /api/v1/analytics/*
              │                        │
         AnalyticsService              │
              │
AnalyticsRepositoryProtocol            ← port (Protocol)
              │
CachedAnalyticsRepository             ← cache decorator
              │
SmartTradeAnalyticsRepository         ← SQL GROUP BY adapter
              │
    SmartTrade SQL Server
```

### New files

```
src/bestbox/core/domain/analytics.py
src/bestbox/core/ports/analytics.py
src/bestbox/services/analytics.py
src/bestbox/adapters/smarttrade/repositories/analytics.py
src/bestbox/adapters/cache/analytics.py
src/bestbox/rest/routers/analytics.py
src/bestbox/mcp/analytics.py
```

### Modified files

- `src/bestbox/rest/main.py` — wire `AnalyticsService` into `create_app()`
- `src/bestbox/mcp/server.py` — import `bestbox.mcp.analytics` to register tools
- `src/bestbox/adapters/cache/redis_cache.py` — add `ttl_analytics_sec` and `ttl_analytics_alert_sec` to `CacheConfig`

---

## Analytics Functions

### KPIs

| Function | SQL approach | Returns |
|---|---|---|
| `sales_summary(date_from, date_to)` | `SELECT COUNT(*), SUM(soAmount), AVG(soAmount) FROM SellOrder WHERE soOrderDate BETWEEN ? AND ?` | `SalesSummary` |
| `top_customers(date_from, date_to, limit=10)` | `SELECT soCustomerID, COUNT(*), SUM(soAmount) … GROUP BY soCustomerID ORDER BY SUM(soAmount) DESC` | `list[CustomerRank]` |
| `top_products(date_from, date_to, limit=10)` | `SELECT soiProductID, soiPartNumber, soiBrand, SUM(soiQty), SUM(soiQty*soiPrice) … GROUP BY soiProductID ORDER BY SUM(soiQty*soiPrice) DESC` | `list[ProductRank]` |

### Trends

| Function | SQL approach | Returns |
|---|---|---|
| `order_trend(date_from, date_to, bucket)` | `SELECT FORMAT(soOrderDate, fmt) AS bucket, COUNT(*), SUM(soAmount) … GROUP BY FORMAT(…)` where `fmt` is `'yyyy-MM'` / `'yyyy-WW'` / `'yyyy-MM-dd'` | `list[TrendPoint]` |
| `inventory_status_summary()` | `SELECT piInventoryStatus, COUNT(DISTINCT piProductID), SUM(piQty) FROM ProductInventory GROUP BY piInventoryStatus` | `list[InventoryStatusSummary]` |

### Anomaly / Alerts

| Function | SQL approach | Returns |
|---|---|---|
| `overdue_orders(as_of_date)` | `SELECT … FROM SellOrder WHERE soDeliveryDate < ? AND soApproveTag <> 1 OR soiExecuteTag NOT IN (2,3) …` refined to exclude fulfilled/cancelled | `list[OverdueOrder]` |
| `stock_coverage_alert()` | Open SO qty per product vs `SUM(piQty WHERE piInventoryStatus=1)` — join `SellOrderItem` to `ProductInventory` | `list[StockCoverageAlert]` |
| `large_order_alert(multiplier=2.0)` | Subquery computes `AVG(soAmount)` for a rolling 90-day window; outer query selects orders where `soAmount > multiplier * avg` | `list[LargeOrderAlert]` |

---

## Domain Models

```python
# src/bestbox/core/domain/analytics.py

class SalesSummary(BaseModel):
    date_from: datetime
    date_to: datetime
    total_revenue: Decimal
    order_count: int
    avg_order_value: Decimal

class CustomerRank(BaseModel):
    customer_id: int
    total_revenue: Decimal
    order_count: int

class ProductRank(BaseModel):
    product_id: int
    part_number: str
    brand: str
    qty_sold: Decimal
    total_revenue: Decimal

class TrendPoint(BaseModel):
    bucket: str          # "2026-03" | "2026-W12" | "2026-03-25"
    order_count: int
    revenue: Decimal

class InventoryStatusSummary(BaseModel):
    status: int
    status_name: str     # "Available" | "Held" | "Quarantine" | "Locked"
    product_count: int
    total_qty: Decimal

class OverdueOrder(BaseModel):
    order_id: int
    order_sn: str
    customer_id: int
    delivery_date: datetime
    days_overdue: int
    total_amount: Decimal

class StockCoverageAlert(BaseModel):
    product_id: int
    part_number: str
    brand: str
    available_qty: Decimal
    open_order_qty: Decimal
    shortfall: Decimal

class LargeOrderAlert(BaseModel):
    order_id: int
    order_sn: str
    customer_id: int
    total_amount: Decimal
    period_average: Decimal
    multiplier: float
```

---

## Port

```python
# src/bestbox/core/ports/analytics.py

class AnalyticsRepositoryProtocol(Protocol):
    def sales_summary(self, date_from: datetime, date_to: datetime) -> SalesSummary: ...
    def top_customers(self, date_from: datetime, date_to: datetime, limit: int = 10) -> list[CustomerRank]: ...
    def top_products(self, date_from: datetime, date_to: datetime, limit: int = 10) -> list[ProductRank]: ...
    def order_trend(self, date_from: datetime, date_to: datetime, bucket: str = "month") -> list[TrendPoint]: ...
    def inventory_status_summary(self) -> list[InventoryStatusSummary]: ...
    def overdue_orders(self, as_of_date: datetime) -> list[OverdueOrder]: ...
    def stock_coverage_alert(self) -> list[StockCoverageAlert]: ...
    def large_order_alert(self, multiplier: float = 2.0) -> list[LargeOrderAlert]: ...
```

---

## REST Endpoints

All under `/api/v1/analytics/`. Query parameters mirror function arguments.

| Method | Path | Key params |
|---|---|---|
| GET | `/analytics/sales/summary` | `date_from`, `date_to` |
| GET | `/analytics/sales/top-customers` | `date_from`, `date_to`, `limit=10` |
| GET | `/analytics/sales/top-products` | `date_from`, `date_to`, `limit=10` |
| GET | `/analytics/sales/trend` | `date_from`, `date_to`, `bucket=month` |
| GET | `/analytics/inventory/status` | — |
| GET | `/analytics/alerts/overdue-orders` | `as_of` (default: today) |
| GET | `/analytics/alerts/stock-coverage` | — |
| GET | `/analytics/alerts/large-orders` | `multiplier=2.0` |

All return JSON. On invalid params, return HTTP 422.

---

## MCP Tools

Eight tools in `src/bestbox/mcp/analytics.py`, registered by importing the module in `mcp/server.py`:

| Tool name | Maps to |
|---|---|
| `analyze_sales_summary` | `sales_summary` |
| `analyze_top_customers` | `top_customers` |
| `analyze_top_products` | `top_products` |
| `analyze_order_trend` | `order_trend` |
| `analyze_inventory_status` | `inventory_status_summary` |
| `analyze_overdue_orders` | `overdue_orders` |
| `analyze_stock_coverage` | `stock_coverage_alert` |
| `analyze_large_orders` | `large_order_alert` |

Date parameters passed as ISO strings from MCP, converted to `datetime` inside the tool function (same pattern as existing `list_sales_orders`).

---

## Caching

`CachedAnalyticsRepository` wraps `SmartTradeAnalyticsRepository` using the existing `RedisCache` helper. Two new TTL fields added to `CacheConfig`:

| Field | Env var | Default | Applies to |
|---|---|---|---|
| `ttl_analytics_sec` | `CACHE_TTL_ANALYTICS_SEC` | `600` (10 min) | KPIs, trends |
| `ttl_analytics_alert_sec` | `CACHE_TTL_ANALYTICS_ALERT_SEC` | `300` (5 min) | Alert queries |

Cache keys use `bestbox:analytics:` prefix. List results use `_list_cache_key` (SHA-256 of params), single-result queries use fixed keys.

---

## Testing

### Unit tests

- `tests/unit/test_analytics_service.py` — mock repository, one happy-path + one edge case (empty result) per function
- `tests/unit/test_rest_analytics.py` — `httpx` async tests, mock `AnalyticsService`, HTTP 200 + response shape per endpoint
- `tests/unit/test_cached_analytics.py` — mock `RedisCache`, cache-hit skips repo, cache-miss calls repo and stores

### Integration tests

- `tests/integration/test_analytics_integration.py` — `@pytest.mark.integration`, skip if `SMARTTRADE_SERVER` or `REDIS_URL` not set, one test per function verifying non-None result and correct type

---

## What This Design Does Not Include

- Historical stock level trends (SmartTrade does not store inventory snapshots — only current lot state)
- Push-based alerts (webhooks, Slack notifications) — deferred to sub-project 2
- Ad-hoc NL query capability — sub-project 2
- Customer or product name resolution — `customer_id` and `product_id` are returned as IDs; name lookup requires joining to customer/product master tables not yet mapped
