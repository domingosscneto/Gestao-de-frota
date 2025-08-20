import streamlit as st
import pandas as pd
import numpy as np
from datetime import date, datetime
from db import init_db, fetch_df, execute, get_params, month_yyyymm
init_db()


# ---------- Utils ----------
def brl(x):
    try:
        return ("R$ " + f"{float(x):,.2f}").replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return x

def date_br(s):
    try:
        if hasattr(s, "strftime"):
            return s.strftime("%d/%m/%Y")
        return datetime.fromisoformat(str(s)).strftime("%d/%m/%Y")
    except Exception:
        return s



def filter_table(df, key_prefix="flt", num_cols=4):
    """Tabela com filtros por coluna (listas suspensas).
    O botão 'Limpar filtros' limpa o estado **antes** de renderizar os widgets,
    evitando erros do Streamlit ao mexer em st.session_state depois da criação.
    """
    if df is None or df.empty:
        return df

    st.markdown("#### Filtros da Tabela")

    # Botão de limpar – executado ANTES de criar os widgets
    clear = st.button("Limpar filtros", key=f"{key_prefix}_clear")
    if clear:
        for c in df.columns:
            st.session_state.pop(f"{key_prefix}_{c}", None)
        try:
            st.rerun()
        except Exception:
            st.experimental_rerun()

    # Render dos filtros
    num_cols = max(1, min(num_cols, len(df.columns)))
    cols = st.columns(num_cols)

    selections = {}
    for i, c in enumerate(df.columns):
        col = cols[i % num_cols]
        options = (
            df[c]
            .astype(str)
            .replace({"nan": ""})
            .dropna()
            .unique()
            .tolist()
        )
        try:
            options = sorted(options)
        except Exception:
            pass

        selections[c] = col.multiselect(
            c,
            options,
            default=st.session_state.get(f"{key_prefix}_{c}", []),
            key=f"{key_prefix}_{c}",
        )

        if (i % num_cols) == (num_cols - 1) and (i < len(df.columns) - 1):
            cols = st.columns(num_cols)

    # Aplica os filtros
    for c, selected in selections.items():
        if selected:
            df = df[df[c].astype(str).isin(selected)]

    return df
    st.markdown("#### Filtros da Tabela")
    num_cols = max(1, min(num_cols, len(df.columns)))
    cols = st.columns(num_cols)

    selections = {}
    for i, c in enumerate(df.columns):
        col = cols[i % num_cols]
        opts = (
            df[c]
            .astype(str)
            .replace({"nan": ""})
            .dropna()
            .unique()
            .tolist()
        )
        try:
            opts = sorted(opts)
        except Exception:
            pass
        selections[c] = col.multiselect(c, opts, default=[], key=f"{key_prefix}_{c}")
        # Nova linha de colunas a cada "num_cols" filtros
        if (i % num_cols) == (num_cols - 1) and (i < len(df.columns) - 1):
            cols = st.columns(num_cols)

    # Botão para limpar todos os filtros (voltar à tabela inteira)
    if st.button("Limpar filtros", key=f"{key_prefix}_clear"):
        for c in df.columns:
            st.session_state[f"{key_prefix}_{c}"] = []

    # Aplicar filtros
    for c, selected in selections.items():
        if selected:
            df = df[df[c].astype(str).isin(selected)]
    return df

    st.markdown("#### Filtros da Tabela (lista suspensa)")
    # Para cada coluna, cria um multiselect com valores únicos
    for c in df.columns:
        opts = (
            df[c]
            .astype(str)
            .replace({"nan": ""})
            .dropna()
            .unique()
            .tolist()
        )
        try:
            opts = sorted(opts)
        except Exception:
            pass
        selected = st.multiselect(f"{c}", opts, default=[], key=f"{key_prefix}_{c}")
        if selected:
            df = df[df[c].astype(str).isin(selected)]
    # Botão para limpar todos os filtros (voltar à tabela inteira)
    if st.button("Limpar filtros", key=f"{key_prefix}_clear"):
        for c in df.columns:
            st.session_state[f"{key_prefix}_{c}"] = []
    return df

    st.markdown("#### Filtros da Tabela")
    cols = st.columns(min(4, len(df.columns)))
    filters = {}
    for i, c in enumerate(df.columns):
        col = cols[i % len(cols)]
        filters[c] = col.text_input(f"Filtrar '{c}'", value="", key=f"{key_prefix}_{c}")
    btns = st.columns([1,1,6])
    apply = btns[0].button("Aplicar filtros", key=f"{key_prefix}_apply")
    clear = btns[1].button("Limpar filtros", key=f"{key_prefix}_clear")
    if clear:
        for c in df.columns:
            st.session_state[f"{key_prefix}_{c}"] = ""
    if apply:
        mask = np.ones(len(df), dtype=bool)
        for c, val in filters.items():
            v = val.strip()
            if v:
                mask &= df[c].astype(str).str.contains(re.escape(v), case=False, na=False)
        df = df[mask]
    return df


