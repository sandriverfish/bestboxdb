# Analytics Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 8 analytics functions (KPIs, trends, anomaly alerts) exposed via both MCP tools and REST endpoints, backed by SQL aggregation against SmartTrade with Redis cache.

**Architecture:** New vertical slice (domain → port → service → SmartTrade adapter → cache decorator → REST router + MCP tools) following the existing hexagonal pattern. Only `redis_cache.py`, `rest/main.py`, and `mcp/server.py` get additions; no structural changes to existing files.

**Tech Stack:** Python, Pydantic v2, pyodbc (SQL Server), Redis (redis-py), FastAPI, FastMCP

---

## File Map

| Action | Path | Responsibility |
|---|---|---|
| Create | `src/bestbox/core/domain/analytics.py` | 8 Pydantic models |
| Create | `src/bestbox/core/ports/analytics.py` | `AnalyticsRepositoryProtocol` |
| Create | `src/bestbox/services/analytics.py` | Thin service passthrough |
| Create | `src/bestbox/adapters/smarttrade/repositories/analytics.py` | SQL GROUP BY queries |
| Modify | `src/bestbox/adapters/cache/redis_cache.py` | Add `ttl_analytics_sec`, `ttl_analytics_alert_sec` |
| Create | `src/bestbox/adapters/cache/analytics.py` | `CachedAnalyticsRepository` decorator |
| Create | `src/bestbox/rest/routers/analytics.py` | FastAPI router, 8 GET endpoints |
| Modify | `src/bestbox/rest/main.py` | Wire `AnalyticsService` into `create_app()` |
| Create | `src/bestbox/mcp/analytics.py` | FastMCP `analyze_*` tools |
| Modify | `src/bestbox/mcp/server.py` | Build `_analytics_service`, import `mcp.analytics` |
| Create | `tests/unit/test_domain_analytics.py` | Domain model construction |
| Create | `tests/unit/test_analytics_service.py` | Service unit tests (mock repo) |
| Create | `tests/unit/test_cached_analytics.py` | Cache hit/miss unit tests |
| Create | `tests/unit/test_rest_analytics.py` | REST endpoint unit tests (httpx) |
| Create | `tests/integration/test_analytics_integration.py` | Integration tests (skipped without DB) |

---

### Task 1: Domain Models

**Files:**
- Create: `src/bestbox/core/domain/analytics.py`
- Create: `tests/unit/test_domain_analytics.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/test_domain_analytics.py
from decimal import Decimal
from datetime import datetime
from bestbox.core.domain.analytics import (
    SalesSummary, CustomerRank, ProductRank, TrendPoint,
    InventoryStatusSummary, OverdueOrder, StockCoverageAlert, LargeOrderAlert,
)

def test_sales_summary_construction():
    s = SalesSummary(
        date_from=datetime(2026, 1, 1), date_to=datetime(2026, 3, 31),
        total_revenue=Decimal("150000.00"), order_count=45, avg_order_value=Decimal("3333.33"),
    )
    assert s.order_count == 45
    assert s.total_revenue == Decimal("150000.00")

def test_customer_rank_construction():
    c = CustomerRank(customer_id=42, total_revenue=Decimal("50000"), order_count=12)
    assert c.customer_id == 42

def test_trend_point_bucket_formats():
    for bucket in ["2026-03", "2026-W12", "2026-03-25"]:
        t = TrendPoint(bucket=bucket, order_count=10, revenue=Decimal("9000"))
        assert t.bucket == bucket

def test_overdue_order_construction():
    o = OverdueOrder(
        order_id=1, order_sn="SO001", customer_id=5,
        delivery_date=datetime(2026, 3, 1), days_overdue=25,
        total_amount=Decimal("5000"),
    )
    assert o.days_overdue == 25

def test_stock_coverage_alert_shortfall():
    a = StockCoverageAlert(
        product_id=10, part_number="P001", brand="TI",
        available_qty=Decimal("100"), open_order_qty=Decimal("250"),
        shortfall=Decimal("150"),
    )
    assert a.shortfall == Decimal("150")

def test_large_order_alert_construction():
    a = LargeOrderAlert(
        order_id=1, order_sn="SO001", customer_id=5,
        total_amount=Decimal("20000"), period_average=Decimal("8000"), multiplier=2.0,
    )
    assert a.total_amount == Decimal("20000")
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/unit/test_domain_analytics.py -v
```
Expected: `ImportError: cannot import name 'SalesSummary'`

- [ ] **Step 3: Create domain models**

```python
# src/bestbox/core/domain/analytics.py
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel


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
    part_number: str | None
    brand: str | None
    qty_sold: Decimal
    total_revenue: Decimal


class TrendPoint(BaseModel):
    bucket: str
    order_count: int
    revenue: Decimal


class InventoryStatusSummary(BaseModel):
    status: int
    status_name: str
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
    part_number: str | None
    brand: str | None
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

- [ ] **Step 4: Run test to verify it passes**

```
pytest tests/unit/test_domain_analytics.py -v
```
Expected: `6 passed`

- [ ] **Step 5: Commit**

```bash
git add src/bestbox/core/domain/analytics.py tests/unit/test_domain_analytics.py
git commit -m "feat: add analytics domain models"
```

---

### Task 2: Port Protocol

**Files:**
- Create: `src/bestbox/core/ports/analytics.py`

No test — `Protocol` is structural typing, verified when concrete classes are type-checked.

- [ ] **Step 1: Create port**

```python
# src/bestbox/core/ports/analytics.py
from datetime import datetime
from typing import Protocol
from bestbox.core.domain.analytics import (
    SalesSummary, CustomerRank, ProductRank, TrendPoint,
    InventoryStatusSummary, OverdueOrder, StockCoverageAlert, LargeOrderAlert,
)


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

- [ ] **Step 2: Commit**

```bash
git add src/bestbox/core/ports/analytics.py
git commit -m "feat: add analytics repository protocol"
```

---

### Task 3: Analytics Service + Unit Tests

