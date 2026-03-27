# Docker Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Package BestBox as a Docker image, deploy it alongside SQL Server 2022 and Redis on `apexvue@192.168.1.98`, with the SmartTrade database auto-restored from backup and the MCP server accessible remotely via SSE transport.

**Architecture:** Single BestBox Docker image (python:3.12-slim + ODBC Driver 18) pushed to the server's private registry (192.168.1.98:5000); two Docker Compose files on the server — `infra` (SQL Server + Redis, stand up once) and `app` (REST API + MCP, redeploy on code changes); SQL Server uses a custom entrypoint script that auto-restores the latest `.bak` from `/data/yishang/` on first boot.

**Tech Stack:** Docker, Docker Compose, SQL Server 2022 (Linux container), Redis 7 Alpine, FastAPI/uvicorn, FastMCP SSE transport

---

## File Map

| Action | Path | Responsibility |
|---|---|---|
| Create | `Dockerfile` | BestBox image: python:3.12-slim + ODBC Driver 18 + bestbox package |
| Create | `.dockerignore` | Exclude venv, tests, .env, docs from build context |
| Create | `deploy/init-db.sh` | SQL Server entrypoint: wait for ready, restore .bak if DB absent |
| Create | `deploy/docker-compose.infra.yml` | SQL Server + Redis with volumes and healthchecks |
| Create | `deploy/docker-compose.app.yml` | bestbox-api (port 8000) + bestbox-mcp (port 8001, SSE) |
| Create | `deploy/.env.server.example` | Environment variable template for the remote host |
| Modify | `src/bestbox/mcp/server.py` | Read `MCP_TRANSPORT` env var to switch between stdio and SSE |

---

### Task 1: Dockerfile and .dockerignore

**Files:**
- Create: `Dockerfile`
- Create: `.dockerignore`

- [ ] **Step 1: Create `.dockerignore`**

```
.venv/
__pycache__/
*.pyc
*.pyo
.env
.env.*
tests/
docs/
*.bak
.git/
.mcp.json
deploy/
```

- [ ] **Step 2: Create `Dockerfile`**

```dockerfile
FROM python:3.12-slim

# Install Microsoft ODBC Driver 18 for SQL Server (required by pyodbc on Linux)
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl gnupg2 apt-transport-https ca-certificates && \
    curl -fsSL https://packages.microsoft.com/keys/microsoft.asc \
        | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg && \
    curl -fsSL https://packages.microsoft.com/config/debian/12/prod.list \
        > /etc/apt/sources.list.d/mssql-release.list && \
    apt-get update && \
    ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 unixodbc-dev && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml .
COPY src/ src/

RUN pip install --no-cache-dir .

CMD ["uvicorn", "bestbox.rest.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 3: Verify the image builds cleanly**

```bash
docker build -t bestbox-test .
```

Expected: `Successfully built <id>` — no errors. Build will take 3–5 minutes on first run (ODBC Driver download).

- [ ] **Step 4: Verify the image runs and imports correctly**

```bash
docker run --rm bestbox-test python -c "import bestbox.rest.main; import bestbox.mcp.server; print('OK')"
```

Expected output: `OK`

- [ ] **Step 5: Commit**

```bash
git add Dockerfile .dockerignore
git commit -m "feat: add Dockerfile with ODBC Driver 18 for Linux deployment"
```

---

### Task 2: MCP SSE Transport

**Files:**
- Modify: `src/bestbox/mcp/server.py` (line 137–138)

- [ ] **Step 1: Replace the `__main__` block in `src/bestbox/mcp/server.py`**

Replace:
```python
if __name__ == "__main__":
    mcp.run()
```

With:
```python
if __name__ == "__main__":
    import os
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    if transport == "sse":
        mcp.run(
            transport="sse",
            host="0.0.0.0",
            port=int(os.environ.get("MCP_PORT", "8001")),
        )
    else:
        mcp.run()
