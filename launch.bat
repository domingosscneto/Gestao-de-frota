@echo off
REM Inicializador rápido no Windows
python -m venv .venv
call .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