**Files:**
- Create: `src/bestbox/services/analytics.py`
- Create: `tests/unit/test_analytics_service.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/test_analytics_service.py
from datetime import datetime
from decimal import Decimal
from bestbox.core.domain.analytics import (
    SalesSummary, CustomerRank, ProductRank, TrendPoint,
    InventoryStatusSummary, OverdueOrder, StockCoverageAlert, LargeOrderAlert,
)
from bestbox.services.analytics import AnalyticsService

_DATE_FROM = datetime(2026, 1, 1)
_DATE_TO = datetime(2026, 3, 31)


class MockAnalyticsRepo:
    def sales_summary(self, date_from, date_to):
        return SalesSummary(date_from=date_from, date_to=date_to,
                            total_revenue=Decimal("100000"), order_count=30, avg_order_value=Decimal("3333.33"))
    def top_customers(self, date_from, date_to, limit=10):
        return [CustomerRank(customer_id=1, total_revenue=Decimal("50000"), order_count=15)]
    def top_products(self, date_from, date_to, limit=10):
        return [ProductRank(product_id=1, part_number="P001", brand="TI", qty_sold=Decimal("500"), total_revenue=Decimal("30000"))]
    def order_trend(self, date_from, date_to, bucket="month"):
        return [TrendPoint(bucket="2026-01", order_count=10, revenue=Decimal("50000"))]
    def inventory_status_summary(self):
        return [InventoryStatusSummary(status=1, status_name="Available", product_count=100, total_qty=Decimal("5000"))]
    def overdue_orders(self, as_of_date):
        return [OverdueOrder(order_id=1, order_sn="SO001", customer_id=5,
                             delivery_date=datetime(2026, 3, 1), days_overdue=25, total_amount=Decimal("5000"))]
    def stock_coverage_alert(self):
        return [StockCoverageAlert(product_id=10, part_number="P001", brand="TI",
                                   available_qty=Decimal("100"), open_order_qty=Decimal("250"), shortfall=Decimal("150"))]
    def large_order_alert(self, multiplier=2.0):
        return [LargeOrderAlert(order_id=1, order_sn="SO001", customer_id=5,
                                total_amount=Decimal("20000"), period_average=Decimal("8000"), multiplier=multiplier)]


def test_sales_summary_returns_model():
    result = AnalyticsService(repo=MockAnalyticsRepo()).sales_summary(_DATE_FROM, _DATE_TO)
    assert isinstance(result, SalesSummary)
    assert result.order_count == 30

def test_sales_summary_empty_period():
    class EmptyRepo(MockAnalyticsRepo):
        def sales_summary(self, df, dt):
            return SalesSummary(date_from=df, date_to=dt,
                                total_revenue=Decimal("0"), order_count=0, avg_order_value=Decimal("0"))
    assert AnalyticsService(repo=EmptyRepo()).sales_summary(_DATE_FROM, _DATE_TO).order_count == 0

def test_top_customers_returns_list():
    result = AnalyticsService(repo=MockAnalyticsRepo()).top_customers(_DATE_FROM, _DATE_TO, limit=5)
    assert isinstance(result, list)
    assert all(isinstance(c, CustomerRank) for c in result)

def test_top_products_returns_list():
    result = AnalyticsService(repo=MockAnalyticsRepo()).top_products(_DATE_FROM, _DATE_TO)
    assert result[0].part_number == "P001"

def test_order_trend_returns_list():
    result = AnalyticsService(repo=MockAnalyticsRepo()).order_trend(_DATE_FROM, _DATE_TO, bucket="month")
    assert result[0].bucket == "2026-01"

def test_inventory_status_summary():
    result = AnalyticsService(repo=MockAnalyticsRepo()).inventory_status_summary()
    assert result[0].status_name == "Available"

def test_overdue_orders():
    result = AnalyticsService(repo=MockAnalyticsRepo()).overdue_orders(datetime(2026, 3, 26))
    assert result[0].days_overdue == 25

def test_stock_coverage_alert():
    result = AnalyticsService(repo=MockAnalyticsRepo()).stock_coverage_alert()
    assert result[0].shortfall == Decimal("150")

def test_large_order_alert_default_multiplier():
    result = AnalyticsService(repo=MockAnalyticsRepo()).large_order_alert()
    assert result[0].multiplier == 2.0

def test_large_order_alert_custom_multiplier():
    result = AnalyticsService(repo=MockAnalyticsRepo()).large_order_alert(multiplier=3.0)
    assert result[0].multiplier == 3.0
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/unit/test_analytics_service.py -v
```
Expected: `ImportError: cannot import name 'AnalyticsService'`

- [ ] **Step 3: Create analytics service**

```python
# src/bestbox/services/analytics.py
from datetime import datetime
from bestbox.core.domain.analytics import (
    SalesSummary, CustomerRank, ProductRank, TrendPoint,
    InventoryStatusSummary, OverdueOrder, StockCoverageAlert, LargeOrderAlert,
)
from bestbox.core.ports.analytics import AnalyticsRepositoryProtocol


class AnalyticsService:
    def __init__(self, repo: AnalyticsRepositoryProtocol):
        self._repo = repo

    def sales_summary(self, date_from: datetime, date_to: datetime) -> SalesSummary:
        return self._repo.sales_summary(date_from, date_to)

    def top_customers(self, date_from: datetime, date_to: datetime, limit: int = 10) -> list[CustomerRank]:
        return self._repo.top_customers(date_from, date_to, limit=limit)

    def top_products(self, date_from: datetime, date_to: datetime, limit: int = 10) -> list[ProductRank]:
        return self._repo.top_products(date_from, date_to, limit=limit)

    def order_trend(self, date_from: datetime, date_to: datetime, bucket: str = "month") -> list[TrendPoint]:
        return self._repo.order_trend(date_from, date_to, bucket=bucket)

    def inventory_status_summary(self) -> list[InventoryStatusSummary]:
        return self._repo.inventory_status_summary()

    def overdue_orders(self, as_of_date: datetime) -> list[OverdueOrder]:
        return self._repo.overdue_orders(as_of_date)

    def stock_coverage_alert(self) -> list[StockCoverageAlert]:
        return self._repo.stock_coverage_alert()

    def large_order_alert(self, multiplier: float = 2.0) -> list[LargeOrderAlert]:
        return self._repo.large_order_alert(multiplier=multiplier)
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/unit/test_analytics_service.py -v
```
Expected: `10 passed`

- [ ] **Step 5: Commit**

```bash
git add src/bestbox/services/analytics.py tests/unit/test_analytics_service.py
git commit -m "feat: add analytics service with unit tests"
```

---

### Task 4: SmartTrade Analytics Repository

**Files:**
- Create: `src/bestbox/adapters/smarttrade/repositories/analytics.py`

No unit tests — SQL can only be validated against a live DB (covered in Task 8 integration tests).

- [ ] **Step 1: Create repository**