st.set_page_config(page_title="Gestão de Frota", layout="wide")

# ---------- Init DB ----------

st.title("🚚 Gestão de Frota")

PAGES = [
    "Dashboard",
    "Veículos",
    "Motoristas",
    "Abastecimentos",
    "Viagens",
    "Custos",
    "Parâmetros",
]

page = st.sidebar.radio("Navegação", PAGES, index=0)

def to_iso(d):
    if isinstance(d, str):
        return d
    return d.strftime("%Y-%m-%d")


def editor_delete_update(df, table, keycol, editable_map, column_config=None, key_prefix="ed", transforms=None):
    """
    df: DataFrame exibido (com nomes de colunas possivelmente diferentes dos do banco)
    table: nome da tabela no banco
    keycol: coluna-chave presente em df (ex.: 'id' ou 'plate')
    editable_map: dict {coluna_df -> coluna_bd} indicando o que pode ser alterado
    transforms: dict opcional {coluna_df -> func(value) -> valor_para_bd}
    """
    if df is None or df.empty:
        st.info("Sem registros.")
        return

    from streamlit import column_config as cc
    import pandas as pd

    df = df.copy()
    if "Excluir" not in df.columns:
        df.insert(0, "Excluir", False)

    cfg = column_config.copy() if isinstance(column_config, dict) else {}
    cfg["Excluir"] = cc.CheckboxColumn("🗑️", help="Marque para excluir", default=False)
    # Desabilitar visualmente a coluna-chave
    try:
        if pd.api.types.is_numeric_dtype(df[keycol]):
            cfg[keycol] = cc.NumberColumn(keycol, disabled=True)
        else:
            cfg[keycol] = cc.TextColumn(keycol, disabled=True)
    except Exception:
        pass

    edited = st.data_editor(
        df,
        hide_index=True,
        use_container_width=True,
        column_config=cfg,
        key=f"{key_prefix}_editor"
    )

    cdel, csave = st.columns([1,1])

    if cdel.button("Excluir linhas marcadas", key=f"{key_prefix}_del"):
        to_del = edited[edited["Excluir"] == True][keycol].tolist()
        for v in to_del:
            execute(f"DELETE FROM {table} WHERE {keycol}=?", (int(v) if keycol=='id' else v,))
        st.success(f"Apagadas {len(to_del)} linha(s).")
        try:
            st.rerun()
        except Exception:
            st.experimental_rerun()

    if csave.button("Salvar alterações", key=f"{key_prefix}_save"):
        # Remove coluna Excluir antes de comparar
        orig = df.drop(columns=["Excluir"])
        cur = edited.drop(columns=["Excluir"])

        updates = 0
        for _, row in cur.iterrows():
            keyval = row[keycol]
            base = orig[orig[keycol] == keyval]
            if base.empty:
                continue
            base_row = base.iloc[0]

            changed_pairs = []
            for col_df, col_db in editable_map.items():
                val_new = row.get(col_df)
                val_old = base_row.get(col_df)
                if str(val_new) != str(val_old):
                    if transforms and col_df in transforms:
                        val_new = transforms[col_df](val_new)
                    changed_pairs.append((col_db, val_new))

            if changed_pairs:
                set_clause = ", ".join([f"{c}=?" for c,_ in changed_pairs])
                params = [v for _,v in changed_pairs] + [int(keyval) if keycol=='id' else keyval]
                execute(f"UPDATE {table} SET {set_clause} WHERE {keycol}=?", tuple(params))
                updates += 1

        st.success(f"Atualizadas {updates} linha(s).")
        try:
            st.rerun()
        except Exception:
            st.experimental_rerun()


def df_download_button(df, label, filename):
    st.download_button(label, df.to_csv(index=False).encode("utf-8-sig"), file_name=filename, mime="text/csv")

# ---------- Dashboard ----------

