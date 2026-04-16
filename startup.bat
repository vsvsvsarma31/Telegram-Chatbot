@echo off
:: ============================================================
:: BEFORE FIRST RUN:
::   setx TELEGRAM_TOKEN "123456789:your_bot_token_here"
::   setx ALLOWED_TELEGRAM_USER_ID "123456789"
::
:: Restart the terminal after running setx so Windows reloads them.
:: ============================================================
:: HOW TO AUTO-START ON BOOT:
::   Press Win+R, type shell:startup, then press Enter.
::   Drag or copy a shortcut of this .bat file into that folder.
::   Windows will launch it automatically every time you log in.
:: ============================================================

cd /d "%~dp0"

py main.py

if %errorlevel% == 9009 (
    echo.
    echo *** Python not found. Install Python and add it to PATH. ***
    echo.
)

pause
