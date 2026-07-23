@echo off
title Chrome CDP - DispatchAssistant

echo ==========================================
echo  Chrome CDP Launcher (Guest Mode)
echo  Port: 9222
echo ==========================================
echo.

set CHROME_EXE="C:\Program Files\Google\Chrome\Application\chrome.exe"
set CDP_PROFILE=C:\ChromeCDP

echo Profile: %CDP_PROFILE%
echo.

start "" %CHROME_EXE% ^
    --remote-debugging-port=9222 ^
    --user-data-dir="%CDP_PROFILE%" ^
    --no-first-run ^
    "https://sygap.telkom.co.id/req_fulfillment" ^
    "https://biscuit-dashboard-dev-playground.apps.mypaas.telkom.co.id/helpdesk/tools/inseratools"

timeout /t 3 /nobreak >nul

netstat -an | findstr :9222 >nul
if %ERRORLEVEL% EQU 0 (
    echo Chrome CDP berhasil dijalankan!
) else (
    echo [WARNING] Port 9222 belum aktif, tunggu beberapa detik...
)

echo.
echo Chrome akan membuka sebagai GUEST (terpisah dari akun utama).
echo Login SYGAP dan Biscuit di Chrome baru ini.
echo.
pause