if page == "Dashboard":
    st.subheader("Painel Geral")

    # --- Filtros do Dashboard ---
    plates_all = ["Todas"] + fetch_df("SELECT plate FROM vehicles ORDER BY plate")["plate"].tolist()
    cflt1, cflt2, cflt3 = st.columns([2,1,1])
    f_placa = cflt1.selectbox("Placa (filtro)", plates_all, index=0)
    dates_union = fetch_df("SELECT date FROM fuels UNION SELECT date FROM costs UNION SELECT date FROM trips")
    if dates_union.empty:
        years = [date.today().year]
    else:
        years = sorted(pd.to_datetime(dates_union["date"], errors="coerce").dropna().dt.year.unique().tolist()) or [date.today().year]
    f_ano = cflt2.selectbox("Ano", years, index=years.index(date.today().year) if date.today().year in years else 0)
    f_mes = cflt3.selectbox("Mês", list(range(1,13)), index=date.today().month-1)
    ym = f"{f_ano}-{f_mes:02d}"
    plate_sql = "" if f_placa == "Todas" else " AND plate = ?"
    params = (ym,) if f_placa == "Todas" else (ym, f_placa)

    # --- Métricas ---
    col1, col2, col3, col4 = st.columns(4)
    total_veic = fetch_df("SELECT COUNT(*) AS n FROM vehicles")["n"].iloc[0]
    total_driv = fetch_df("SELECT COUNT(*) AS n FROM drivers")["n"].iloc[0]
    litros_mes = fetch_df("SELECT IFNULL(SUM(liters),0) AS s FROM fuels WHERE substr(date,1,7)=?" + plate_sql, params)["s"].iloc[0]
    comb_mes = fetch_df("SELECT IFNULL(SUM(total),0) AS s FROM fuels WHERE substr(date,1,7)=?" + plate_sql, params)["s"].iloc[0]
    custos_mes = fetch_df("SELECT IFNULL(SUM(amount),0) AS s FROM costs WHERE substr(date,1,7)=?" + plate_sql, params)["s"].iloc[0]

    col1.metric("Veículos", int(total_veic))
    col2.metric("Motoristas", int(total_driv))
    col3.metric("Litros abastecidos (mês)", round(litros_mes, 2))
    col4.metric("Custo Combustível (mês)", brl(comb_mes))

    col5, col6 = st.columns(2)
    col5.metric("Custos Totais (mês)", brl(custos_mes))

    st.markdown("---")
    st.subheader("Receitas e Despesas do Mês")
    rev = fetch_df("SELECT IFNULL(SUM(revenue),0) AS s FROM trips WHERE substr(date,1,7)=?" + plate_sql, params)["s"].iloc[0]
    despesas = float(custos_mes) + float(comb_mes)
    resultado = float(rev) - despesas
    mc1, mc2, mc3 = st.columns(3)
    mc1.metric("Receitas (R$)", brl(rev))
    mc2.metric("Despesas (R$)", brl(despesas))
    mc3.metric("Resultado (R$)", brl(resultado))
    st.caption("Despesas = Combustível + Custos (ex.: salários, pedágios etc.).")

    st.markdown("---")
    st.subheader("Gráfico do mês")
    df_fuel = fetch_df("SELECT date, total FROM fuels WHERE substr(date,1,7)=?" + plate_sql, params)
    if not df_fuel.empty:
        df_fuel["dia"] = pd.to_datetime(df_fuel["date"]).dt.strftime("%d/%m/%Y")
        grp = df_fuel.groupby("dia")["total"].sum().reset_index().sort_values("dia")
        st.markdown("**Gasto com combustível por dia (R$)**")
        st.bar_chart(grp.set_index("dia"))
    else:
        st.info("Sem dados de combustíveis no período.")
# ---------- Veículos ----------

