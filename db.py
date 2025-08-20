# db.py — libSQL (Turso) em produção e SQLite local no dev
import os
import pandas as pd
import streamlit as st

BACKEND = (st.secrets.get("DB_BACKEND")
           or os.environ.get("DB_BACKEND")
           or "libsql").lower()

if BACKEND == "libsql":
    from libsql_client import create_client

    @st.cache_resource
    def _client():
        url = st.secrets["LIBSQL_URL"]
        token = st.secrets.get("LIBSQL_AUTH_TOKEN", "")
        return create_client(url=url, auth_token=token)

    def execute(sql: str, params: tuple = ()):
        _client().execute(sql, params)

    def fetch_df(query: str, params: tuple = ()):
        res = _client().execute(query, params)
        rows = getattr(res, "rows", []) or []
        if rows and isinstance(rows[0], dict):
            return pd.DataFrame(rows)
        cols = getattr(res, "columns", None)
        return pd.DataFrame(rows, columns=cols)
else:
    import sqlite3
    @st.cache_resource
    def _conn():
        db_path = st.secrets.get("DB_PATH", os.environ.get("DB_PATH", "frota.db"))
        return sqlite3.connect(db_path, check_same_thread=False)
    def execute(sql: str, params: tuple = ()):
        c = _conn(); c.execute(sql, params); c.commit()
    def fetch_df(query: str, params: tuple = ()):
        return pd.read_sql_query(query, _conn(), params=params)

def init_db():
    ddl = """
    CREATE TABLE IF NOT EXISTS vehicles (
      plate TEXT PRIMARY KEY,
      model TEXT, year INTEGER, fuel_type TEXT, tank_l REAL,
      owner TEXT, status TEXT, color TEXT, notes TEXT
    );
    CREATE TABLE IF NOT EXISTS drivers (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT, cnh TEXT, cnh_category TEXT,
      cnh_expiry TEXT, phone TEXT, notes TEXT
    );
    CREATE TABLE IF NOT EXISTS fuels (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      date TEXT NOT NULL,
      plate TEXT, driver_id INTEGER,
      station TEXT, liters REAL, unit_price REAL, total REAL,
      odometer REAL, payment TEXT, notes TEXT
    );
    CREATE TABLE IF NOT EXISTS trips (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      date TEXT NOT NULL,
      plate TEXT, driver_id INTEGER,
      client TEXT, notes TEXT, revenue REAL DEFAULT 0,
      nfe TEXT
    );
    CREATE TABLE IF NOT EXISTS costs (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      date TEXT NOT NULL,
      plate TEXT, ctype TEXT, description TEXT, amount REAL,
      notes TEXT, driver_id INTEGER
    );
    CREATE TABLE IF NOT EXISTS parameters (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      category TEXT NOT NULL, value TEXT NOT NULL
    );
    """
    for stmt in ddl.strip().split(";\n"):
        s = stmt.strip()
        if s:
            execute(s + ";")

init_db()
