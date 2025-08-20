# db.py — backend duplo: Turso/libSQL (produção) ou SQLite local (dev)
import os
import pandas as pd
from datetime import datetime

# Cache compatível dentro/fora do Streamlit
try:
    import streamlit as st
    _CACHE = st.cache_resource
    _SECRETS = getattr(st, "secrets", {})
except Exception:  # execução fora do Streamlit
    st = None
    _SECRETS = {}
    from functools import lru_cache as _lru_cache
    def _CACHE(fn):
        cached = _lru_cache(maxsize=1)(lambda: fn())
        def _wrapper():
            return cached()
        return _wrapper

# Escolha do backend por secret/variável de ambiente
BACKEND = (_SECRETS.get("DB_BACKEND") or os.environ.get("DB_BACKEND") or "sqlite").lower()

# -------------------------- Utilidades comuns --------------------------

def _normalize_url(u):
    """Converte libsql://, wss://, ws:// para https:// (modo HTTP síncrono)."""
    if not u:
        return u
    u = u.strip()
    if u.startswith("libsql://"):
        return "https://" + u[len("libsql://"):]
    if u.startswith("wss://"):
        return "https://" + u[len("wss://"):]
    if u.startswith("ws://"):
        return "https://" + u[len("ws://"):]
    return u

# -------------------------- Backend: Turso / libSQL --------------------------

if BACKEND == "libsql":
    from libsql_client import create_client

    @_CACHE
    def _client():
        raw_url = _SECRETS.get("LIBSQL_URL") or os.environ.get("LIBSQL_URL", "")
        url = _normalize_url(raw_url)  # força HTTP
        token = _SECRETS.get("LIBSQL_AUTH_TOKEN", os.environ.get("LIBSQL_AUTH_TOKEN", ""))
        if not url:
            raise RuntimeError("LIBSQL_URL não definido em secrets/variáveis.")
        return create_client(url=url, auth_token=token)

    def fetch_df(query, params=()):
        res = _client().execute(query, params)
        rows = getattr(res, "rows", []) or []
        # pode vir lista de dicts ou de tuplas
        if rows and isinstance(rows[0], dict):
            return pd.DataFrame(rows)
        cols = getattr(res, "columns", None)
        return pd.DataFrame(rows, columns=cols)

    def execute(query, params=()):
        _client().execute(query, params)
        last_id = None
        q0 = query.strip().lower()
        if q0.startswith("insert"):
            try:
                r = _client().execute("SELECT last_insert_rowid() AS id")
                if r.rows:
                    last_id = r.rows[0]["id"] if isinstance(r.rows[0], dict) else r.rows[0][0]
            except Exception:
                pass
        return last_id

# -------------------------- Backend: SQLite local --------------------------

else:
    import sqlite3

    @_CACHE
    def _conn():
        path = _SECRETS.get("DB_PATH", os.environ.get("DB_PATH", "frota.db"))
        return sqlite3.connect(path, check_same_thread=False)

    def fetch_df(query, params=()):
        return pd.read_sql_query(query, _conn(), params=params)

    def execute(query, params=()):
        cur = _conn().cursor()
        cur.execute(query, params)
        _conn().commit()
        return cur.lastrowid

# -------------------------- Schema e helpers --------------------------

def init_db():
    ddl = """
    CREATE TABLE IF NOT EXISTS parameters (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      category TEXT NOT NULL,
      value TEXT NOT NULL
    );
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
    """
    # executa cada statement separadamente (evita problemas de parser)
    parts = [s.strip() for s in ddl.strip().split(";") if s.strip()]
    for stmt in parts:
        execute(stmt + ";")

    # migrações idempotentes
    for alt in [
        "ALTER TABLE vehicles ADD COLUMN color TEXT",
        "ALTER TABLE trips ADD COLUMN nfe TEXT",
        "ALTER TABLE trips ADD COLUMN revenue REAL DEFAULT 0",
        "ALTER TABLE costs ADD COLUMN driver_id INTEGER"
    ]:
        try:
            execute(alt + ";")
        except Exception:
            pass

    # seed básico de parâmetros
    try:
        cnt = fetch_df("SELECT COUNT(*) AS n FROM parameters")
        if not cnt.empty and int(cnt.iloc[0, 0]) == 0:
            defaults = {
                "Tipos_Manutencao": ["Revisao", "Troca de Oleos", "Pneus", "Freios", "Suspensao", "Eletrica", "Motor", "Outros"],
                "Tipos_Custo": ["Combustivel", "Manutencao", "Pedagio", "Seguro", "IPVA", "Licenciamento", "Multa", "Outros"],
                "Combustiveis": ["Gasolina", "Etanol", "Diesel", "GNV", "Flex"],
                "Status_Veiculo": ["Ativo", "Inativo", "Em manutencao", "Reservado"],
                "Postos": ["Posto A", "Posto B", "Posto C"],
                "Fornecedores": ["Oficina X", "Oficina Y", "Autopecas Z", "Concessionaria"],
                "Formas_Pagamento": ["Dinheiro", "Cartao", "PIX", "Boleto", "Frota"]
            }
            for cat, vals in defaults.items():
                for v in vals:
                    execute("INSERT INTO parameters (category, value) VALUES (?, ?);", (cat, v))
    except Exception:
        pass

def get_params(category):
    df = fetch_df("SELECT value FROM parameters WHERE category=? ORDER BY value ASC;", (category,))
    return df["value"].tolist() if not df.empty else []

def month_yyyymm(date_str):
    # aceita ISO (YYYY-MM-DD) ou dd/mm/aaaa
    try:
        dt = datetime.fromisoformat(date_str)
    except Exception:
        dt = datetime.strptime(date_str, "%d/%m/%Y")
    return dt.strftime("%Y-%m")
