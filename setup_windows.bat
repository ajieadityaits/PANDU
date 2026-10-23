@echo off
setlocal
cd /d "%~dp0"
py -3.12 -m venv .venv
if errorlevel 1 (
  echo [ERROR] Python 3.12 tidak ditemukan. Instal Python 3.10-3.12 64-bit.
  pause
  exit /b 1
)
call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
echo.
echo Setup selesai. Jalankan run_windows.bat.
pause
endlocal