```python
# src/bestbox/adapters/smarttrade/repositories/analytics.py
from datetime import datetime
from decimal import Decimal

from bestbox.adapters.smarttrade.db.connection import get_connection
from bestbox.core.domain.analytics import (
    CustomerRank, InventoryStatusSummary, LargeOrderAlert, OverdueOrder,
    ProductRank, SalesSummary, StockCoverageAlert, TrendPoint,
)

_BUCKET_FORMATS = {"month": "yyyy-MM", "week": "yyyy-WW", "day": "yyyy-MM-dd"}
_STATUS_NAMES = {1: "Available", 2: "Held", 3: "Quarantine", 4: "Locked"}


class SmartTradeAnalyticsRepository:

    def sales_summary(self, date_from: datetime, date_to: datetime) -> SalesSummary:
        sql = """
            SELECT COUNT(*) AS order_count,
                   ISNULL(SUM(soAmount), 0) AS total_revenue,
                   ISNULL(AVG(soAmount), 0) AS avg_order_value
            FROM SellOrder
            WHERE soOrderDate >= ? AND soOrderDate <= ?
        """
        with get_connection() as conn:
            row = conn.cursor().execute(sql, date_from, date_to).fetchone()
        return SalesSummary(
            date_from=date_from, date_to=date_to,
            total_revenue=Decimal(str(row.total_revenue or 0)),
            order_count=int(row.order_count or 0),
            avg_order_value=Decimal(str(row.avg_order_value or 0)),
        )

    def top_customers(self, date_from: datetime, date_to: datetime, limit: int = 10) -> list[CustomerRank]:
        sql = f"""
            SELECT TOP {int(limit)}
                soCustomerID AS customer_id,
                COUNT(*) AS order_count,
                SUM(soAmount) AS total_revenue
            FROM SellOrder
            WHERE soOrderDate >= ? AND soOrderDate <= ?
            GROUP BY soCustomerID
            ORDER BY SUM(soAmount) DESC
        """
        with get_connection() as conn:
            rows = conn.cursor().execute(sql, date_from, date_to).fetchall()
        return [
            CustomerRank(
                customer_id=r.customer_id,
                total_revenue=Decimal(str(r.total_revenue or 0)),
                order_count=int(r.order_count),
            )
            for r in rows
        ]

    def top_products(self, date_from: datetime, date_to: datetime, limit: int = 10) -> list[ProductRank]:
        sql = f"""
            SELECT TOP {int(limit)}
                soi.soiProductID AS product_id,
                MAX(soi.soiPartNumber) AS part_number,
                MAX(soi.soiBrand) AS brand,
                SUM(soi.soiQty) AS qty_sold,
                SUM(soi.soiQty * soi.soiPrice) AS total_revenue
            FROM SellOrderItem soi
            JOIN SellOrder so ON soi.soiOrderID = so.soOrderID
            WHERE so.soOrderDate >= ? AND so.soOrderDate <= ?
            GROUP BY soi.soiProductID
            ORDER BY SUM(soi.soiQty * soi.soiPrice) DESC
        """
        with get_connection() as conn:
            rows = conn.cursor().execute(sql, date_from, date_to).fetchall()
        return [
            ProductRank(
                product_id=r.product_id, part_number=r.part_number, brand=r.brand,
                qty_sold=Decimal(str(r.qty_sold or 0)),
                total_revenue=Decimal(str(r.total_revenue or 0)),
            )
            for r in rows
        ]

    def order_trend(self, date_from: datetime, date_to: datetime, bucket: str = "month") -> list[TrendPoint]:
        fmt = _BUCKET_FORMATS.get(bucket, "yyyy-MM")
        sql = f"""
            SELECT FORMAT(soOrderDate, '{fmt}') AS bucket,
                   COUNT(*) AS order_count,
                   SUM(soAmount) AS revenue
            FROM SellOrder
            WHERE soOrderDate >= ? AND soOrderDate <= ?
            GROUP BY FORMAT(soOrderDate, '{fmt}')
            ORDER BY bucket
        """
        with get_connection() as conn:
            rows = conn.cursor().execute(sql, date_from, date_to).fetchall()
        return [
            TrendPoint(bucket=r.bucket, order_count=int(r.order_count),
                       revenue=Decimal(str(r.revenue or 0)))
            for r in rows
        ]

    def inventory_status_summary(self) -> list[InventoryStatusSummary]:
        sql = """
            SELECT piInventoryStatus AS status,
                   COUNT(DISTINCT piProductID) AS product_count,
                   SUM(piQty) AS total_qty
            FROM ProductInventory
            GROUP BY piInventoryStatus
            ORDER BY piInventoryStatus
        """
        with get_connection() as conn:
            rows = conn.cursor().execute(sql).fetchall()
        return [
            InventoryStatusSummary(
                status=int(r.status),
                status_name=_STATUS_NAMES.get(int(r.status), str(r.status)),
                product_count=int(r.product_count),
                total_qty=Decimal(str(r.total_qty or 0)),
            )
            for r in rows
        ]

    def overdue_orders(self, as_of_date: datetime) -> list[OverdueOrder]:
        sql = """
            SELECT so.soOrderID AS order_id,
                   so.soOrderSN AS order_sn,
                   so.soCustomerID AS customer_id,
                   so.soDeliveryDate AS delivery_date,
                   so.soAmount AS total_amount
            FROM SellOrder so
            WHERE so.soDeliveryDate < ?
              AND so.soApproveTag = 1
              AND so.soOrderID NOT IN (
                  SELECT soiOrderID
                  FROM SellOrderItem
                  GROUP BY soiOrderID
                  HAVING MIN(CASE WHEN soiExecuteTag IN (2, 3) THEN 1 ELSE 0 END) = 1
              )
            ORDER BY so.soDeliveryDate ASC
        """
        with get_connection() as conn:
            rows = conn.cursor().execute(sql, as_of_date).fetchall()
        return [
            OverdueOrder(
                order_id=r.order_id, order_sn=r.order_sn, customer_id=r.customer_id,
                delivery_date=r.delivery_date,
                days_overdue=(as_of_date - r.delivery_date).days,
                total_amount=Decimal(str(r.total_amount or 0)),
            )
            for r in rows
        ]

    def stock_coverage_alert(self) -> list[StockCoverageAlert]:
        sql = """
            WITH open_orders AS (
                SELECT soi.soiProductID,
                       SUM(soi.soiQty - ISNULL(soi.soiOutQty, 0)) AS open_order_qty
                FROM SellOrderItem soi
                JOIN SellOrder so ON soi.soiOrderID = so.soOrderID
                WHERE so.soApproveTag = 1
                  AND (soi.soiExecuteTag IS NULL OR soi.soiExecuteTag NOT IN (2, 3))
                GROUP BY soi.soiProductID
            ),
            available_stock AS (
                SELECT piProductID,
                       MAX(piPartNumber) AS part_number,
                       MAX(piBrand) AS brand,
                       SUM(CASE WHEN piInventoryStatus = 1 THEN piQty ELSE 0 END) AS available_qty
                FROM ProductInventory
                GROUP BY piProductID
            )
            SELECT av.piProductID AS product_id,
                   av.part_number,
                   av.brand,
                   av.available_qty,
                   oo.open_order_qty,
                   oo.open_order_qty - av.available_qty AS shortfall
            FROM available_stock av
            JOIN open_orders oo ON av.piProductID = oo.soiProductID
            WHERE oo.open_order_qty > av.available_qty
            ORDER BY shortfall DESC
        """
        with get_connection() as conn:
            rows = conn.cursor().execute(sql).fetchall()
        return [
            StockCoverageAlert(
                product_id=r.product_id, part_number=r.part_number, brand=r.brand,
                available_qty=Decimal(str(r.available_qty or 0)),
                open_order_qty=Decimal(str(r.open_order_qty or 0)),
                shortfall=Decimal(str(r.shortfall or 0)),
            )
            for r in rows
        ]

    def large_order_alert(self, multiplier: float = 2.0) -> list[LargeOrderAlert]:
        sql = """
            WITH rolling_avg AS (
                SELECT AVG(soAmount) AS avg_amount
                FROM SellOrder
                WHERE soOrderDate >= DATEADD(day, -90, GETDATE())
                  AND soApproveTag = 1
            )
            SELECT so.soOrderID AS order_id,
                   so.soOrderSN AS order_sn,
                   so.soCustomerID AS customer_id,
                   so.soAmount AS total_amount,
                   ra.avg_amount AS period_average
            FROM SellOrder so, rolling_avg ra
            WHERE so.soOrderDate >= DATEADD(day, -90, GETDATE())
              AND so.soApproveTag = 1
              AND so.soAmount > ? * ra.avg_amount
            ORDER BY so.soAmount DESC
        """
        with get_connection() as conn:
            rows = conn.cursor().execute(sql, multiplier).fetchall()
        return [
            LargeOrderAlert(
                order_id=r.order_id, order_sn=r.order_sn, customer_id=r.customer_id,
                total_amount=Decimal(str(r.total_amount or 0)),
                period_average=Decimal(str(r.period_average or 0)),
                multiplier=multiplier,
            )
            for r in rows
        ]
```

