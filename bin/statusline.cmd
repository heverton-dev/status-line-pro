@echo off
setlocal
if exist "%USERPROFILE%\.claude\statusline_renderer.py" (
    python "%USERPROFILE%\.claude\statusline_renderer.py"
)
exit /b 0
