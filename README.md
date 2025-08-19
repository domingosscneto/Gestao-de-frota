# Sistema de Gestão de Frota (Streamlit)

Este projeto é um **sistema completo de gestão de frota** inspirado em modelos de planilha e dashboards do YouTube.
Ele permite **cadastrar veículos e motoristas**, **registrar abastecimentos, viagens, manutenções e outros custos**,
e acompanha um **Painel (Dashboard)** com indicadores e gráficos mensais.

## Como executar (Windows/Mac/Linux)

1. Instale o Python 3.9+ (https://www.python.org/downloads/).
2. No terminal/prompt, entre na pasta do projeto e crie um ambiente virtual (opcional, mas recomendado):
   ```bash
   python -m venv .venv
   # Windows
   .venv\Scripts\activate
   # macOS/Linux
   source .venv/bin/activate
   ```
3. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```
4. Inicie o sistema:
   ```bash
   streamlit run app.py
   ```

## Organização

- `app.py` — aplicativo Streamlit principal (UI, formulários, painéis).
- `db.py` — camada de persistência, criação do banco, consultas auxiliares.
- `fleet.db` — banco de dados SQLite (criado automaticamente ao iniciar).
- `requirements.txt` — dependências Python.
- `launch.bat` — atalho para Windows que cria venv, instala dependências e inicia o app.

## Importante

- As listas de **Parâmetros** (Tipos de Manutenção, Tipos de Custo, Combustíveis, Status, Postos, Fornecedores)
  podem ser personalizadas na aba **Parâmetros** no próprio app.
- Todos os relatórios possuem botões para exportar os dados em CSV.
- O Painel mostra KPIs e gráficos por mês de: combustível, manutenção e km rodados.

> Dúvidas ou quer que eu personalize 100% igual ao seu vídeo/base original? Posso ajustar aparência, campos,
  regras de validação e indicadores sob demanda.
