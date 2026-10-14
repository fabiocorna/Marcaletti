@echo off
REM Crea l'eseguibile Windows di PDF Studio in dist\PDFStudio\PDFStudio.exe
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
    --name PDFStudio ^
    --icon assets\pdfstudio.ico ^
    --add-data "assets;assets" ^
    main.py || goto :error

echo.
echo Fatto! Eseguibile: dist\PDFStudio\PDFStudio.exe
echo Per creare l'installer apri installer.iss con Inno Setup (https://jrsoftware.org/isinfo.php).
goto :eof

:error
echo.
echo ERRORE durante la compilazione.
exit /b 1
