@echo off
REM =============================================================
REM build_exe.bat
REM Gera um .exe standalone do programa (TikTokVRChatBridge.exe),
REM que roda em qualquer PC Windows SEM precisar instalar Python.
REM
REM Precisa rodar isso no Windows de verdade -- nao da pra gerar um
REM .exe do Windows a partir de outro sistema operacional.
REM
REM O .exe final fica em: dist\TikTokVRChatBridge.exe
REM
REM Este script SEMPRE grava tudo que aconteceu em build_log.txt,
REM nesta mesma pasta -- assim, mesmo que a janela feche rapido
REM demais pra ler, da pra abrir esse arquivo depois (ou mandar
REM pra alguem ajudar a descobrir o que deu errado).
REM =============================================================

if "%~1"=="__LOGGED__" goto :run
%ComSpec% /c "%~f0" __LOGGED__ > "%~dp0build_log.txt" 2>&1
echo ============================================================
echo  Saida completa (tambem salva em build_log.txt):
echo ============================================================
type "%~dp0build_log.txt"
echo ============================================================
pause
exit /b

:run
setlocal
cd /d "%~dp0"

set VENV_DIR=.venv
set PYTHON_EXE=%VENV_DIR%\Scripts\python.exe

echo [INFO] Pasta do projeto: %CD%
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [ERRO] Python nao foi encontrado no PATH do sistema.
    echo Instale o Python em https://www.python.org/downloads/ e marque
    echo a opcao "Add Python to PATH" durante a instalacao.
    echo ^(Isso e so pra GERAR o .exe -- quem for so USAR o .exe pronto
    echo depois nao precisa de Python instalado.^)
    exit /b 1
)

python --version
echo.

if not exist "%PYTHON_EXE%" (
    echo [SETUP] Ambiente virtual nao encontrado. Criando em ".\%VENV_DIR%"...
    python -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [ERRO] Falha ao criar o ambiente virtual.
        exit /b 1
    )
    echo [SETUP] Ambiente virtual criado.
) else (
    echo [SETUP] Reaproveitando ambiente virtual existente em ".\%VENV_DIR%".
)
echo.

echo [SETUP] Atualizando pip...
"%PYTHON_EXE%" -m pip install --upgrade pip --disable-pip-version-check
if errorlevel 1 (
    echo [ERRO] Falha ao atualizar o pip.
    exit /b 1
)
echo.

echo [SETUP] Instalando dependencias do programa (requirements.txt)...
"%PYTHON_EXE%" -m pip install -r requirements.txt --disable-pip-version-check
if errorlevel 1 (
    echo [ERRO] Falha ao instalar requirements.txt.
    exit /b 1
)
echo.

echo [SETUP] Instalando PyInstaller (requirements-dev.txt)...
"%PYTHON_EXE%" -m pip install -r requirements-dev.txt --disable-pip-version-check
if errorlevel 1 (
    echo [ERRO] Falha ao instalar requirements-dev.txt.
    exit /b 1
)
echo.

echo [SETUP] Limpando builds antigos...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
echo.

echo [BUILD] Gerando o .exe com PyInstaller (isso pode demorar alguns minutos)...
echo.
"%PYTHON_EXE%" -m PyInstaller tiktok_vrchat.spec
if errorlevel 1 (
    echo.
    echo [ERRO] A geracao do .exe falhou. Veja as mensagens do PyInstaller acima.
    exit /b 1
)

echo.
if exist "dist\TikTokVRChatBridge.exe" (
    echo [OK] Pronto! O executavel esta em:
    echo      dist\TikTokVRChatBridge.exe
    echo.
    echo Copie esse arquivo ^(e um config.yaml ao lado dele^) pra qualquer
    echo pasta, em qualquer PC Windows -- nao precisa de Python instalado
    echo la pra rodar.
) else (
    echo [ERRO] O PyInstaller terminou sem erro, mas o arquivo
    echo dist\TikTokVRChatBridge.exe nao foi encontrado. Algo incomum
    echo aconteceu -- confira as mensagens acima.
    exit /b 1
)

endlocal
