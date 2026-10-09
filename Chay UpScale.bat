@echo off
rem Mở AIEZO UpScale từ mã nguồn (không hiện cửa sổ dòng lệnh)
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
  echo Chua co moi truong Python. Xem README.md, muc "Cai dat tu dau".
  pause
  exit /b 1
)
if not exist "frontend\dist\index.html" (
  echo Chua build giao dien. Chay: cd frontend ^&^& npm install ^&^& npm run build
  pause
  exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" main.py
