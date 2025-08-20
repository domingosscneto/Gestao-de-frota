# db.py
import os
import sqlite3
from datetime import datetime
import pandas as pd
import streamlit as st

# --- Dropbox SDK (opcionalmente com refresh token) ---
DROPBOX_ENABLED = "dropbox" in st.secrets
if DROPBOX_ENABLED:
    import dropbox
    if "refresh_token" in st.secrets["dropbox"]:
        DBX = dropbox.Dropbox(
            oauth2_refresh_token=st.secrets["dropbox"]["refresh_token"],
            app_key=st.secrets["dropbox"]["app_key"],
            app_secret=st.secrets["dropbox"]["app_secret"],
        )
    else:
        DBX = dropbox.Dropbox(st.secrets["dropbox"]["access_token"])
    DROPBOX_PATH = st.secrets["dropbox"].get("path", "/fleet.db")

DB_PATH = "fleet.db"

# ---------- helpers Dropbox ----------
def _download_from_dropbox_if_exists():
    if not DROPBOX_ENABLED:
        return False
    try:
        md, res = DBX.files_download(DROPBOX_PATH)
        with open(DB_PATH, "wb") as f:
            f.write(res.content)
        return True
    except Exception as e:
        # 404 ou outro erro => ignora (primeira execução pode não ter arquivo remoto)
        return False

def _upload_to_dropbox():
    if not DROPBOX_ENABLED or not os.path.exists(DB_PATH):
        return
    with open(DB_PATH, "rb") as f:
        data = f.read()
    mode = dropbox.files.WriteMode("overwrite")
    try:
        DBX.files_upload(data, DROPBOX_PATH, mode=mode, mute=True)
    except Exception as e:
        # Mostra um aviso leve no app, mas não quebra a experiência
        st.warning("Falha ao enviar banco ao Dropbox. Tente novamente.")

def ensure_local_db_is_restored():
    """Se não houver DB local, tenta restaurar do Dropbox."""
    if os.path.exists(DB_PATH):
        return
    _download_from_dropbox_if_exists()

# ---------- SQLite ----------
def get_conn():
    # SQLite local (rápido); persistência via Dropbox
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    # 1) restaurar do Dropbox (se existir) antes de criar tabelas
    ensure_local_db_is_restored()

    conn = get_conn()
    cur = conn.cursor()

    # Parâmetros
    cur.execute("""
    CREATE TABLE IF NOT EXISTS parameters (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT NOT NULL,
        value TEXT NOT NULL
    );
    """)

    # Veículos
    cur.execute("""
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
    """)

    # Motoristas
    cur.execute("""
    CREATE TABLE IF NOT EXISTS drivers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        license TEXT,
        salary REAL,
        status TEXT,
        notes TEXT
    );
    """)

    # Abastecimentos
    cur.execute("""
    CREATE TABLE IF NOT EXISTS fuelings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        plate TEXT,
        liters REAL,
        price_per_l REAL,
        total REAL,
        station TEXT,
        notes TEXT,
        FOREIGN KEY(plate) REFERENCES vehicles(plate)
    );
    """)

    # Viagens
    cur.execute("""
    CREATE TABLE IF NOT EXISTS trips (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        plate TEXT,
        driver_id INTEGER,
        freight_value REAL,
        origin TEXT,
        destination TEXT,
        km_start REAL,
        km_end REAL,
        km_driven REAL,
        cargo TEXT,
        client TEXT,
        notes TEXT,
        FOREIGN KEY(plate) REFERENCES vehicles(plate),
        FOREIGN KEY(driver_id) REFERENCES drivers(id)
    );
    """)

    # Manutenções
    cur.execute("""
    CREATE TABLE IF NOT EXISTS maints (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        plate TEXT,
        type TEXT,
        cost REAL,
        notes TEXT,
        FOREIGN KEY(plate) REFERENCES vehicles(plate)
    );
    """)

    # Custos
    cur.execute("""
    CREATE TABLE IF NOT EXISTS costs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        category TEXT,
        plate TEXT,
        driver_id INTEGER,
        amount REAL,
        notes TEXT,
        FOREIGN KEY(plate) REFERENCES vehicles(plate),
        FOREIGN KEY(driver_id) REFERENCES drivers(id)
    );
    """)

    conn.commit()
    conn.close()

    # 2) garante que há cópia inicial no Dropbox
    if DROPBOX_ENABLED:
        _upload_to_dropbox()

def fetch_df(query, params=()):
    conn = get_conn()
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df

def execute(query, params=()):
    """INSERT/UPDATE/DELETE unitários; sincroniza após commit."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(query, params)
    conn.commit()
    conn.close()
    if DROPBOX_ENABLED:
        _upload_to_dropbox()

def insert_many(table, rows):
    """Inserção em lote; sincroniza ao final."""
    if not rows:
        return
    conn = get_conn()
    cur = conn.cursor()
    cols = list(rows[0].keys())
    placeholders = ",".join(["?"] * len(cols))
    sql = f"INSERT INTO {table} ({','.join(cols)}) VALUES ({placeholders})"
    cur.executemany(sql, [tuple(r[c] for c in cols) for r in rows])
    conn.commit()
    conn.close()
    if DROPBOX_ENABLED:
        _upload_to_dropbox()

def get_params(category):
    df = fetch_df("SELECT value FROM parameters WHERE category=? ORDER BY value ASC", (category,))
    return df["value"].tolist()

def month_yyyymm(date_str):
    try:
        dt = datetime.fromisoformat(date_str)
    except ValueError:
        from datetime import datetime as _dt
        dt = _dt.strptime(date_str, "%d/%m/%Y")
    return dt.strftime("%Y-%m")
