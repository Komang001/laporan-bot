@echo off
title Chrome CDP - Report Request (AGENT)
echo ==========================================
echo  Chrome CDP Launcher - Report Request
echo  Port : 9229
echo  Profil: C:\ChromeDebug_REPORT_REQUEST
echo ==========================================
echo.

set CHROME_EXE="C:\Program Files\Google\Chrome\Application\chrome.exe"
set CDP_PROFILE=C:\ChromeDebug_REPORT_REQUEST

echo Profile: %CDP_PROFILE%
echo.

start "" %CHROME_EXE% ^
    --remote-debugging-port=9229 ^
    --user-data-dir="%CDP_PROFILE%" ^
    --no-first-run ^
    "https://sygap.telkom.co.id//req_fulfillment"

timeout /t 3 /nobreak >nul

netstat -an | findstr :9229 >nul
if %ERRORLEVEL% EQU 0 (
    echo Chrome 9229 berhasil dijalankan!
) else (
    echo [WARNING] Port 9229 belum aktif, tunggu beberapa detik...
)

echo.
echo LOGIN SYGAP sebagai AGENT di Chrome ini (SEKALI saja).
echo Sesi login akan persist di profil %CDP_PROFILE%.
echo Biarkan Chrome 9229 tetap MENYALA agar bot report bisa baca
echo antrian Request tim (100+ completed) untuk laporan.
echo.
pause
