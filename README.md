# Gestão de Frota – Streamlit + SQLite (persistência via Dropbox)

Sistema completo para **gestão de frota** com cadastros de **veículos, motoristas, viagens (com frete/receita), abastecimentos, manutenções e custos**, além de **dashboard** com filtros por período/placa.

O app roda:
- **Online** no **Streamlit Community Cloud** (publicação gratuita).
- **Offline** no seu **Windows** via **Anaconda** (ambiente local).
  
Para **não perder dados** no Streamlit Cloud (onde o disco é temporário), o projeto sincroniza automaticamente o arquivo **SQLite** (`fleet.db`) com o **Dropbox**:
- **No início do app**: baixa a versão mais recente do `fleet.db` do Dropbox.
- **Após cada gravação**: envia a versão atualizada para o Dropbox.
- Assim, em qualquer reinício, o app recomeça do **último estado salvo**.

---

## ✨ Recursos principais

- Cadastros: **Veículos, Motoristas, Abastecimentos, Viagens (com frete), Manutenções, Custos**.
- **Parâmetros do Sistema** (listas auxiliares como status de veículo, formas de pagamento etc.).
- **Dashboard** com gráficos e totais do mês (receitas x despesas) e filtros.
- Persistência de dados em **SQLite** com **backup/sincronização no Dropbox**.
- **Execução local (Windows/Anaconda)** e **deploy no Streamlit Cloud**.

---

## 🧱 Arquitetura (como funciona)