elif page == "Veículos":
    st.subheader("Cadastro de Veículos")
    status_opts = get_params("Status_Veiculo")
    fuel_opts = get_params("Combustiveis")

    with st.form("frm_veic", clear_on_submit=True):
        c1, c2, c3, c4 = st.columns([1,2,1,1])
        plate = c1.text_input("Placa *").upper().strip()
        model = c2.text_input("Modelo")
        year = c3.number_input("Ano", min_value=1900, max_value=2100, value=2020, step=1)
        fuel = c4.selectbox("Combustível", fuel_opts)

        c5, c6, c7 = st.columns([1,2,2])
        tank = c5.number_input("Tanque (L)", min_value=0.0, step=1.0)
        owner = c6.text_input("Proprietário")
        color = c7.text_input("Cor")
        status = c7.selectbox("Status", status_opts)

        notes = st.text_area("Observações")
        submitted = st.form_submit_button("Salvar Veículo")
        if submitted:
            if not plate:
                st.warning("Informe a Placa.")
            else:
                execute("""
                    INSERT OR REPLACE INTO vehicles (plate, model, year, fuel_type, tank_l, owner, status, color, notes)
                    VALUES (?,?,?,?,?,?,?,?,?)
                """, (plate, model, int(year), fuel, float(tank), owner, status, color, notes))
                st.success("Veículo salvo com sucesso!")

        df = fetch_df("SELECT plate, model, year, fuel_type, tank_l, owner, status, color, notes FROM vehicles ORDER BY plate")
    if not df.empty:
        df = filter_table(df, "flt_veh")
        editor_delete_update(
            df,
            "vehicles",
            "plate",
            editable_map={"model":"model","year":"year","fuel_type":"fuel_type","tank_l":"tank_l","owner":"owner","status":"status","color":"color","notes":"notes"},
            column_config={
                "year": st.column_config.NumberColumn("Ano", step=1),
                "tank_l": st.column_config.NumberColumn("Tanque (L)", step=1.0),
                "fuel_type": st.column_config.SelectboxColumn("Combustível", options=get_params("Combustiveis")),
                "status": st.column_config.SelectboxColumn("Status", options=get_params("Status_Veiculo"))
            },
            key_prefix="veh"
        )
    else:
        st.info("Sem registros.")
    df_download_button(df, "⬇️ Exportar veículos (CSV)", "veiculos.csv")

# ---------- Motoristas ----------
elif page == "Motoristas":
    st.subheader("Cadastro de Motoristas")
    with st.form("frm_drv", clear_on_submit=True):
        c1, c2 = st.columns([2,1])
        name = c1.text_input("Nome *")
        cnh = c2.text_input("CNH")
        c3, c4, c5 = st.columns([1,1,1])
        cat = c3.text_input("Categoria")
        expiry = c4.date_input("Vencimento CNH", value=date.today())
        phone = c5.text_input("Telefone")
        notes = st.text_area("Observações")
        submitted = st.form_submit_button("Salvar Motorista")
        if submitted:
            if not name:
                st.warning("Informe o Nome.")
            else:
                execute("""
                    INSERT INTO drivers (name, cnh, cnh_category, cnh_expiry, phone, notes)
                    VALUES (?,?,?,?,?,?)
                """, (name, cnh, cat, expiry.strftime("%Y-%m-%d"), phone, notes))
                st.success("Motorista salvo!")

        df = fetch_df("SELECT id, name, cnh, cnh_category, cnh_expiry, phone, notes FROM drivers ORDER BY name")
    if not df.empty:
        df["cnh_expiry"] = pd.to_datetime(df["cnh_expiry"], errors="coerce").dt.date
        df = filter_table(df, "flt_drivers")
        editor_delete_update(
            df,
            "drivers",
            "id",
            editable_map={"name":"name","cnh":"cnh","cnh_category":"cnh_category","cnh_expiry":"cnh_expiry","phone":"phone","notes":"notes"},
            column_config={ "cnh_expiry": st.column_config.DateColumn("Vencimento CNH", format="DD/MM/YYYY") },
            key_prefix="drv",
            transforms={"cnh_expiry": lambda v: v.strftime("%Y-%m-%d") if hasattr(v, "strftime") else str(v)}
        )
    else:
        st.info("Sem registros.")
    df_download_button(df, "⬇️ Exportar motoristas (CSV)", "motoristas.csv")

