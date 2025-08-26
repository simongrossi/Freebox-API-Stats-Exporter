#!/usr/bin/env bash
set -e
echo "📦 Installation des dépendances..."
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
echo "🚀 Lancement de Freebox API Stats Exporter..."
python3 -m streamlit run app.py