- [ ] **Step 2: Commit**

```bash
git add src/bestbox/adapters/smarttrade/repositories/analytics.py
git commit -m "feat: add SmartTrade analytics repository with SQL aggregations"
```

---

### Task 5: CacheConfig TTL Fields + Cached Analytics Repository

**Files:**
- Modify: `src/bestbox/adapters/cache/redis_cache.py`
- Create: `src/bestbox/adapters/cache/analytics.py`
- Create: `tests/unit/test_cached_analytics.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/test_cached_analytics.py
import json
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock
from bestbox.adapters.cache.analytics import CachedAnalyticsRepository
from bestbox.adapters.cache.redis_cache import CacheConfig
from bestbox.core.domain.analytics import (
    SalesSummary, CustomerRank, TrendPoint, InventoryStatusSummary,
    OverdueOrder, StockCoverageAlert, LargeOrderAlert, ProductRank,
)

_DATE_FROM = datetime(2026, 1, 1)
_DATE_TO = datetime(2026, 3, 31)


def _make_summary():
    return SalesSummary(date_from=_DATE_FROM, date_to=_DATE_TO,
                        total_revenue=Decimal("100000"), order_count=30, avg_order_value=Decimal("3333.33"))


def test_sales_summary_cache_miss_calls_repo():
    mock_repo = MagicMock()
    mock_repo.sales_summary.return_value = _make_summary()
    cache = MagicMock()
    cache.get.return_value = None
    repo = CachedAnalyticsRepository(mock_repo, cache, CacheConfig())

    result = repo.sales_summary(_DATE_FROM, _DATE_TO)

    mock_repo.sales_summary.assert_called_once_with(_DATE_FROM, _DATE_TO)
    cache.set.assert_called_once()
    assert result.order_count == 30


def test_sales_summary_cache_hit_skips_repo():
    mock_repo = MagicMock()
    cache = MagicMock()
    cache.get.return_value = _make_summary().model_dump_json()
    repo = CachedAnalyticsRepository(mock_repo, cache, CacheConfig())

    result = repo.sales_summary(_DATE_FROM, _DATE_TO)

    mock_repo.sales_summary.assert_not_called()
    assert result.order_count == 30


def test_top_customers_cache_miss():
    mock_repo = MagicMock()
    mock_repo.top_customers.return_value = [
        CustomerRank(customer_id=1, total_revenue=Decimal("50000"), order_count=15)
    ]
    cache = MagicMock()
    cache.get.return_value = None
    repo = CachedAnalyticsRepository(mock_repo, cache, CacheConfig())

    result = repo.top_customers(_DATE_FROM, _DATE_TO, limit=10)

    mock_repo.top_customers.assert_called_once()
    assert len(result) == 1


def test_top_customers_cache_hit():
    data = [{"customer_id": 1, "total_revenue": "50000", "order_count": 15}]
    cache = MagicMock()
    cache.get.return_value = json.dumps(data)
    mock_repo = MagicMock()
    repo = CachedAnalyticsRepository(mock_repo, cache, CacheConfig())

    result = repo.top_customers(_DATE_FROM, _DATE_TO)

    mock_repo.top_customers.assert_not_called()
    assert result[0].customer_id == 1


def test_invalid_cache_payload_falls_back_to_repo():
    mock_repo = MagicMock()
    mock_repo.sales_summary.return_value = _make_summary()
    cache = MagicMock()
    cache.get.return_value = "not-valid-json{{"
    repo = CachedAnalyticsRepository(mock_repo, cache, CacheConfig())

    result = repo.sales_summary(_DATE_FROM, _DATE_TO)

    mock_repo.sales_summary.assert_called_once()
    assert result.order_count == 30


def test_overdue_orders_uses_alert_ttl():
    mock_repo = MagicMock()
    mock_repo.overdue_orders.return_value = []
    cache = MagicMock()
    cache.get.return_value = None
    config = CacheConfig()
    repo = CachedAnalyticsRepository(mock_repo, cache, config)

    repo.overdue_orders(datetime(2026, 3, 26))

    ttl_used = cache.set.call_args[0][2]
    assert ttl_used == config.ttl_analytics_alert_sec


def test_stock_coverage_uses_alert_ttl():
    mock_repo = MagicMock()
    mock_repo.stock_coverage_alert.return_value = []
    cache = MagicMock()
    cache.get.return_value = None
    config = CacheConfig()
    repo = CachedAnalyticsRepository(mock_repo, cache, config)

    repo.stock_coverage_alert()

    ttl_used = cache.set.call_args[0][2]
    assert ttl_used == config.ttl_analytics_alert_sec
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/unit/test_cached_analytics.py -v
```
Expected: `ImportError: cannot import name 'CachedAnalyticsRepository'`

