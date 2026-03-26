from contextlib import contextmanager
import pyodbc
from bestbox.adapters.smarttrade.config import SmartTradeConfig


@contextmanager
def get_connection():
    conn = pyodbc.connect(SmartTradeConfig.connection_string(), timeout=15)
    try:
        yield conn
    finally:
        conn.close()
