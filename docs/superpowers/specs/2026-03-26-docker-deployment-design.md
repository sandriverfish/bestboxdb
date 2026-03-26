# BestBox Docker Deployment Design

**Date:** 2026-03-26
**Status:** Approved
**Scope:** Deploy BestBox REST API and MCP server as Docker containers on `apexvue@192.168.1.98`, with SQL Server 2022 auto-restoring the SmartTrade database from an existing `.bak` backup, and the MCP server accessible to remote Claude Code clients via SSE transport.

---

## Context

BestBox currently runs on a developer's local machine against a customer on-site SmartTrade ERP server. This deployment makes BestBox available as a persistent enterprise service on a dedicated server, decoupled from the developer machine, so AI agents can query SmartTrade data at any time.

The target server (`192.168.1.98`) already has:
- Docker 29.3.0 on Ubuntu 24.04
- A private Docker registry running at port 5000
- SmartTrade SQL Server backup files at `/data/yishang/`
- 1.6 TB free storage, 15 GB RAM, 8 CPU cores

---

## Architecture

```
Dev machine
  │
  ├── docker build → 192.168.1.98:5000/bestbox:latest
  │
  └── ssh deploy

192.168.1.98 (Docker host)
  │
  ├── docker-compose.infra.yml
  │     ├── sqlserver   (SQL Server 2022, port 1433 internal)
  │     └── redis       (Redis 7 Alpine, port 6379 internal)
  │
  └── docker-compose.app.yml
        ├── bestbox-api  (FastAPI/uvicorn, port 8000 → LAN)
        └── bestbox-mcp  (FastMCP SSE, port 8001 → LAN)

Claude Code clients (any machine on LAN)
  └── MCP config: url = http://192.168.1.98:8001/sse
```

All four containers share a Docker bridge network `bestbox-net`. SQL Server and Redis are internal only — not exposed to the host.

---

## New Files

```
Dockerfile                          # Single image for both REST and MCP services
.dockerignore
deploy/
  init-db.sh                        # SQL Server auto-restore entrypoint script
  docker-compose.infra.yml          # SQL Server + Redis (stand up once)
  docker-compose.app.yml            # REST API + MCP server (redeploy on code changes)
  .env.server.example               # Template — never committed with real values
```

No existing source files change structurally. One targeted change to `src/bestbox/mcp/server.py` adds SSE transport support via env var.

---

## Component Design

### Dockerfile

Single image based on `python:3.12-slim`. Installs Microsoft ODBC Driver 18 for SQL Server (required by pyodbc on Linux), then installs the `bestbox` package from `pyproject.toml`.

- Default `CMD`: `uvicorn bestbox.rest.main:app --host 0.0.0.0 --port 8000` (REST API)
- MCP service overrides CMD to `python -m bestbox.mcp.server` with `MCP_TRANSPORT=sse`

One image, two roles — reduces build surface and keeps images in sync.

### deploy/init-db.sh

Custom entrypoint for the `sqlserver` container:

1. Starts `sqlservr` in the background
2. Polls `sqlcmd` in a loop (1s interval, 60s max) until SQL Server accepts connections
3. Queries `sys.databases` for `SmartTrade_2024`
4. If absent: selects the lexicographically latest `.bak` file from `/data/yishang/` (filenames embed timestamps — alphabetical = chronological), runs:
   ```sql
   RESTORE DATABASE [SmartTrade_2024]
   FROM DISK='<latest.bak>'
   WITH MOVE 'FES' TO '/var/opt/mssql/data/SmartTrade_2024.mdf',
        MOVE 'FES_log' TO '/var/opt/mssql/data/SmartTrade_2024_log.ldf',
        REPLACE
   ```
5. If present: skips restore (idempotent — safe on container restart)
6. Foregrounds `sqlservr` so Docker health tracking works

Logical file names `FES` / `FES_log` were confirmed by `RESTORE FILELISTONLY` against the actual backup files.

### docker-compose.infra.yml

| Service | Image | Mounts | Network |
|---|---|---|---|
| `sqlserver` | `mcr.microsoft.com/mssql/server:2022-latest` | `/data/yishang:/data/yishang:ro`, `/data/sqlserver/data:/var/opt/mssql/data` | `bestbox-net` |
| `redis` | `redis:7-alpine` | `/data/redis:/data` | `bestbox-net` |