```

- [ ] **Step 2: Verify stdio mode still works (no env var)**

```bash
cd E:/MyCode/bestboxdb
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1"}}}' | .venv/Scripts/python.exe -m bestbox.mcp.server
```

Expected: JSON response containing `"result"` with server info. Press Ctrl+C to exit.

- [ ] **Step 3: Verify SSE mode starts an HTTP server**

```bash
cd E:/MyCode/bestboxdb
MCP_TRANSPORT=sse MCP_PORT=8002 .venv/Scripts/python.exe -m bestbox.mcp.server &
sleep 3
curl -s http://localhost:8002/sse | head -c 100
kill %1
```

On Windows Git Bash, use:
```bash
cd E:/MyCode/bestboxdb
set MCP_TRANSPORT=sse && set MCP_PORT=8002 && .venv/Scripts/python.exe -m bestbox.mcp.server
```
Open a second terminal and run: `curl http://localhost:8002/sse`
Expected: SSE stream opens (hanging connection, no immediate error). Stop server with Ctrl+C.

- [ ] **Step 4: Commit**

```bash
git add src/bestbox/mcp/server.py
git commit -m "feat: add SSE transport support to MCP server via MCP_TRANSPORT env var"
```

---

### Task 3: SQL Server Auto-Restore Script

**Files:**
- Create: `deploy/init-db.sh`

- [ ] **Step 1: Create `deploy/` directory and write `init-db.sh`**

```bash
#!/bin/bash
set -e

echo "[init-db] Starting SQL Server..."
/opt/mssql/bin/sqlservr &
MSSQL_PID=$!

echo "[init-db] Waiting for SQL Server to accept connections (max 60s)..."
for i in $(seq 1 60); do
    if /opt/mssql-tools18/bin/sqlcmd \
            -S localhost -U sa -P "$MSSQL_SA_PASSWORD" -C \
            -Q "SELECT 1" > /dev/null 2>&1; then
        echo "[init-db] SQL Server ready after ${i}s."
        break
    fi
    if [ "$i" -eq 60 ]; then
        echo "[init-db] ERROR: SQL Server did not start within 60s. Aborting."
        exit 1
    fi
    sleep 1
done

DB_EXISTS=$(/opt/mssql-tools18/bin/sqlcmd \
    -S localhost -U sa -P "$MSSQL_SA_PASSWORD" -C \
    -h -1 -Q "SET NOCOUNT ON; SELECT COUNT(*) FROM sys.databases WHERE name='SmartTrade_2024'" \
    2>/dev/null | tr -d '[:space:]')

if [ "$DB_EXISTS" = "0" ]; then
    echo "[init-db] Database not found. Locating latest backup..."

    LATEST_BAK=$(ls -1 /data/yishang/*.bak 2>/dev/null | sort | tail -1)

    if [ -z "$LATEST_BAK" ]; then
        echo "[init-db] ERROR: No .bak files found in /data/yishang/. Cannot restore."
        exit 1
    fi

    echo "[init-db] Restoring from: $LATEST_BAK"
    /opt/mssql-tools18/bin/sqlcmd \
        -S localhost -U sa -P "$MSSQL_SA_PASSWORD" -C \
        -Q "RESTORE DATABASE [SmartTrade_2024]
            FROM DISK='$LATEST_BAK'
            WITH MOVE 'FES'     TO '/var/opt/mssql/data/SmartTrade_2024.mdf',
                 MOVE 'FES_log' TO '/var/opt/mssql/data/SmartTrade_2024_log.ldf',
                 REPLACE"

    echo "[init-db] Restore complete."
else
    echo "[init-db] Database SmartTrade_2024 already exists. Skipping restore."
fi

echo "[init-db] Handing control to SQL Server process $MSSQL_PID."
wait $MSSQL_PID
```

- [ ] **Step 2: Make it executable**

```bash
chmod +x deploy/init-db.sh
```

- [ ] **Step 3: Verify shell syntax**

```bash
bash -n deploy/init-db.sh
```

Expected: no output (clean parse, no syntax errors).

- [ ] **Step 4: Commit**

```bash
git add deploy/init-db.sh
git commit -m "feat: add SQL Server auto-restore entrypoint script"
```

---

