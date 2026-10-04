@echo off
setlocal
echo ========================================================
echo       Instalador do Status Line Pro para Claude Code
echo ========================================================
echo.

set "SRC_DIR=%~dp0src"
set "BIN_DIR=%~dp0bin"
set "TARGET_CLAUDE=%USERPROFILE%\.claude"
set "TARGET_ORCA=%USERPROFILE%\.orca\agent-hooks"

if not exist "%TARGET_CLAUDE%" mkdir "%TARGET_CLAUDE%" 2>nul
if not exist "%TARGET_ORCA%" mkdir "%TARGET_ORCA%" 2>nul

echo [1/3] Copiando binarios e renderizadores...
if exist "%BIN_DIR%\statusline.exe" copy /Y "%BIN_DIR%\statusline.exe" "%TARGET_CLAUDE%\statusline.exe" >nul
copy /Y "%SRC_DIR%\statusline_renderer.py" "%TARGET_CLAUDE%\statusline_renderer.py" >nul
copy /Y "%BIN_DIR%\statusline.cmd" "%TARGET_CLAUDE%\statusline.cmd" >nul
copy /Y "%BIN_DIR%\claude-statusline.cmd" "%TARGET_ORCA%\claude-statusline.cmd" >nul

echo [2/3] Verificando ambiente de execucao...
if exist "%TARGET_CLAUDE%\statusline.exe" (
    echo Motor Go nativo detectado (statusline.exe pronto para latencia ultra-baixa).
) else (
    python --version >nul 2>&1
    if errorlevel 1 (
        echo AVISO: Nem Go compilado nem Python foram localizados!
    ) else (
        echo Python detectado como fallback.
    )
)

echo [3/3] Testando renderizacao...
echo {"model":{"display_name":"StatusLine-Pro"},"context_window":{"context_window_size":200000,"used_tokens":50000},"usage":{"input_tokens":50000,"output_tokens":250,"cache_read_input_tokens":10000}} | call "%BIN_DIR%\statusline.cmd"

echo.
echo ========================================================
echo  Instalacao concluida com sucesso!
echo  Abra um terminal com Claude Code para ver a barra ativa.
echo ========================================================
pause
