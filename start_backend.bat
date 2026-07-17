@echo off
cd /d "%~dp0backend"
if not exist .venv python -m venv .venv
call .venv\Scripts\activate
pip install -r requirements.txt -q
if not exist .env copy .env.example .env
echo Starting Job Hunt Agent API on http://0.0.0.0:8000
python main.py
