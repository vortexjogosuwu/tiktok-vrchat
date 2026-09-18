@echo off
REM =============================================================
REM iniciar_app.bat
REM Inicia a interface grafica (app.py) usando um ambiente virtual
REM Python local (pasta "venv"), criando e instalando dependencias
REM automaticamente na primeira vez que for executado.
REM =============================================================

setlocal
cd /d "%~dp0"

set VENV_DIR=.venv
set PYTHON_EXE=%VENV_DIR%\Scripts\python.exe

REM --- Verifica se o Python esta instalado no sistema ---
where python >nul 2>nul
if errorlevel 1 (
    echo [ERRO] Python nao foi encontrado no PATH do sistema.
    echo Instale o Python em https://www.python.org/downloads/ e marque
    echo a opcao "Add Python to PATH" durante a instalacao.
    pause
    exit /b 1
)

REM --- Cria o ambiente virtual local, se ainda nao existir ---
if not exist "%PYTHON_EXE%" (
    echo [SETUP] Ambiente virtual nao encontrado. Criando em ".\%VENV_DIR%"...
    python -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [ERRO] Falha ao criar o ambiente virtual.
        pause
        exit /b 1
    )

    echo [SETUP] Instalando dependencias do requirements.txt...
    "%PYTHON_EXE%" -m pip install --upgrade pip
    "%PYTHON_EXE%" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERRO] Falha ao instalar as dependencias.
        pause
        exit /b 1
    )
)

echo [INFO] Iniciando a interface grafica...
"%PYTHON_EXE%" app.py

if errorlevel 1 (
    echo.
    echo [ERRO] O programa terminou com um erro. Veja as mensagens acima.
    pause
)

endlocal