- [ ] **Step 3: Add TTL fields to `CacheConfig`**

In `src/bestbox/adapters/cache/redis_cache.py`, append after `ttl_low_stock_sec`:

```python
    ttl_analytics_sec: int = field(
        default_factory=lambda: _get_env_int("CACHE_TTL_ANALYTICS_SEC", 600)
    )
    ttl_analytics_alert_sec: int = field(
        default_factory=lambda: _get_env_int("CACHE_TTL_ANALYTICS_ALERT_SEC", 300)
    )
```

- [ ] **Step 4: Create cached analytics repository**

```python
# src/bestbox/adapters/cache/analytics.py
import hashlib
import json
import logging
from datetime import datetime

from pydantic import ValidationError

from bestbox.adapters.cache.redis_cache import CacheConfig, RedisCache
from bestbox.core.domain.analytics import (
    CustomerRank, InventoryStatusSummary, LargeOrderAlert, OverdueOrder,
    ProductRank, SalesSummary, StockCoverageAlert, TrendPoint,
)

logger = logging.getLogger(__name__)


def _list_cache_key(prefix: str, params: dict) -> str:
    payload = json.dumps(params, sort_keys=True, default=str)
    return f"{prefix}:{hashlib.sha256(payload.encode()).hexdigest()}"


class CachedAnalyticsRepository:
    def __init__(self, repo, cache: RedisCache, config: CacheConfig):
        self._repo = repo
        self._cache = cache
        self._config = config

    def _get(self, key: str) -> str | None:
        try:
            return self._cache.get(key)
        except Exception as exc:
            logger.warning("Analytics cache read failed for %s: %s", key, exc)
            return None

    def _set(self, key: str, value: str, ttl: int) -> None:
        try:
            self._cache.set(key, value, ttl)
        except Exception as exc:
            logger.warning("Analytics cache write failed for %s: %s", key, exc)

    def _load_single(self, key: str, model_cls):
        raw = self._get(key)
        if raw is None:
            return None
        try:
            return model_cls.model_validate_json(raw)
        except (ValidationError, ValueError, TypeError) as exc:
            logger.warning("Analytics cache invalid for %s: %s", key, exc)
            return None

    def _load_list(self, key: str, model_cls):
        raw = self._get(key)
        if raw is None:
            return None
        try:
            return [model_cls.model_validate(item) for item in json.loads(raw)]
        except (ValidationError, ValueError, TypeError) as exc:
            logger.warning("Analytics cache invalid for %s: %s", key, exc)
            return None

    def sales_summary(self, date_from: datetime, date_to: datetime) -> SalesSummary:
        key = _list_cache_key("bestbox:analytics:sales_summary", {"df": date_from, "dt": date_to})
        cached = self._load_single(key, SalesSummary)
        if cached is not None:
            return cached
        result = self._repo.sales_summary(date_from, date_to)
        self._set(key, result.model_dump_json(), self._config.ttl_analytics_sec)
        return result

    def top_customers(self, date_from: datetime, date_to: datetime, limit: int = 10) -> list[CustomerRank]:
        key = _list_cache_key("bestbox:analytics:top_customers", {"df": date_from, "dt": date_to, "limit": limit})
        cached = self._load_list(key, CustomerRank)
        if cached is not None:
            return cached
        result = self._repo.top_customers(date_from, date_to, limit=limit)
        self._set(key, json.dumps([r.model_dump(mode="json") for r in result]), self._config.ttl_analytics_sec)
        return result

    def top_products(self, date_from: datetime, date_to: datetime, limit: int = 10) -> list[ProductRank]:
        key = _list_cache_key("bestbox:analytics:top_products", {"df": date_from, "dt": date_to, "limit": limit})
        cached = self._load_list(key, ProductRank)
        if cached is not None:
            return cached
        result = self._repo.top_products(date_from, date_to, limit=limit)
        self._set(key, json.dumps([r.model_dump(mode="json") for r in result]), self._config.ttl_analytics_sec)
        return result

    def order_trend(self, date_from: datetime, date_to: datetime, bucket: str = "month") -> list[TrendPoint]:
        key = _list_cache_key("bestbox:analytics:order_trend", {"df": date_from, "dt": date_to, "bucket": bucket})
        cached = self._load_list(key, TrendPoint)
        if cached is not None:
            return cached
        result = self._repo.order_trend(date_from, date_to, bucket=bucket)
        self._set(key, json.dumps([r.model_dump(mode="json") for r in result]), self._config.ttl_analytics_sec)
        return result

    def inventory_status_summary(self) -> list[InventoryStatusSummary]:
        key = "bestbox:analytics:inventory_status"
        cached = self._load_list(key, InventoryStatusSummary)
        if cached is not None:
            return cached
        result = self._repo.inventory_status_summary()
        self._set(key, json.dumps([r.model_dump(mode="json") for r in result]), self._config.ttl_analytics_sec)
        return result

    def overdue_orders(self, as_of_date: datetime) -> list[OverdueOrder]:
        key = _list_cache_key("bestbox:analytics:overdue", {"as_of": as_of_date})
        cached = self._load_list(key, OverdueOrder)
        if cached is not None:
            return cached
        result = self._repo.overdue_orders(as_of_date)
        self._set(key, json.dumps([r.model_dump(mode="json") for r in result]), self._config.ttl_analytics_alert_sec)
        return result

    def stock_coverage_alert(self) -> list[StockCoverageAlert]:
        key = "bestbox:analytics:stock_coverage"
        cached = self._load_list(key, StockCoverageAlert)
        if cached is not None:
            return cached
        result = self._repo.stock_coverage_alert()
        self._set(key, json.dumps([r.model_dump(mode="json") for r in result]), self._config.ttl_analytics_alert_sec)
        return result

    def large_order_alert(self, multiplier: float = 2.0) -> list[LargeOrderAlert]:
        key = _list_cache_key("bestbox:analytics:large_orders", {"multiplier": multiplier})
        cached = self._load_list(key, LargeOrderAlert)
        if cached is not None:
            return cached
        result = self._repo.large_order_alert(multiplier=multiplier)
        self._set(key, json.dumps([r.model_dump(mode="json") for r in result]), self._config.ttl_analytics_alert_sec)
        return result
```

- [ ] **Step 5: Run tests to verify they pass**

```
pytest tests/unit/test_cached_analytics.py -v
```
Expected: `7 passed`

