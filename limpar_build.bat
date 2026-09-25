@echo off
REM =============================================================
REM limpar_build.bat
REM Remove os arquivos/pastas que o build_exe.bat CRIA (build\,
REM dist\, build_log.txt) e as pastas __pycache__ (cache do Python),
REM deixando a pasta do projeto limpa de novo.
REM
REM NAO mexe em: .venv\ (ambiente virtual, reaproveitado entre builds)
REM nem em tiktok_vrchat.spec (arquivo de configuracao do projeto,
REM nao e gerado pelo build -- e usado por ele).
REM
REM Copie o TikTokVRChatBridge.exe (dentro de dist\) pra outro lugar
REM ANTES de rodar isso -- ele tambem sera apagado.
REM =============================================================

setlocal
cd /d "%~dp0"

echo Isso vai apagar, se existirem:
echo   - build\
echo   - dist\        (contem o TikTokVRChatBridge.exe -- copie antes!)
echo   - build_log.txt
echo   - pastas __pycache__ (em qualquer lugar do projeto)
echo.
echo NAO mexe em .venv\ nem em tiktok_vrchat.spec.
echo.
set /p CONFIRMA="Continuar? (S/N): "
if /i not "%CONFIRMA%"=="S" (
    echo Cancelado.
    pause
    exit /b 0
)

if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "build_log.txt" del /q "build_log.txt"

echo Removendo pastas __pycache__...
for /f "delims=" %%D in ('dir /s /b /ad "__pycache__" 2^>nul') do (
    rmdir /s /q "%%D"
)

echo.
echo [OK] Pasta limpa.
pause
endlocal
