@echo off
REM Crea l'eseguibile Windows di CRN Computo in dist\CRNComputo\CRNComputo.exe
REM Requisiti: Python 3.10+ per Windows (https://www.python.org/downloads/)
setlocal
cd /d "%~dp0"

if not exist .venv (
    py -3 -m venv .venv || python -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt || goto :error

python -m pytest -q tests || goto :error

pyinstaller --noconfirm --clean --windowed ^
    --name CRNComputo ^
    --icon assets\computo.ico ^
    --add-data "assets;assets" ^
    --collect-submodules keyring ^
    main.py || goto :error

echo.
echo Fatto! Eseguibile: dist\CRNComputo\CRNComputo.exe
goto :eof

:error
echo.
echo ERRORE durante la compilazione.
exit /b 1
