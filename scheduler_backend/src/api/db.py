import os
import sqlite3

from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

DB_PATH = os.getenv("DB_PATH") or os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "app.db")

def get_db_connection() -> sqlite3.Connection:
    """
    PUBLIC_INTERFACE
    Returns a new SQLite database connection.
    Database path is loaded from the DB_PATH env variable or defaults to scheduler_backend/app.db.
    """
    conn = sqlite3.connect(DB_PATH)
    # Optional: Enable foreign keys
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def check_db_connection() -> bool:
    """
    PUBLIC_INTERFACE
    Checks connectivity to the SQLite DB by opening and closing a connection, returns True if successful.
    """
    try:
        conn = get_db_connection()
        conn.execute("SELECT 1")
        conn.close()
        return True
    except Exception:
        return False