# ---------- Abastecimentos ----------
elif page == "Abastecimentos":
    st.subheader("Registro de Abastecimentos")
    veics = fetch_df("SELECT plate FROM vehicles ORDER BY plate")["plate"].tolist()
    drivers_df = fetch_df("SELECT id, name FROM drivers ORDER BY name")
    drivers = dict(zip(drivers_df["name"], drivers_df["id"]))
    stations = get_params("Postos")
    payments = get_params("Formas_Pagamento")

    with st.form("frm_fuel", clear_on_submit=True):
        c1, c2, c3, c4 = st.columns([1,1,1,1])
        d = c1.date_input("Data", value=date.today())
        plate = c2.selectbox("Placa", veics)
        drv_name = c3.selectbox("Motorista", [""] + list(drivers.keys()))
        station = c4.selectbox("Posto", stations)

        c5, c6, c7 = st.columns([1,1,1])
        liters = c5.number_input("Litros", min_value=0.0, step=0.1)
        unit_price = c6.number_input("Preço Unitário (R$)", min_value=0.0, step=0.01, format="%.2f")
        odom = c7.number_input("Hodômetro", min_value=0.0, step=1.0)

        c8, c9 = st.columns([1,2])
        pay = c8.selectbox("Forma de Pagamento", payments)
        notes = c9.text_input("Observações")

        submitted = st.form_submit_button("Salvar Abastecimento")
        if submitted:
            if not plate:
                st.warning("Cadastre veículos e motoristas primeiro.")
            else:
                total = liters * unit_price
                execute("""
                    INSERT INTO fuels (date, plate, driver_id, station, liters, unit_price, total, odometer, payment, notes)
                    VALUES (?,?,?,?,?,?,?,?,?,?)
                """, (d.strftime("%Y-%m-%d"), plate, drivers.get(drv_name), station, liters, unit_price, total, odom, pay, notes))
                st.success("Abastecimento salvo! Total calculado: R$ {:.2f}".format(total))

        df = fetch_df("""
        SELECT f.id, f.date AS data, f.plate AS placa, d.name AS motorista, f.station AS posto,
               f.liters AS litros, f.unit_price AS preco, f.total, f.odometer AS hodometro,
               f.payment AS pagamento, f.notes AS obs
        FROM fuels f
        LEFT JOIN drivers d ON d.id = f.driver_id
        ORDER BY f.date DESC, f.id DESC
    """)
    if not df.empty:
        df["data"] = pd.to_datetime(df["data"], errors="coerce").dt.date
        df = filter_table(df, "flt_fuels")
        editor_delete_update(
            df,
            "fuels",
            "id",
            editable_map={"data":"date","placa":"plate","posto":"station","litros":"liters","preco":"unit_price","total":"total","hodometro":"odometer","pagamento":"payment","obs":"notes"},
            column_config={
                "data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                "litros": st.column_config.NumberColumn("Litros"),
                "preco": st.column_config.NumberColumn("Preço/L (R$)", format="R$ %.2f"),
                "total": st.column_config.NumberColumn("Total (R$)", format="R$ %.2f"),
                "hodometro": st.column_config.NumberColumn("Hodômetro")
            },
            key_prefix="fuel",
            transforms={"data": lambda v: v.strftime("%Y-%m-%d") if hasattr(v, "strftime") else str(v)}
        )
    else:
        st.info("Sem registros.")
    df_download_button(df, "⬇️ Exportar abastecimentos (CSV)", "abastecimentos.csv")

# ---------- Viagens ----------
elif page == "Viagens":
    st.subheader("Registro de Viagens")
    veics = fetch_df("SELECT plate FROM vehicles ORDER BY plate")["plate"].tolist()
    drivers_df = fetch_df("SELECT id, name FROM drivers ORDER BY name")
    drivers = dict(zip(drivers_df["name"], drivers_df["id"]))

    with st.form("frm_trip", clear_on_submit=True):
        c1, c2, c3 = st.columns([1,1,1])
        d = c1.date_input("Data", value=date.today())
        plate = c2.selectbox("Placa", veics)
        drv_name = c3.selectbox("Motorista", [""] + list(drivers.keys()))

        c4, c5 = st.columns([2,2])
        nfe = c4.text_input("NF-e")
        client = c5.text_input("Cliente")
        freight = st.number_input("Frete (R$)", min_value=0.0, step=0.01, format="%.2f")
        notes = st.text_area("Observações")
        submitted = st.form_submit_button("Salvar Viagem")
        if submitted:
            execute("""
                INSERT INTO trips (date, plate, driver_id, client, notes, revenue, nfe)
                VALUES (?,?,?,?,?,?,?)
            """, (d.strftime("%Y-%m-%d"), plate, drivers.get(drv_name), client, notes, freight, nfe))
            st.success("Viagem salva!")

        df = fetch_df("""
        SELECT t.id, t.date AS data, t.plate AS placa, d.name AS motorista,
               t.nfe, t.client AS cliente, t.revenue AS frete, t.notes AS obs
        FROM trips t
        LEFT JOIN drivers d ON d.id = t.driver_id
        ORDER BY t.date DESC, t.id DESC
    """)
    if not df.empty:
        df["data"] = pd.to_datetime(df["data"], errors="coerce").dt.date
        df = filter_table(df, "flt_trips")
        editor_delete_update(
            df,
            "trips",
            "id",
            editable_map={"data":"date","placa":"plate","nfe":"nfe","cliente":"client","frete":"revenue","obs":"notes"},
            column_config={
                "data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                "frete": st.column_config.NumberColumn("Frete (R$)", format="R$ %.2f")
            },
            key_prefix="trip",
            transforms={"data": lambda v: v.strftime("%Y-%m-%d") if hasattr(v, "strftime") else str(v)}
        )
    else:
        st.info("Sem registros.")
    df_download_button(df, "⬇️ Exportar viagens (CSV)", "viagens.csv")


