@echo off
rem Avvia CRN Manutenzione PC chiedendo i privilegi di amministratore.
rem Se si rifiuta la richiesta, il programma parte comunque con funzioni limitate.
cd /d "%~dp0"
set "CRN_PS1=%~dp0CRNManutenzione.ps1"
net session >nul 2>&1
if %errorlevel% equ 0 goto avvia
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "try { Start-Process powershell.exe -Verb RunAs -WindowStyle Hidden -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-STA','-WindowStyle','Hidden','-File',('\"' + $env:CRN_PS1 + '\"') -ErrorAction Stop } catch { exit 1 }"
if errorlevel 1 goto avvia
exit /b
:avvia
start "" powershell.exe -NoProfile -ExecutionPolicy Bypass -STA -WindowStyle Hidden -File "%CRN_PS1%"
