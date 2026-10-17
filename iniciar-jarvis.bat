@echo off
title Jarvis
cd /d "%~dp0"
call .venv\Scripts\activate.bat
python servidor.py
pause
