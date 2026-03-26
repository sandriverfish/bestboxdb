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
