@echo off
setlocal
cd /d "%~dp0"
py -3 main.py
if errorlevel 1 (
    echo.
    echo Nao foi possivel iniciar o Projeto Fusion Jiu Jitsu.
    echo Confira se o Python 3 esta instalado. Veja o README.md para instrucoes.
    pause
)