SQL Server uses a custom entrypoint (`init-db.sh`). Both services use `restart: unless-stopped`.

### docker-compose.app.yml

| Service | Image | Port | Env | Network |
|---|---|---|---|---|
| `bestbox-api` | `192.168.1.98:5000/bestbox:latest` | `8000:8000` | from `.env.server` | `bestbox-net` |
| `bestbox-mcp` | `192.168.1.98:5000/bestbox:latest` | `8001:8001` | from `.env.server` + `MCP_TRANSPORT=sse` | `bestbox-net` |

Both services depend on `sqlserver` and `redis` via `external: true` network reference. Both use `restart: unless-stopped`.

### MCP SSE Transport (mcp/server.py change)

Replace the `if __name__ == "__main__":` block:

```python
if __name__ == "__main__":
    import os
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    if transport == "sse":
        mcp.run(transport="sse", host="0.0.0.0", port=int(os.environ.get("MCP_PORT", "8001")))
    else:
        mcp.run()
```

Local stdio behaviour is unchanged. No changes to any MCP tool definitions.

### .env.server.example

```env
# SQL Server
SA_PASSWORD=ChangeMe_Strong1

# SmartTrade connection (container name resolves inside Docker network)
SMARTTRADE_SERVER=sqlserver
SMARTTRADE_PORT=1433
SMARTTRADE_DATABASE=SmartTrade_2024
SMARTTRADE_USER=sa
SMARTTRADE_PASSWORD=ChangeMe_Strong1
SMARTTRADE_DRIVER=ODBC Driver 18 for SQL Server

# Redis
REDIS_URL=redis://redis:6379

# MCP
MCP_TRANSPORT=sse
MCP_PORT=8001
```

---

## Port Exposure Summary

| Port | Service | Access |
|------|---------|--------|
| 8000 | BestBox REST API | LAN — dashboards, agents |
| 8001 | BestBox MCP SSE | LAN — Claude Code clients |
| 5000 | Private registry | Dev machine push/pull |
| 1433 | SQL Server | **Internal only** |
| 6379 | Redis | **Internal only** |

---

## Claude Code Client Configuration

On any developer machine pointing at the remote server, add to `~/.claude/settings.json`:

```json
"mcpServers": {
  "bestbox": {
    "url": "http://192.168.1.98:8001/sse"
  }
}
```

The local stdio entry (`command`/`args`) can remain alongside this for local dev use.

---

## Build & Deploy Workflow

### First-time setup

```bash
# 1. Build and push image (dev machine)
docker build -t 192.168.1.98:5000/bestbox:latest .
docker push 192.168.1.98:5000/bestbox:latest

# 2. Prepare server directories
ssh apexvue@192.168.1.98 "mkdir -p /data/bestbox /data/sqlserver/data /data/redis"

# 3. Copy deploy files and env template
scp deploy/* apexvue@192.168.1.98:/data/bestbox/
# Edit /data/bestbox/.env.server on the server with real passwords

# 4. Start infrastructure (triggers auto-restore, takes ~30s)
ssh apexvue@192.168.1.98 "cd /data/bestbox && docker compose -f docker-compose.infra.yml up -d"

# 5. Start application
ssh apexvue@192.168.1.98 "cd /data/bestbox && docker compose -f docker-compose.app.yml up -d"
```

### Subsequent deploys (app code changes only)

```bash
docker build -t 192.168.1.98:5000/bestbox:latest .
docker push 192.168.1.98:5000/bestbox:latest
ssh apexvue@192.168.1.98 "cd /data/bestbox && docker compose -f docker-compose.app.yml pull && docker compose -f docker-compose.app.yml up -d"
```

SQL Server and Redis are not touched on app redeployments.

---

## What This Design Does Not Include

- HTTPS / TLS termination — LAN-only deployment, plain HTTP acceptable
- Authentication on MCP or REST endpoints — add nginx + API key if internet exposure needed later
- CI/CD pipeline — deploy workflow is manual shell commands for now
- Multi-instance / load balancing — single server deployment