# ---------- Custos ----------
elif page == "Custos":
    st.subheader("Outros Custos")
    veics = fetch_df("SELECT plate FROM vehicles ORDER BY plate")["plate"].tolist()
    ctypes = get_params("Tipos_Custo")
    drivers_df = fetch_df("SELECT id, name FROM drivers ORDER BY name")
    drivers = dict(zip(drivers_df["name"], drivers_df["id"]))

    with st.form("frm_cost", clear_on_submit=True):
        c1, c2, c3, c4 = st.columns([1,1,2,1])
        d = c1.date_input("Data", value=date.today())
        plate = c2.selectbox("Placa", veics)
        ctype = c3.selectbox("Tipo de Custo", ctypes)
        amount = c4.number_input("Valor (R$)", min_value=0.0, step=0.01, format="%.2f")

        drv_name = st.selectbox("Motorista", [""] + list(drivers.keys()))
        desc = st.text_input("Descrição/Obs")
        submitted = st.form_submit_button("Salvar Custo")
        if submitted:
            execute("""
                INSERT INTO costs (date, plate, ctype, description, amount, notes, driver_id)
                VALUES (?,?,?,?,?,?,?)
            """, (d.strftime("%Y-%m-%d"), plate, ctype, desc, amount, "", drivers.get(drv_name)))
            st.success("Custo salvo!")

        df = fetch_df("""
        SELECT c.id, c.date AS data, c.plate AS placa, c.ctype AS tipo,
               c.description AS descricao, c.amount AS valor, d.name AS motorista
        FROM costs c
        LEFT JOIN drivers d ON d.id = c.driver_id
        ORDER BY c.date DESC, c.id DESC
    """)
    if not df.empty:
        df["data"] = pd.to_datetime(df["data"], errors="coerce").dt.date
        df = filter_table(df, "flt_costs")
        editor_delete_update(
            df,
            "costs",
            "id",
            editable_map={"data":"date","placa":"plate","tipo":"ctype","descricao":"description","valor":"amount"},
            column_config={
                "data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                "valor": st.column_config.NumberColumn("Valor (R$)", format="R$ %.2f")
            },
            key_prefix="cost",
            transforms={"data": lambda v: v.strftime("%Y-%m-%d") if hasattr(v, "strftime") else str(v)}
        )
    else:
        st.info("Sem registros.")
    df_download_button(df, "⬇️ Exportar custos (CSV)", "custos.csv")

# ---------- Parâmetros ----------
elif page == "Parâmetros":
    st.subheader("Parâmetros do Sistema")
    categories = [
        "Tipos_Manutencao",
        "Tipos_Custo",
        "Combustiveis",
        "Status_Veiculo",
        "Postos",
        "Fornecedores",
        "Formas_Pagamento"
    ]
    cat = st.selectbox("Categoria", categories)

    with st.form("frm_param", clear_on_submit=True):
        val = st.text_input("Novo valor")
        add = st.form_submit_button("Adicionar")
        if add and val.strip():
            execute("INSERT INTO parameters (category, value) VALUES (?,?)", (cat, val.strip()))
            st.success("Adicionado!")

        df = fetch_df("SELECT id, value FROM parameters WHERE category=? ORDER BY value", (cat,))
    if not df.empty:
        df = filter_table(df, "flt_params")
        editor_delete_update(
            df,
            "parameters",
            "id",
            editable_map={"value":"value"},
            column_config={},
            key_prefix="param"
        )
    else:
        st.info("Sem registros.")

    
    # Backup
    st.markdown("---")
    st.info("Backup do banco (fleet.db) pode ser feito copiando o arquivo do diretório do projeto.")
