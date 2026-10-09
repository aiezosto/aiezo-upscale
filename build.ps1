# Đóng gói AIEZO UpScale: build giao diện rồi PyInstaller → dist\AIEZO UpScale\AIEZO UpScale.exe
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Push-Location frontend
npm install --no-audit --no-fund
npm run build
Pop-Location

.\.venv\Scripts\python.exe download_models.py
if ($LASTEXITCODE -ne 0) { throw "Thiếu hoặc sai file model" }

.\.venv\Scripts\python.exe -m PyInstaller UpScale.spec --noconfirm --clean
Write-Host "Xong: dist\AIEZO UpScale\AIEZO UpScale.exe"
