@echo off
echo ============================================
echo  Freebox API Stats Exporter - Setup & Launch
echo ============================================

REM (Optionnel) Activer un venv :
REM if not exist .venv (
REM     python -m venv .venv
REM )
REM call .venv\Scripts\activate.bat

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m streamlit run app.py
