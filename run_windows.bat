@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] Virtual environment belum ada.
  echo Jalankan setup_windows.bat terlebih dahulu.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -c "import cv2_enumerate_cameras, pythoncom, win32com.client" >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Dependensi kamera atau Windows SAPI belum terpasang.
  echo Jalankan setup_windows.bat lagi setelah perubahan source code.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" main.py
endlocal
