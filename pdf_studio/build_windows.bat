@echo off
REM Crea l'eseguibile Windows di CRN PDF Studio in dist\CRNPDFStudio\CRNPDFStudio.exe
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
    --name CRNPDFStudio ^
    --icon assets\pdfstudio.ico ^
    --add-data "assets;assets" ^
    main.py || goto :error

echo.
xcopy /E /I /Y tools dist\CRNPDFStudio\tools >nul
echo Fatto! Eseguibile: dist\CRNPDFStudio\CRNPDFStudio.exe
echo Per creare l'installer apri installer.iss con Inno Setup (https://jrsoftware.org/isinfo.php).
goto :eof

:error
echo.
echo ERRORE durante la compilazione.
exit /b 1
