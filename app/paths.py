"""Đường dẫn dùng chung: chạy từ mã nguồn hoặc từ bản đóng gói PyInstaller."""
from __future__ import annotations

import os
import sys
from pathlib import Path

FROZEN = getattr(sys, "frozen", False)

# Thư mục chứa tài nguyên đi kèm (models/, frontend/dist/)
RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) if FROZEN else Path(__file__).resolve().parent.parent

MODELS_DIR = RESOURCE_DIR / "models"
FRONTEND_DIST = RESOURCE_DIR / "frontend" / "dist"

# Dữ liệu người dùng (cài đặt, nhật ký) nằm trong %APPDATA%, không ghi vào thư mục cài đặt
DATA_DIR = Path(os.environ.get("APPDATA", Path.home())) / "AIEZO UpScale"
DATA_DIR.mkdir(parents=True, exist_ok=True)
SETTINGS_FILE = DATA_DIR / "settings.json"
LOG_FILE = DATA_DIR / "upscale.log"

# Thư mục lưu ảnh kết quả mặc định
DEFAULT_OUTPUT_DIR = Path.home() / "Pictures" / "AIEZO UpScale"