### Task 4: Infrastructure Compose File

**Files:**
- Create: `deploy/docker-compose.infra.yml`

- [ ] **Step 1: Create `deploy/docker-compose.infra.yml`**

```yaml
networks:
  bestbox-net:
    name: bestbox-net
    driver: bridge

services:
  sqlserver:
    image: mcr.microsoft.com/mssql/server:2022-latest
    container_name: bestbox-sqlserver
    environment:
      ACCEPT_EULA: "Y"
      MSSQL_SA_PASSWORD: "${SA_PASSWORD}"
    volumes:
      - /data/yishang:/data/yishang:ro
      - /data/sqlserver/data:/var/opt/mssql/data
      - ./init-db.sh:/init-db.sh:ro
    entrypoint: ["/bin/bash", "/init-db.sh"]
    networks:
      - bestbox-net
    restart: unless-stopped
    healthcheck:
      test: >
        CMD-SHELL /opt/mssql-tools18/bin/sqlcmd
        -S localhost -U sa -P "$$MSSQL_SA_PASSWORD" -C
        -Q "SELECT 1" || exit 1
      interval: 30s
      timeout: 10s
      retries: 10
      start_period: 90s

  redis:
    image: redis:7-alpine
    container_name: bestbox-redis
    volumes:
      - /data/redis:/data
    networks:
      - bestbox-net
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 3
```

- [ ] **Step 2: Validate the YAML**

```bash
docker compose -f deploy/docker-compose.infra.yml config > /dev/null
```

Expected: no output (valid YAML, no compose errors).

- [ ] **Step 3: Commit**

```bash
git add deploy/docker-compose.infra.yml
git commit -m "feat: add infra compose file (SQL Server + Redis with auto-restore)"
```

---

### Task 5: App Compose File + Env Template

**Files:**
- Create: `deploy/docker-compose.app.yml`
- Create: `deploy/.env.server.example`

- [ ] **Step 1: Create `deploy/docker-compose.app.yml`**

```yaml
networks:
  bestbox-net:
    external: true
    name: bestbox-net

services:
  bestbox-api:
    image: 192.168.1.98:5000/bestbox:latest
    container_name: bestbox-api
    ports:
      - "8000:8000"
    env_file:
      - .env.server
    networks:
      - bestbox-net
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "curl -sf http://localhost:8000/docs || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 15s

  bestbox-mcp:
    image: 192.168.1.98:5000/bestbox:latest
    container_name: bestbox-mcp
    command: ["python", "-m", "bestbox.mcp.server"]
    ports:
      - "8001:8001"
    env_file:
      - .env.server
    environment:
      MCP_TRANSPORT: "sse"
      MCP_PORT: "8001"
    networks:
      - bestbox-net
    restart: unless-stopped
```

- [ ] **Step 2: Create `deploy/.env.server.example`**

```env
# -------------------------------------------------------
# BestBox Server Environment — copy to .env.server
# NEVER commit .env.server (only this example file)
# -------------------------------------------------------

# SQL Server SA password (must match SA_PASSWORD in infra compose)
SA_PASSWORD=ChangeMe_Strong1

# SmartTrade connection — container name resolves inside bestbox-net
SMARTTRADE_SERVER=sqlserver
SMARTTRADE_PORT=1433
SMARTTRADE_DATABASE=SmartTrade_2024
SMARTTRADE_USER=sa
SMARTTRADE_PASSWORD=ChangeMe_Strong1
SMARTTRADE_DRIVER=ODBC Driver 18 for SQL Server

# Redis — container name resolves inside bestbox-net
REDIS_URL=redis://redis:6379

# Cache TTLs (optional — defaults shown)
# CACHE_TTL_SALES_ORDER_SEC=60
# CACHE_TTL_ANALYTICS_SEC=600
# CACHE_TTL_ANALYTICS_ALERT_SEC=300

# MCP (set by docker-compose.app.yml — do not override here)
# MCP_TRANSPORT=sse
# MCP_PORT=8001
```

- [ ] **Step 3: Validate app compose YAML**

