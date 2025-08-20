# db.py — compatível com SQLite local e Turso (libSQL)
import os
import pandas as pd
from datetime import datetime

# Tentamos importar Streamlit para usar secrets e cache;
# se não houver Streamlit (execução fora do app), seguimos sem ele.
try:
    import streamlit as st
    _cache = st.cache_resource
    _secrets = getattr(st, "secrets", {})
except Exception:
    st = None
    _secrets = {}
    from functools import lru_cache as _cache  # cache simples fora do Streamlit

# --------- Seleção de backend ---------
# Padrão: SQLite local (compatível com seu fluxo atual).
BACKEND = (_secrets.get("DB_BACKEND")
           or os.environ.get("DB_BACKEND")
           or "sqlite").lower()

# --------- Backend: Turso/libSQL ---------
def _normalize_url(u: str) -> str:
    """Converte libsql:// / wss:// / ws:// para https:// (evita event loop)."""
    u = (u or "").strip()
    if u.startswith("libsql://"):
        return "https://" + u[len("libsql://"):]
    if u.startswith("wss://"):
        return "https://" + u[len("wss://"):]
    if u.startswith("ws://"):
        return "https://" + u[len("ws://"):]
    return u

if BACKEND == "libsql":
    from libsql_client import create_client

    @_cache
    def _client():
        raw_url = _secrets.get("LIBSQL_URL") or os.environ["LIBSQL_URL"]
        url = _normalize_url(raw_url)  # força HTTP
        token = _secrets.get("LIBSQL_AUTH_TOKEN", os.environ.get("LIBSQL_AUTH_TOKEN", ""))
        return create_client(url=url, auth_token=token)

    def fetch_df(query, params=()):
        res = _client().execute(query, params)
        rows = getattr(res, "rows", []) or []
        # Pode vir lista de dicts ou de tuplas:
        if rows and isinstance(rows[0], dict):
            return pd.DataFrame(rows)
        cols = getattr(res, "columns", None)
        return pd.DataFrame(rows, columns=cols)

    def execute(query, params=()):
        _client().execute(query, params)
        last_id = None
        # Para INSERT com chave auto, tentamos buscar o last_insert_rowid da sessão
        q0 = query.strip().lower()
        if q0.startswith("insert"):
            try:
                r = _client().execute("SELECT last_insert_rowid() AS id")
                if r.rows:
                    last_id = r.rows[0]["id"] if isinstance(r.rows[0], dict) else r.rows[0][0]
            except Exception:
                pass
        return last_id

# --------- Backend: SQLite local (secrets/ENV não pedirem libsql) ---------
else:
    import sqlite3
    DB_PATH = "fleet.db"  # mantém o mesmo nome do seu arquivo original

    @_cache
    def get_conn():
        # Permite sobrescrever via secret/ENV se quiser
        path = _secrets.get("DB_PATH", os.environ.get("DB_PATH", DB_PATH))
        return sqlite3.connect(path, check_same_thread=False)

    def fetch_df(query, params=()):
        conn = get_conn()
        df = pd.read_sql_query(query, conn, params=params)
        return df

    def execute(query, params=()):
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(query, params)
        conn.commit()
        return cur.lastrowid

# --------- Funções comuns (independentes do backend) ---------
def init_db():
    # Cria tabelas se não existirem (todas compatíveis com SQLite/libSQL)
    ddl = """
    CREATE TABLE IF NOT EXISTS parameters (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT NOT NULL,
        value TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS vehicles (
        plate TEXT PRIMARY KEY,
        model TEXT,
        year INTEGER,
        fuel_type TEXT,
        tank_l REAL,
        owner TEXT,
        status TEXT,
        notes TEXT
    );
    CREATE TABLE IF NOT EXISTS drivers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        cnh TEXT,
        cnh_category TEXT,
        cnh_expiry TEXT,
        phone TEXT,
        notes TEXT
    );
    CREATE TABLE IF NOT EXISTS fuels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        plate TEXT,
        driver_id INTEGER,
        station TEXT,
        liters REAL,
        unit_price REAL,
        total REAL,
        odometer REAL,
        payment TEXT,
        notes TEXT
    );
    CREATE TABLE IF NOT EXISTS trips (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        plate TEXT,
        driver_id INTEGER,
        origin TEXT,
        destination TEXT,
        km_start REAL,
        km_end REAL,
        km_driven REAL,
        cargo TEXT,
        client TEXT,
        notes TEXT
    );
    CREATE TABLE IF NOT EXISTS maintenance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        plate TEXT,
        mtype TEXT,
        description TEXT,
        supplier TEXT,
        odometer REAL,
        cost REAL,
        next_km REAL,
        next_date TEXT,
        notes TEXT
    );
    CREATE TABLE IF NOT EXISTS costs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        plate TEXT,
        ctype TEXT,
        description TEXT,
        amount REAL,
        notes TEXT
    );
    """
    # Executa cada bloco do DDL
    for stmt in ddl.strip().split(";\n"):
        s = stmt.strip()
        if s:
            execute(s + ";")

    # Migrações leves (alter table se não existir)
    for alt in [
        "ALTER TABLE vehicles ADD COLUMN color TEXT",
        "ALTER TABLE trips ADD COLUMN revenue REAL DEFAULT 0",
        "ALTER TABLE trips ADD COLUMN nfe TEXT",
        "ALTER TABLE costs ADD COLUMN driver_id INTEGER",
    ]:
        try:
            execute(alt)
        except Exception:
            pass

    # Seed de parâmetros (somente se vazio)
    try:
        df_cnt = fetch_df("SELECT COUNT(*) AS n FROM parameters")
        if int(df_cnt.iloc[0, 0]) == 0:
            defaults = {
                "Tipos_Manutencao": ["Revisão", "Troca de Óleo", "Pneus", "Freios", "Suspensão", "Elétrica", "Motor", "Outros"],
                "Tipos_Custo": ["Combustível", "Manutenção", "Pedágio", "Seguro", "IPVA", "Licenciamento", "Multa", "Outros"],
                "Combustiveis": ["Gasolina", "Etanol", "Diesel", "GNV", "Flex"],
                "Status_Veiculo": ["Ativo", "Inativo", "Em manutenção", "Reservado"],
                "Postos": ["Posto A", "Posto B", "Posto C"],
                "Fornecedores": ["Oficina X", "Oficina Y", "Autopeças Z", "Concessionária"],
                "Formas_Pagamento": ["Dinheiro", "Cartão", "PIX", "Boleto", "Frota"],
            }
            for cat, items in defaults.items():
                for v in items:
                    execute("INSERT INTO parameters (category, value) VALUES (?, ?)", (cat, v))
    except Exception:
        pass

def get_params(category):
    df = fetch_df("SELECT value FROM parameters WHERE category=? ORDER BY value ASC", (category,))
    return df["value"].tolist()

def month_yyyymm(date_str):
    # date_str em ISO ou dd/mm/yyyy
    try:
        dt = datetime.fromisoformat(date_str)
    except ValueError:
        dt = datetime.strptime(date_str, "%d/%m/%Y")
    return dt.strftime("%Y-%m")
