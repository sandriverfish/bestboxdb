# Redis Cache Layer Design

**Date:** 2026-03-25
**Status:** Approved
**Scope:** Add a Redis-backed caching layer to BestBox to reduce SQL Server load and accelerate agent query responses.

---

## Context

BestBox currently hits SmartTrade SQL Server on every MCP tool call and REST request. There is no measured latency or load problem today, but caching is being added proactively as agent usage grows. The design prioritises operational simplicity and graceful degradation over cache freshness guarantees.

---

## Architecture

The cache is implemented as a **decorator repository pattern**. `CachedOrderRepository` and `CachedInventoryRepository` each wrap the corresponding SmartTrade repository and implement the same `Protocol`, making them transparent to the service layer.

```
MCP tools / REST routers
        │
   OrderService / InventoryService          (unchanged)
        │
CachedOrderRepository                       (NEW — checks Redis first)
        │ on miss
SmartTradeOrderRepository                   (unchanged — hits SQL Server)
        │
    SmartTrade SQL Server
```

### New files

```
src/bestbox/adapters/cache/
    __init__.py
    redis_cache.py          — RedisCache helper: get / set / invalidate
    orders.py               — CachedOrderRepository decorator
    inventory.py            — CachedInventoryRepository decorator
```

### Wiring changes

- `src/bestbox/rest/main.py` — `create_app()` wraps SmartTrade repos with cached counterparts
- `src/bestbox/mcp/server.py` — module-level service init wraps SmartTrade repos with cached counterparts

### New dependency

- `redis` (redis-py) added to `pyproject.toml` dependencies
- `REDIS_URL` env var (default: `redis://localhost:6379`)

---

## Cache Keys & TTL

All keys are prefixed `bestbox:` for easy identification and bulk flush (`redis-cli KEYS bestbox:*`).

| Query | Cache Key | TTL |
|---|---|---|
| `get_sales_order(order_id)` | `bestbox:so:{order_id}` | 60 sec |
| `list_sales_orders(**params)` | `bestbox:so:list:{sha256(params)}` | 3 min |
| `get_purchase_order(order_id)` | `bestbox:po:{order_id}` | 5 min |
| `list_purchase_orders(**params)` | `bestbox:po:list:{sha256(params)}` | 5 min |
| `check_stock(part_number)` | `bestbox:inv:stock:{part_number}` | 2 min |
| `get_inventory_lots(product_id)` | `bestbox:inv:lots:{product_id}` | 2 min |
| `list_low_stock(threshold)` | `bestbox:inv:lowstock:{threshold}` | 5 min |

List query keys hash all filter parameters (`customer_id`, `date_from`, `date_to`, `status`, `limit`) using SHA-256 of their sorted JSON representation (`json.dumps(params, sort_keys=True, default=str)`), so different filter combinations get independent cache entries.

TTLs are defined in a single `CacheConfig` dataclass and overridable via env vars (e.g., `CACHE_TTL_STOCK_SEC=120`).

---

## Serialisation

Pydantic domain models are stored as JSON strings using the existing `model_dump(mode="json")` pattern (handles `Decimal` correctly). On cache hit, results are deserialised with `model_validate()`.

```
Miss:  SQL → Pydantic model → model_dump(mode="json") → Redis SET(key, json, ex=ttl)
Hit:   Redis GET(key) → JSON string → model_validate(json) → Pydantic model
```

---

## Fallback Behaviour

Redis errors never propagate to callers. `RedisCache` wraps every operation:

- **GET failure** → treated as cache miss; falls through to SQL normally
- **SET failure** → logs a warning at `WARNING` level; returns the SQL result anyway

If `REDIS_URL` is unreachable at startup, `create_app()` and the MCP server init log a warning and continue with the unwrapped SmartTrade repositories. The system is fully operational without Redis.

---

## Manual Invalidation

`RedisCache.invalidate(pattern: str)` uses redis-py's `scan_iter(pattern)` + `delete` to flush targeted entries without blocking the server. Intended for ops use (e.g., after a manual ERP correction). No automatic write-through or pub/sub invalidation in this design.

Example:
```python
cache.invalidate("bestbox:so:35171")       # flush one order
cache.invalidate("bestbox:inv:stock:*")    # flush all stock checks
```

---

## Testing

### Unit tests (no Redis, no SQL)

- `CachedOrderRepository`: mock `RedisCache` — assert cache hit skips repo call; assert cache miss calls repo and stores result
- `CachedInventoryRepository`: same pattern
- Fallback: mock `RedisCache.get` raises `ConnectionError` — assert data still returned, no exception raised

### Integration tests (`@pytest.mark.integration`)

- Require `REDIS_URL` env var; skipped otherwise
- Second call for same query returns matching result
- TTL expiry: set 1-sec TTL via env override, sleep 1.1 sec, assert next call hits SQL

### Existing tests

No changes. SmartTrade repository tests and service tests are unaffected.

---

## Deployment

### Local development

```bash
docker run -d -p 6379:6379 redis:7-alpine
# add to .env:
REDIS_URL=redis://localhost:6379
```

### Production

Run Redis on the same host or LAN as the BestBox process. Redis does not need persistence (`--save ""`) since all cached data is derived from the ERP and TTL-bounded.

---

## What This Design Does Not Include

- Pub/sub invalidation triggered by ERP data changes (CDC / SQL triggers)
- Cache warming on startup
- Cache metrics / hit-rate monitoring
- Horizontal scaling with Redis Cluster

These are deferred until a measured need arises.