```bash
docker compose -f deploy/docker-compose.app.yml config > /dev/null
```

Expected: no output.

- [ ] **Step 4: Commit**

```bash
git add deploy/docker-compose.app.yml deploy/.env.server.example
git commit -m "feat: add app compose file and env template for server deployment"
```

---

### Task 6: Configure Local Docker for Insecure Registry + Build + Push

**Files:**
- No source file changes — Docker Desktop configuration + shell commands

- [ ] **Step 1: Allow Docker Desktop to push to the insecure private registry**

Open Docker Desktop → Settings → Docker Engine. Add `192.168.1.98:5000` to `insecure-registries`:

```json
{
  "insecure-registries": ["192.168.1.98:5000"]
}
```

Click **Apply & Restart**. Wait for Docker Desktop to restart (~15s).

- [ ] **Step 2: Verify Docker can reach the registry**

```bash
curl http://192.168.1.98:5000/v2/_catalog
```

Expected: `{"repositories":[]}` or existing repo list. If connection refused, confirm Docker Desktop restarted and port 5000 is open on the server.

- [ ] **Step 3: Build the production image**

```bash
cd E:/MyCode/bestboxdb
docker build -t 192.168.1.98:5000/bestbox:latest .
```

Expected: `Successfully tagged 192.168.1.98:5000/bestbox:latest`

- [ ] **Step 4: Push to the private registry**

```bash
docker push 192.168.1.98:5000/bestbox:latest
```

Expected: All layers pushed, ending with `latest: digest: sha256:...`

- [ ] **Step 5: Verify image is in the registry**

```bash
curl http://192.168.1.98:5000/v2/bestbox/tags/list
```

Expected: `{"name":"bestbox","tags":["latest"]}`

---

### Task 7: First-Time Deploy — Infrastructure

All commands run on the **remote server** via SSH unless noted.

- [ ] **Step 1: Create server directories**

```bash
ssh apexvue@192.168.1.98 "mkdir -p /data/bestbox /data/sqlserver/data /data/redis"
```

- [ ] **Step 2: Copy deploy files to server**

```bash
scp deploy/docker-compose.infra.yml \
    deploy/docker-compose.app.yml \
    deploy/init-db.sh \
    deploy/.env.server.example \
    apexvue@192.168.1.98:/data/bestbox/
```

- [ ] **Step 3: Create `.env.server` on the server with real credentials**

```bash
ssh apexvue@192.168.1.98
cd /data/bestbox
cp .env.server.example .env.server
nano .env.server   # set SA_PASSWORD and SMARTTRADE_PASSWORD to the same strong value
```

Choose a strong SA password (min 8 chars, upper + lower + digit + symbol). Example: `BestBox@Prod2026`

- [ ] **Step 4: Start infrastructure**

```bash
# On the server
cd /data/bestbox
docker compose -f docker-compose.infra.yml --env-file .env.server up -d
```

Expected: `bestbox-sqlserver` and `bestbox-redis` created and started.

- [ ] **Step 5: Watch the restore progress**

```bash
docker logs -f bestbox-sqlserver
```

Expected log sequence:
```
[init-db] Starting SQL Server...
[init-db] Waiting for SQL Server to accept connections...
[init-db] SQL Server ready after Xs.
[init-db] Database not found. Locating latest backup...
[init-db] Restoring from: /data/yishang/SmartTrade_2024_backup_2026_03_11_180001_8097112.bak
Processed 112464 pages...
[init-db] Restore complete.
[init-db] Handing control to SQL Server process...
```

Restore takes approximately 30–60 seconds on the server. Press Ctrl+C to stop following logs once restore is complete — the container keeps running.

- [ ] **Step 6: Verify SQL Server health**

```bash
docker exec bestbox-sqlserver /opt/mssql-tools18/bin/sqlcmd \
    -S localhost -U sa -P "$(grep SA_PASSWORD /data/bestbox/.env.server | cut -d= -f2)" \
    -C -Q "SELECT COUNT(*) FROM SmartTrade_2024.dbo.SellOrder"
```

