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

echo [1/3] Copiando renderizador e wrappers...
copy /Y "%SRC_DIR%\statusline_renderer.py" "%TARGET_CLAUDE%\statusline_renderer.py" >nul
copy /Y "%BIN_DIR%\statusline.cmd" "%TARGET_CLAUDE%\statusline.cmd" >nul
copy /Y "%BIN_DIR%\claude-statusline.cmd" "%TARGET_ORCA%\claude-statusline.cmd" >nul

echo [2/3] Verificando Python no PATH...
python --version >nul 2>&1
if errorlevel 1 (
    echo AVISO: Python nao foi localizado no PATH! Certifique-se de instalar Python 3.8+.
) else (
    echo Python detectado com sucesso.
)

echo [3/3] Testando renderizacao...
echo {"model":{"display_name":"StatusLine-Pro"},"context_window":{"context_window_size":200000,"used_tokens":50000},"usage":{"input_tokens":50000,"output_tokens":250,"cache_read_input_tokens":10000}} | python "%TARGET_CLAUDE%\statusline_renderer.py"

echo.
echo ========================================================
echo  Instalacao concluida com sucesso!
echo  Abra um terminal com Claude Code para ver a barra ativa.
echo ========================================================
pause
