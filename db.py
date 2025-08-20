import sqlite3
import pandas as pd
from datetime import datetime

DB_PATH = "fleet.db"

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    # Parâmetros dinâmicos
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
        name TEXT NOT NULL,
        cnh TEXT,
        cnh_category TEXT,
        cnh_expiry TEXT,
        phone TEXT,
        notes TEXT
    );
    """)
    # Abastecimentos
    cur.execute("""
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
        notes TEXT,
        FOREIGN KEY(plate) REFERENCES vehicles(plate),
        FOREIGN KEY(driver_id) REFERENCES drivers(id)
    );
    """)
    # Viagens
    cur.execute("""
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
        notes TEXT,
        FOREIGN KEY(plate) REFERENCES vehicles(plate),
        FOREIGN KEY(driver_id) REFERENCES drivers(id)
    );
    """)
    # Manutenções
    cur.execute("""
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
        notes TEXT,
        FOREIGN KEY(plate) REFERENCES vehicles(plate)
    );
    """)
    # Outros custos
    cur.execute("""
    CREATE TABLE IF NOT EXISTS costs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        plate TEXT,
        ctype TEXT,
        description TEXT,
        amount REAL,
        notes TEXT,
        FOREIGN KEY(plate) REFERENCES vehicles(plate)
    );
    """)
    conn.commit()

    # Garantir coluna color em vehicles
    try:
        cur.execute("ALTER TABLE vehicles ADD COLUMN color TEXT")
    except Exception:
        pass


    # Garantir coluna revenue em trips
    try:
        cur.execute("ALTER TABLE trips ADD COLUMN revenue REAL DEFAULT 0")
    except Exception:
        pass


    # Garantir coluna nfe em trips
    try:
        cur.execute("ALTER TABLE trips ADD COLUMN nfe TEXT")
    except Exception:
        pass


    # Garantir coluna driver_id em costs
    try:
        cur.execute("ALTER TABLE costs ADD COLUMN driver_id INTEGER")
    except Exception:
        pass

    # Seed básico de parâmetros se estiver vazio
    cur.execute("SELECT COUNT(*) FROM parameters")
    if cur.fetchone()[0] == 0:
        defaults = {
            "Tipos_Manutencao": ["Revisão", "Troca de Óleo", "Pneus", "Freios", "Suspensão", "Elétrica", "Motor", "Outros"],
            "Tipos_Custo": ["Combustível", "Manutenção", "Pedágio", "Seguro", "IPVA", "Licenciamento", "Multa", "Outros"],
            "Combustiveis": ["Gasolina", "Etanol", "Diesel", "GNV", "Flex"],
            "Status_Veiculo": ["Ativo", "Inativo", "Em manutenção", "Reservado"],
            "Postos": ["Posto A", "Posto B", "Posto C"],
            "Fornecedores": ["Oficina X", "Oficina Y", "Autopeças Z", "Concessionária"],
            "Formas_Pagamento": ["Dinheiro", "Cartão", "PIX", "Boleto", "Frota"]
        }
        for cat, items in defaults.items():
            cur.executemany(
                "INSERT INTO parameters (category, value) VALUES (?,?)",
                [(cat, v) for v in items]
            )
        conn.commit()
    conn.close()

def fetch_df(query, params=()):
    conn = get_conn()
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df

def execute(query, params=()):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(query, params)
    conn.commit()
    last_id = cur.lastrowid
    conn.close()
    return last_id

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
