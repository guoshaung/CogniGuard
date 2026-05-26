@echo off
cd /d "%~dp0\.."
python src\main.py --config configs\config.yaml --mode demo