Expected: a row count (e.g., `34200`). If 0 or error, check `docker logs bestbox-sqlserver`.

- [ ] **Step 7: Verify Redis**

```bash
docker exec bestbox-redis redis-cli ping
```

Expected: `PONG`

---

### Task 8: First-Time Deploy — Application + End-to-End Verification

- [ ] **Step 1: Configure the server to allow pulling from its own registry**

On the remote server, ensure Docker daemon allows the insecure local registry. Check `/etc/docker/daemon.json`:

```bash
ssh apexvue@192.168.1.98 "cat /etc/docker/daemon.json 2>/dev/null || echo '{}'"
```

If `192.168.1.98:5000` is not in `insecure-registries`, add it:

```bash
ssh apexvue@192.168.1.98 "sudo tee /etc/docker/daemon.json <<'EOF'
{
  \"insecure-registries\": [\"192.168.1.98:5000\"]
}
EOF
sudo systemctl reload docker"
```

- [ ] **Step 2: Start the application stack**

```bash
ssh apexvue@192.168.1.98 "cd /data/bestbox && docker compose -f docker-compose.app.yml --env-file .env.server up -d"
```

Expected: `bestbox-api` and `bestbox-mcp` created and started.

- [ ] **Step 3: Check all four containers are running**

```bash
ssh apexvue@192.168.1.98 "docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'"
```

Expected:
```
NAMES                STATUS          PORTS
bestbox-api          Up X seconds    0.0.0.0:8000->8000/tcp
bestbox-mcp          Up X seconds    0.0.0.0:8001->8001/tcp
bestbox-sqlserver    Up X minutes
bestbox-redis        Up X minutes
```

- [ ] **Step 4: Verify REST API**

From your dev machine:

```bash
curl http://192.168.1.98:8000/docs
```

Expected: FastAPI Swagger HTML (200 response). Then test a live endpoint:

```bash
curl "http://192.168.1.98:8000/api/v1/orders/sales?limit=1"
```

Expected: JSON array with one sales order.

- [ ] **Step 5: Verify MCP SSE endpoint**

```bash
curl -N http://192.168.1.98:8001/sse
```

Expected: SSE stream opens — hanging connection, no error. The server sends `event: endpoint` followed by a session URL. Press Ctrl+C to stop.

- [ ] **Step 6: Configure Claude Code on dev machine to use the remote MCP server**

Edit `C:\Users\admin\.claude\settings.json` — add `bestbox-remote` alongside the existing local entry:

```json
"mcpServers": {
  "bestbox": {
    "command": "E:\\MyCode\\bestboxdb\\.venv\\Scripts\\python.exe",
    "args": ["-m", "bestbox.mcp.server"],
    "cwd": "E:\\MyCode\\bestboxdb"
  },
  "bestbox-remote": {
    "url": "http://192.168.1.98:8001/sse"
  }
}
```

Restart Claude Code. Run `/mcp` to confirm `bestbox-remote` shows as connected.

- [ ] **Step 7: Smoke-test remote MCP tools**

In Claude Code, use the remote server's tools:

```
list_sales_orders(date_from="2026-01-01", date_to="2026-03-31", limit=3)
```

Expected: 3 sales orders returned from the server's database — not the local Docker instance.

---

### Task 9: Document the Redeploy Workflow

- [ ] **Step 1: Test the redeploy command end-to-end**

Make a trivial visible change (e.g., add a version field to the REST response), then run the full redeploy sequence:

```bash
# On dev machine
docker build -t 192.168.1.98:5000/bestbox:latest .
docker push 192.168.1.98:5000/bestbox:latest
ssh apexvue@192.168.1.98 \
  "cd /data/bestbox && docker compose -f docker-compose.app.yml pull && docker compose -f docker-compose.app.yml up -d"
```

Expected: `bestbox-api` and `bestbox-mcp` restart with new image. SQL Server and Redis are untouched. Downtime < 5 seconds.

- [ ] **Step 2: Commit all remaining deploy files and close out**

```bash
git add deploy/
git commit -m "feat: complete Docker deployment setup for 192.168.1.98"
```