- [ ] **Step 6: Commit**

```bash
git add src/bestbox/adapters/cache/redis_cache.py src/bestbox/adapters/cache/analytics.py tests/unit/test_cached_analytics.py
git commit -m "feat: add CachedAnalyticsRepository with TTL config fields"
```

---

### Task 6: REST Router + Unit Tests

**Files:**
- Create: `src/bestbox/rest/routers/analytics.py`
- Modify: `src/bestbox/rest/main.py`
- Create: `tests/unit/test_rest_analytics.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/test_rest_analytics.py
from datetime import datetime
from decimal import Decimal
import pytest
from httpx import AsyncClient, ASGITransport
from bestbox.rest.main import create_app
from bestbox.services.analytics import AnalyticsService
from bestbox.core.domain.analytics import (
    SalesSummary, CustomerRank, TrendPoint, InventoryStatusSummary,
    OverdueOrder, StockCoverageAlert, LargeOrderAlert, ProductRank,
)

_DATE_FROM = datetime(2026, 1, 1)
_DATE_TO = datetime(2026, 3, 31)


class MockAnalyticsRepo:
    def sales_summary(self, df, dt):
        return SalesSummary(date_from=df, date_to=dt,
                            total_revenue=Decimal("100000"), order_count=30, avg_order_value=Decimal("3333"))
    def top_customers(self, df, dt, limit=10):
        return [CustomerRank(customer_id=1, total_revenue=Decimal("50000"), order_count=15)]
    def top_products(self, df, dt, limit=10):
        return [ProductRank(product_id=1, part_number="P001", brand="TI", qty_sold=Decimal("500"), total_revenue=Decimal("30000"))]
    def order_trend(self, df, dt, bucket="month"):
        return [TrendPoint(bucket="2026-01", order_count=10, revenue=Decimal("50000"))]
    def inventory_status_summary(self):
        return [InventoryStatusSummary(status=1, status_name="Available", product_count=100, total_qty=Decimal("5000"))]
    def overdue_orders(self, as_of_date):
        return [OverdueOrder(order_id=1, order_sn="SO001", customer_id=5,
                             delivery_date=datetime(2026, 3, 1), days_overdue=25, total_amount=Decimal("5000"))]
    def stock_coverage_alert(self):
        return [StockCoverageAlert(product_id=10, part_number="P001", brand="TI",
                                   available_qty=Decimal("100"), open_order_qty=Decimal("250"), shortfall=Decimal("150"))]
    def large_order_alert(self, multiplier=2.0):
        return [LargeOrderAlert(order_id=1, order_sn="SO001", customer_id=5,
                                total_amount=Decimal("20000"), period_average=Decimal("8000"), multiplier=multiplier)]


@pytest.fixture
def analytics_app():
    service = AnalyticsService(repo=MockAnalyticsRepo())
    return create_app(analytics_service=service)


@pytest.mark.asyncio
async def test_sales_summary_200(analytics_app):
    async with AsyncClient(transport=ASGITransport(app=analytics_app), base_url="http://test") as client:
        r = await client.get("/api/v1/analytics/sales/summary",
                             params={"date_from": "2026-01-01", "date_to": "2026-03-31"})
    assert r.status_code == 200
    assert r.json()["order_count"] == 30


@pytest.mark.asyncio
async def test_sales_summary_missing_params_422(analytics_app):
    async with AsyncClient(transport=ASGITransport(app=analytics_app), base_url="http://test") as client:
        r = await client.get("/api/v1/analytics/sales/summary")
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_top_customers_200(analytics_app):
    async with AsyncClient(transport=ASGITransport(app=analytics_app), base_url="http://test") as client:
        r = await client.get("/api/v1/analytics/sales/top-customers",
                             params={"date_from": "2026-01-01", "date_to": "2026-03-31"})
    assert r.status_code == 200
    assert r.json()[0]["customer_id"] == 1


@pytest.mark.asyncio
async def test_top_products_200(analytics_app):
    async with AsyncClient(transport=ASGITransport(app=analytics_app), base_url="http://test") as client:
        r = await client.get("/api/v1/analytics/sales/top-products",
                             params={"date_from": "2026-01-01", "date_to": "2026-03-31"})
    assert r.status_code == 200
    assert r.json()[0]["product_id"] == 1


@pytest.mark.asyncio
async def test_order_trend_200(analytics_app):
    async with AsyncClient(transport=ASGITransport(app=analytics_app), base_url="http://test") as client:
        r = await client.get("/api/v1/analytics/sales/trend",
                             params={"date_from": "2026-01-01", "date_to": "2026-03-31", "bucket": "month"})
    assert r.status_code == 200
    assert r.json()[0]["bucket"] == "2026-01"


@pytest.mark.asyncio
async def test_inventory_status_200(analytics_app):
    async with AsyncClient(transport=ASGITransport(app=analytics_app), base_url="http://test") as client:
        r = await client.get("/api/v1/analytics/inventory/status")
    assert r.status_code == 200
    assert r.json()[0]["status_name"] == "Available"


@pytest.mark.asyncio
async def test_overdue_orders_200(analytics_app):
    async with AsyncClient(transport=ASGITransport(app=analytics_app), base_url="http://test") as client:
        r = await client.get("/api/v1/analytics/alerts/overdue-orders")
    assert r.status_code == 200
    assert r.json()[0]["days_overdue"] == 25


@pytest.mark.asyncio
async def test_stock_coverage_200(analytics_app):
    async with AsyncClient(transport=ASGITransport(app=analytics_app), base_url="http://test") as client:
        r = await client.get("/api/v1/analytics/alerts/stock-coverage")
    assert r.status_code == 200
    assert r.json()[0]["shortfall"] == "150"


@pytest.mark.asyncio
async def test_large_orders_200(analytics_app):
    async with AsyncClient(transport=ASGITransport(app=analytics_app), base_url="http://test") as client:
        r = await client.get("/api/v1/analytics/alerts/large-orders", params={"multiplier": "2.0"})
    assert r.status_code == 200
    assert r.json()[0]["order_id"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/unit/test_rest_analytics.py -v
```
Expected: `TypeError` — `create_app` doesn't accept `analytics_service` yet

- [ ] **Step 3: Create analytics REST router**

