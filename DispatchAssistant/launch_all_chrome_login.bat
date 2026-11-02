@echo off
title Launch All Chrome CDP Sessions - DispatchAssistant
echo ============================================================
echo  Membuka Semua Jendela Chrome Sesi Bot (Port 9223 - 9228)
echo ============================================================
echo.
echo Silakan login manual dengan username baru (40010176) di
echo setiap jendela Chrome yang terbuka. Sesi akan tersimpan!
echo.

set CHROME_EXE="C:\Program Files\Google\Chrome\Application\chrome.exe"

echo 1. Launching Chrome CANCLWORK (Port 9223)...
start "" %CHROME_EXE% --remote-debugging-port=9223 --user-data-dir="C:\ChromeDebug_CANCLWORK" --no-first-run --no-default-browser-check "https://sygap.telkom.co.id/req_fulfillment"
timeout /t 2 /nobreak >nul

echo 2. Launching Chrome DISPATCH (Port 9224)...
start "" %CHROME_EXE% --remote-debugging-port=9224 --user-data-dir="C:\ChromeDebug_DISPATCH" --no-first-run --no-default-browser-check "https://sygap.telkom.co.id/req_fulfillment"
timeout /t 2 /nobreak >nul

echo 3. Launching Chrome GAMAS (Port 9225)...
start "" %CHROME_EXE% --remote-debugging-port=9225 --user-data-dir="C:\ChromeDebug_GAMAS" --no-first-run --no-default-browser-check "https://sygap.telkom.co.id/req_fulfillment"
timeout /t 2 /nobreak >nul

echo 4. Launching Chrome REPORT (Port 9226)...
start "" %CHROME_EXE% --remote-debugging-port=9226 --user-data-dir="C:\ChromeDebug_REPORT" --no-first-run --no-default-browser-check "https://sygap.telkom.co.id/req_fulfillment" "https://sygap.telkom.co.id/incident"
timeout /t 2 /nobreak >nul

echo 5. Launching Chrome CHANGE SERVICE ID (Port 9227)...
start "" %CHROME_EXE% --remote-debugging-port=9227 --user-data-dir="C:\ChromeDebug_CHANGE_SERVICE_ID" --no-first-run --no-default-browser-check "https://sygap.telkom.co.id/req_fulfillment"
timeout /t 2 /nobreak >nul

echo 6. Launching Chrome INCIDENT (Port 9228)...
start "" %CHROME_EXE% --remote-debugging-port=9228 --user-data-dir="C:\ChromeDebug_INCIDENT" --no-first-run --no-default-browser-check "https://sygap.telkom.co.id/incident"
timeout /t 2 /nobreak >nul

echo.
echo ============================================================
echo Semua jendela Chrome sudah diluncurkan.
echo Silakan login sekali di tiap jendela yang meminta login.
echo ============================================================
pause