- **Front-end / UI**: [Streamlit](https://streamlit.io/) (`app.py`).
- **Banco local**: `SQLite` em arquivo (`fleet.db`).
- **Persistência em nuvem**: **Dropbox** (upload/download do `fleet.db`).
- **Camada de acesso a dados**: `db.py` (funções `init_db`, `fetch_df`, `execute`, etc.).

**Fluxo de persistência**:
1. O app inicia → `init_db()` tenta **restaurar** o `fleet.db` do Dropbox.
2. Ao gravar (INSERT/UPDATE/DELETE) → envia o `fleet.db` atualizado para o Dropbox.
3. No próximo restart do app → baixa do Dropbox a versão mais nova → dados preservados.

> Para ambientes com **muitos usuários simultâneos**, considere migrar para um banco gerenciado (ex.: Turso/Postgres). Para uso individual/pequena equipe, Dropbox + SQLite atende bem.

---

## 🗂 Estrutura do projeto

```
.
├─ app.py                 # Arquivo principal do Streamlit (UI + navegação)
├─ db.py                  # Camada de banco + sincronização com Dropbox
├─ requirements.txt       # Dependências Python
├─ pages/                 # (opcional) páginas extras do app
├─ .streamlit/
│   └─ secrets.toml       # Segredos locais (NÃO commitar)
├─ seed_fleet.db          # (opcional) base de demonstração para 1º uso local
└─ README.md
```

**Importante – não versionar o banco vivo**. Garanta no `.gitignore`:
```
fleet.db
fleet.db-wal
fleet.db-shm
*.db
*.db-wal
*.db-shm
```

Se você tiver um `fleet.db` já versionado, remova do controle de versão:
```bash
git rm --cached -f fleet.db fleet.db-wal fleet.db-shm
git add .gitignore
git commit -m "Stop tracking local SQLite DB"
git push
```

---

## 🧰 Pré-requisitos (Windows)

- **Python 3.10+** (recomendado 3.11).  
- **Anaconda** (ou Miniconda) – para criar e isolar o ambiente.  
- **Git** – para clonar o repositório.  
- (Opcional) **SQLite CLI** – para inspecionar o banco no terminal.  
- (Opcional) **VS Code** – como editor.

### Instalação rápida de ambiente (Anaconda Prompt)
```bash
conda create -n frota python=3.11 -y
conda activate frota

# dentro da pasta do projeto
pip install -r requirements.txt
```

---

## ▶️ Rodando o app **offline** (somente no seu PC)

1. **Clone** o repositório e entre na pasta do projeto.
2. (Opcional) Se quiser um banco inicial de demonstração:
   ```bash
   copy seed_fleet.db fleet.db   # ou copie via Explorer
   ```
3. **Ative o ambiente** do Anaconda e **instale** dependências:
   ```bash
   conda activate frota
   pip install -r requirements.txt
   ```
4. **(Opcional) Secrets locais** – para sincronizar com Dropbox mesmo no seu PC, crie o arquivo `.streamlit/secrets.toml`:
   ```toml
   [dropbox]
   access_token = "SEU_ACCESS_TOKEN"      # ou use app_key/app_secret/refresh_token
   path = "/fleet.db"
   ```
   > Se não quiser Dropbox local, **não crie** esse arquivo. O app funcionará só com o `fleet.db` local.
5. **Execute o app**:
   ```bash
   streamlit run app.py
   ```
6. Abra no navegador o endereço exibido (geralmente `http://localhost:8501`).

---

## ☁️ Publicando no **Streamlit Community Cloud**

1. **Código no GitHub** (sem `fleet.db` versionado).  
2. Acesse **Community Cloud** → **New app** → selecione seu repositório/branch.  
3. **Secrets do Dropbox** (no painel do app: *Settings → Secrets*):  
   - Opção rápida (token simples):
     ```toml
     [dropbox]
     access_token = "SEU_ACCESS_TOKEN"
     path = "/fleet.db"
     ```
   - Opção recomendada (token com **refresh**, não expira):
     ```toml
     [dropbox]
     app_key = "SUA_APP_KEY"
     app_secret = "SUA_APP_SECRET"
     refresh_token = "SEU_REFRESH_TOKEN"
     path = "/fleet.db"
     ```
4. **Dependencies**: garanta no `requirements.txt` (mínimo):
   ```
   streamlit
   pandas
   dropbox
   ```
5. Faça o **deploy**. Ao gravar dados, o app enviará o `fleet.db` ao Dropbox; nos próximos restarts ele restaurará automaticamente.

> **Atenção**: O Streamlit Cloud pode **hibernar** após período sem uso e possui limites de CPU/RAM/armazenamento (não é “ilimitado”). Por isso usamos um storage externo (Dropbox) para manter os dados.

---

## 🔌 Como integrar **Dropbox** (detalhes)

1. **Crie um app** no Dropbox App Console:  
   - Tipo: **Scoped access**; Pasta: **App folder** (recomendado).  
   - Permissões: `files.content.read` e `files.content.write`.

2. **Gere credenciais**:
   - **Rápido**: *Generate access token* (pode expirar).  
   - **Recomendado**: **Refresh Token** (fluxo OAuth offline): obtenha `app_key`, `app_secret` e gere `refresh_token` com um pequeno script local usando o SDK Python.

3. **Adicione ao `secrets`** (Cloud e/ou local) conforme blocos acima.

4. **Comportamento do app**:
   - Startup: tenta baixar `fleet.db` do `path` informado.
   - Gravação: faz upload (overwrite) do arquivo.
   - Reinício: restaura do Dropbox e segue do último estado.

> **Boas práticas**: manter o `fleet.db` pequeno (use `VACUUM` periódico), não versionar o `.db` no GitHub, conferir se o `path` do secrets aponta para o lugar correto da **App Folder** no Dropbox.

---

## 🧩 Estrutura das tabelas (resumo)

- `parameters (id, category, value)`  
- `vehicles (plate PK, model, year, fuel_type, tank_l, owner, status, notes)`  
- `drivers (id PK, name, license, salary, status, notes)`  
- `fuelings (id PK, date, plate FK, liters, price_per_l, total, station, notes)`  
- `trips (id PK, date, plate FK, driver_id FK, freight_value, origin, destination, km_start, km_end, km_driven, cargo, client, notes)`  
- `maints (id PK, date, plate FK, type, cost, notes)`  
- `costs (id PK, date, category, plate FK, driver_id FK, amount, notes)`

> Datas são armazenadas como `TEXT` em **YYYY-MM-DD** (ISO), o que mantém **ordenação e filtros** corretos.

---

## 🛠 Dicas e solução de problemas

- **Mudanças não persistem após restart**  
  - Verifique se o `fleet.db` **não** está versionado no Git.
  - Confirme os **secrets do Dropbox** (token, `path`).
  - Confira, no Dropbox, se o arquivo **mudou de hora/tamanho** após salvar no app.
  - Se seu código usa `sqlite3` direto, inclua um *backup* no final do script (função `force_backup()` caso exista).

- **Arquivo WAL (`fleet.db-wal`)**  
  - Garanta `PRAGMA journal_mode=DELETE;` e/ou `PRAGMA wal_checkpoint(TRUNCATE);` antes do upload para que tudo esteja consolidado no `fleet.db` principal.

- **Limites do Dropbox**  
  - Plano gratuito tem **2 GB** totais. Se a cota acabar, o upload falha.
  - Upload simples atende arquivos **≤ 150 MB**. Acima disso, use upload em chunks.

- **Streamlit Cloud hibernou**  
  - É normal; ao acessar, ele “acorda”. O disco local é efêmero por design.

---

## 🗺 Roadmap (opcional)

- Modo **edição com senha** (só usuários autorizados podem gravar).  
- Exportações (CSV/Excel/PDF).  
- Migração opcional para **Turso** (libSQL) ou **Postgres/Supabase** para melhor concorrência.

---

## 📄 Licença

Defina a licença do seu projeto (ex.: MIT).

---

## 🙌 Créditos

Projeto de gestão de frota em **Streamlit** com persistência simplificada para uso pessoal e pequenas equipes.