```python
# src/bestbox/rest/routers/analytics.py
from datetime import datetime
from fastapi import APIRouter, Query
from bestbox.services.analytics import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["analytics"])
_service: AnalyticsService | None = None


def set_service(service: AnalyticsService) -> None:
    global _service
    _service = service


@router.get("/sales/summary")
def sales_summary(date_from: datetime = Query(...), date_to: datetime = Query(...)):
    return _service.sales_summary(date_from, date_to).model_dump(mode="json")


@router.get("/sales/top-customers")
def top_customers(date_from: datetime = Query(...), date_to: datetime = Query(...),
                  limit: int = Query(default=10, le=50)):
    return [r.model_dump(mode="json") for r in _service.top_customers(date_from, date_to, limit=limit)]


@router.get("/sales/top-products")
def top_products(date_from: datetime = Query(...), date_to: datetime = Query(...),
                 limit: int = Query(default=10, le=50)):
    return [r.model_dump(mode="json") for r in _service.top_products(date_from, date_to, limit=limit)]


@router.get("/sales/trend")
def order_trend(date_from: datetime = Query(...), date_to: datetime = Query(...),
                bucket: str = Query(default="month", pattern="^(month|week|day)$")):
    return [r.model_dump(mode="json") for r in _service.order_trend(date_from, date_to, bucket=bucket)]


@router.get("/inventory/status")
def inventory_status():
    return [r.model_dump(mode="json") for r in _service.inventory_status_summary()]


@router.get("/alerts/overdue-orders")
def overdue_orders(as_of: datetime = Query(default=None)):
    as_of_date = as_of or datetime.utcnow()
    return [r.model_dump(mode="json") for r in _service.overdue_orders(as_of_date)]


@router.get("/alerts/stock-coverage")
def stock_coverage():
    return [r.model_dump(mode="json") for r in _service.stock_coverage_alert()]


@router.get("/alerts/large-orders")
def large_orders(multiplier: float = Query(default=2.0, gt=0)):
    return [r.model_dump(mode="json") for r in _service.large_order_alert(multiplier=multiplier)]
```

- [ ] **Step 4: Update `src/bestbox/rest/main.py`**

Add import at top (after existing imports):
```python
from bestbox.services.analytics import AnalyticsService
from bestbox.rest.routers import analytics as analytics_router_mod
```

Replace `_build_default_services` entirely:
```python
def _build_default_services() -> tuple[OrderService, InventoryService, AnalyticsService]:
    from bestbox.adapters.smarttrade.repositories.orders import SmartTradeOrderRepository
    from bestbox.adapters.smarttrade.repositories.inventory import SmartTradeInventoryRepository
    from bestbox.adapters.smarttrade.repositories.analytics import SmartTradeAnalyticsRepository

    order_repo = SmartTradeOrderRepository()
    inventory_repo = SmartTradeInventoryRepository()
    analytics_repo = SmartTradeAnalyticsRepository()

    try:
        from bestbox.adapters.cache.inventory import CachedInventoryRepository
        from bestbox.adapters.cache.orders import CachedOrderRepository
        from bestbox.adapters.cache.analytics import CachedAnalyticsRepository
        from bestbox.adapters.cache.redis_cache import CacheConfig, RedisCache

        config = CacheConfig()
        cache = RedisCache(config)
        if cache.ping():
            order_repo = CachedOrderRepository(order_repo, cache, config)
            inventory_repo = CachedInventoryRepository(inventory_repo, cache, config)
            analytics_repo = CachedAnalyticsRepository(analytics_repo, cache, config)
        else:
            logger.warning("Redis unreachable at %s; running without cache", config.redis_url)
    except (ImportError, TypeError, ValueError) as exc:
        logger.warning("Redis cache initialization failed; running without cache: %s", exc)

    return (
        OrderService(repo=order_repo),
        InventoryService(repo=inventory_repo),
        AnalyticsService(repo=analytics_repo),
    )
```

Replace `create_app` signature and body:
```python
def create_app(
    order_service: OrderService | None = None,
    inventory_service: InventoryService | None = None,
    analytics_service: AnalyticsService | None = None,
) -> FastAPI:
    application = FastAPI(title="BestBox ERP Gateway", version="0.1.0")

    if order_service is None or inventory_service is None or analytics_service is None:
        default_order, default_inventory, default_analytics = _build_default_services()
        if order_service is None:
            order_service = default_order
        if inventory_service is None:
            inventory_service = default_inventory
        if analytics_service is None:
            analytics_service = default_analytics

    orders_router_mod.set_service(order_service)
    inventory_router_mod.set_service(inventory_service)
    analytics_router_mod.set_service(analytics_service)

    application.include_router(orders_router_mod.router, prefix="/api/v1")
    application.include_router(inventory_router_mod.router, prefix="/api/v1")
    application.include_router(analytics_router_mod.router, prefix="/api/v1")

    return application
```

- [ ] **Step 5: Run tests**

```
pytest tests/unit/test_rest_analytics.py tests/unit/test_rest_orders.py tests/unit/test_rest_inventory.py -v
```
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add src/bestbox/rest/routers/analytics.py src/bestbox/rest/main.py tests/unit/test_rest_analytics.py
git commit -m "feat: add analytics REST endpoints and wire into create_app"
```

---

### Task 7: MCP Analytics Tools

**Files:**
- Create: `src/bestbox/mcp/analytics.py`
- Modify: `src/bestbox/mcp/server.py`

- [ ] **Step 1: Update `_build_services()` in `mcp/server.py`**

Replace the existing `_build_services` function and unpacking line with:

```python
def _build_services():
    from bestbox.adapters.smarttrade.repositories.orders import SmartTradeOrderRepository
    from bestbox.adapters.smarttrade.repositories.inventory import SmartTradeInventoryRepository
    from bestbox.adapters.smarttrade.repositories.analytics import SmartTradeAnalyticsRepository

    order_repo = SmartTradeOrderRepository()
    inventory_repo = SmartTradeInventoryRepository()
    analytics_repo = SmartTradeAnalyticsRepository()

    try:
        from bestbox.adapters.cache.inventory import CachedInventoryRepository
        from bestbox.adapters.cache.orders import CachedOrderRepository
        from bestbox.adapters.cache.analytics import CachedAnalyticsRepository
        from bestbox.adapters.cache.redis_cache import CacheConfig, RedisCache

        config = CacheConfig()
        cache = RedisCache(config)
        if cache.ping():
            order_repo = CachedOrderRepository(order_repo, cache, config)
            inventory_repo = CachedInventoryRepository(inventory_repo, cache, config)
            analytics_repo = CachedAnalyticsRepository(analytics_repo, cache, config)
        else:
            logger.warning("Redis unreachable at %s; running without cache", config.redis_url)
    except (ImportError, TypeError, ValueError) as exc:
        logger.warning("Redis cache initialization failed; running without cache: %s", exc)

    from bestbox.services.analytics import AnalyticsService
    return (
        OrderService(repo=order_repo),
        InventoryService(repo=inventory_repo),
        AnalyticsService(repo=analytics_repo),
    )


_order_service, _inventory_service, _analytics_service = _build_services()
```

At the bottom of `server.py`, before `if __name__ == "__main__":`, add:
```python
import bestbox.mcp.analytics  # noqa: F401 — registers analyze_* tools as side effect
```

- [ ] **Step 2: Create MCP analytics tools**

```python
# src/bestbox/mcp/analytics.py
from datetime import datetime

from bestbox.mcp.server import _analytics_service, mcp


@mcp.tool()
def analyze_sales_summary(date_from: str, date_to: str) -> dict:
    """Return total revenue, order count, and average order value for a date range."""
    return _analytics_service.sales_summary(
        datetime.fromisoformat(date_from), datetime.fromisoformat(date_to)
    ).model_dump(mode="json")


@mcp.tool()
def analyze_top_customers(date_from: str, date_to: str, limit: int = 10) -> list[dict]:
    """Return top N customers by revenue for a date range."""
    return [r.model_dump(mode="json") for r in _analytics_service.top_customers(
        datetime.fromisoformat(date_from), datetime.fromisoformat(date_to), limit=min(limit, 50)
    )]


@mcp.tool()
def analyze_top_products(date_from: str, date_to: str, limit: int = 10) -> list[dict]:
    """Return top N products by revenue for a date range."""
    return [r.model_dump(mode="json") for r in _analytics_service.top_products(
        datetime.fromisoformat(date_from), datetime.fromisoformat(date_to), limit=min(limit, 50)
    )]


@mcp.tool()
def analyze_order_trend(date_from: str, date_to: str, bucket: str = "month") -> list[dict]:
    """Return order count and revenue time series. bucket: month | week | day."""
    return [r.model_dump(mode="json") for r in _analytics_service.order_trend(
        datetime.fromisoformat(date_from), datetime.fromisoformat(date_to), bucket=bucket
    )]


@mcp.tool()
def analyze_inventory_status() -> list[dict]:
    """Return product count and total quantity grouped by inventory status."""
    return [r.model_dump(mode="json") for r in _analytics_service.inventory_status_summary()]


@mcp.tool()
def analyze_overdue_orders(as_of: str | None = None) -> list[dict]:
    """Return approved orders past delivery date that are not fully fulfilled. Default as_of is today."""
    as_of_date = datetime.fromisoformat(as_of) if as_of else datetime.utcnow()
    return [r.model_dump(mode="json") for r in _analytics_service.overdue_orders(as_of_date)]


@mcp.tool()
def analyze_stock_coverage() -> list[dict]:
    """Return products where open order quantity exceeds available inventory."""
    return [r.model_dump(mode="json") for r in _analytics_service.stock_coverage_alert()]


@mcp.tool()
def analyze_large_orders(multiplier: float = 2.0) -> list[dict]:
    """Return orders in the last 90 days exceeding multiplier × 90-day average order value."""
    return [r.model_dump(mode="json") for r in _analytics_service.large_order_alert(multiplier=multiplier)]
```

- [ ] **Step 3: Verify MCP server imports cleanly**

```
python -c "import bestbox.mcp.server; print('OK')"
```
Expected: `OK` (Redis warning is acceptable)

- [ ] **Step 4: Run all unit tests**

```
pytest tests/unit/ -v
```
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add src/bestbox/mcp/analytics.py src/bestbox/mcp/server.py
git commit -m "feat: add MCP analytics tools and wire into server"
```

---

### Task 8: Integration Test Scaffold

**Files:**
- Create: `tests/integration/test_analytics_integration.py`

These tests are skipped unless the `integration` pytest mark is active and `SMARTTRADE_SERVER` / `REDIS_URL` env vars are set.

- [ ] **Step 1: Create integration test file**

```python
# tests/integration/test_analytics_integration.py
from datetime import datetime
import pytest
from bestbox.adapters.smarttrade.repositories.analytics import SmartTradeAnalyticsRepository
from bestbox.core.domain.analytics import (
    SalesSummary, CustomerRank, ProductRank, TrendPoint,
    InventoryStatusSummary, OverdueOrder, StockCoverageAlert, LargeOrderAlert,
)

pytestmark = pytest.mark.integration

_DATE_FROM = datetime(2025, 1, 1)
_DATE_TO = datetime(2025, 12, 31)


@pytest.fixture
def repo():
    return SmartTradeAnalyticsRepository()


def test_sales_summary(repo):
    result = repo.sales_summary(_DATE_FROM, _DATE_TO)
    assert isinstance(result, SalesSummary)
    assert result.order_count >= 0
    assert result.total_revenue >= 0


def test_top_customers(repo):
    result = repo.top_customers(_DATE_FROM, _DATE_TO, limit=5)
    assert isinstance(result, list)
    assert len(result) <= 5
    for c in result:
        assert isinstance(c, CustomerRank)
        assert c.customer_id > 0


def test_top_products(repo):
    result = repo.top_products(_DATE_FROM, _DATE_TO, limit=5)
    for p in result:
        assert isinstance(p, ProductRank)
        assert p.product_id > 0


def test_order_trend_month(repo):
    result = repo.order_trend(_DATE_FROM, _DATE_TO, bucket="month")
    for t in result:
        assert isinstance(t, TrendPoint)
        assert len(t.bucket) == 7  # "yyyy-MM"


def test_order_trend_day(repo):
    result = repo.order_trend(_DATE_FROM, _DATE_TO, bucket="day")
    for t in result:
        assert len(t.bucket) == 10  # "yyyy-MM-dd"


def test_inventory_status_summary(repo):
    result = repo.inventory_status_summary()
    assert isinstance(result, list)
    for s in result:
        assert isinstance(s, InventoryStatusSummary)
        assert s.product_count >= 0


def test_overdue_orders(repo):
    result = repo.overdue_orders(datetime.utcnow())
    for o in result:
        assert isinstance(o, OverdueOrder)
        assert o.days_overdue >= 0


def test_stock_coverage_alert(repo):
    result = repo.stock_coverage_alert()
    for a in result:
        assert isinstance(a, StockCoverageAlert)
        assert a.shortfall > 0


def test_large_order_alert(repo):
    result = repo.large_order_alert(multiplier=1.5)
    for a in result:
        assert isinstance(a, LargeOrderAlert)
        assert float(a.total_amount) > float(a.period_average) * 1.5 * 0.99  # float tolerance
```

- [ ] **Step 2: Verify unit tests still pass (integration tests skip without DB)**

```
pytest tests/unit/ -v
```
Expected: all pass

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_analytics_integration.py
git commit -m "feat: add analytics integration test scaffold"
```
