"""SeedVR2 (ByteDance Seed, Apache-2.0): khôi phục + phóng ảnh bằng diffusion một bước, chạy trên GPU của máy.

Diffusion một bước: tăng chi tiết mà giữ nguyên người, vật, bố cục.
Chạy bằng CLI của bản ComfyUI-SeedVR2_VideoUpscaler (engines/seedvr2) trong một tiến trình con:
VRAM được trả lại ngay khi xong, huỷ được bằng cách dừng tiến trình.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

from .models import Cancelled, ProgressFn
from .paths import FROZEN, MODELS_DIR, RESOURCE_DIR

ENGINE_DIR = RESOURCE_DIR / "engines" / "seedvr2"
SEEDVR2_MODELS = MODELS_DIR / "seedvr2"
VAE_FILE = "ema_vae_fp16.safetensors"


@dataclass(frozen=True)
class Variant:
    key: str
    file: str
    label: str
    description: str


VARIANTS: dict[str, Variant] = {
    "3b": Variant("3b", "seedvr2_ema_3b_fp8_e4m3fn.safetensors", "SeedVR2 3B",
                  "Nhanh hơn (~50 giây cho ảnh 4K trên RTX 3060). Tự nhiên, ít sai chi tiết."),
    "7b_sharp": Variant("7b_sharp", "seedvr2_ema_7b_sharp-Q4_K_M.gguf", "SeedVR2 7B sharp",
                        "Model lớn, bản nét: chi tiết da, vải, gỗ rõ hơn (~65 giây cho 4K)."),
}


def installed(key: str) -> bool:
    v = VARIANTS[key]
    return (SEEDVR2_MODELS / v.file).exists() and (SEEDVR2_MODELS / VAE_FILE).exists() and ENGINE_DIR.exists()


def _launcher() -> list[str]:
    # Bản EXE gọi lại chính nó với cờ --seedvr2; bản mã nguồn gọi main.py bằng cùng Python
    if FROZEN:
        return [sys.executable, "--seedvr2"]
    py = Path(sys.executable)
    if py.name.lower() == "pythonw.exe":  # cần stdout để đọc tiến độ
        py = py.with_name("python.exe")
    return [str(py), str(RESOURCE_DIR / "main.py"), "--seedvr2"]


# (chuỗi trong nhật ký CLI, tiến độ 0..1, thông báo)
_PHASES = [
    ("Phase 1: VAE encoding", 0.10, "Đang mã hoá ảnh (VAE)"),
    ("Phase 2: DiT upscaling", 0.25, "Đang nạp model và tái tạo chi tiết (DiT)"),
    ("EulerSampler: 100%", 0.70, "Đã tái tạo xong, chuẩn bị giải mã"),
    ("Phase 3: VAE decoding", 0.72, "Đang giải mã ảnh độ phân giải cao (VAE)"),
    ("Phase 4: Post-processing", 0.92, "Đang cân màu theo ảnh gốc"),
    ("Output saved", 0.98, "Đã tạo xong ảnh"),
]


def run(rgb: np.ndarray, short_side: int, variant: str, progress: ProgressFn,
        cancel: threading.Event, seed: int = 42) -> np.ndarray:
    """rgb: HxWx3 float 0..1. Trả ảnh có cạnh ngắn ≈ short_side (CLI làm tròn theo bội số 2)."""
    v = VARIANTS[variant]
    if not installed(variant):
        raise FileNotFoundError(f"Thiếu file model SeedVR2: models/seedvr2/{v.file} hoặc {VAE_FILE}. "
                                "Chạy download_models.py để tải.")
    with tempfile.TemporaryDirectory(prefix="aiezo_seedvr2_") as td:
        src = Path(td) / "input.png"
        dst = Path(td) / "output.png"
        Image.fromarray(np.round(np.clip(rgb, 0, 1) * 255).astype(np.uint8), "RGB").save(src)
        cmd = _launcher() + [
            str(src), "--output", str(dst), "--output_format", "png",
            "--resolution", str(int(short_side)), "--batch_size", "1", "--seed", str(seed),
            "--model_dir", str(SEEDVR2_MODELS), "--dit_model", v.file,
            "--vae_encode_tiled", "--vae_decode_tiled",
        ]
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                encoding="utf-8", errors="replace", env=env, creationflags=flags)
        tail: list[str] = []
        stop = threading.Event()

        def watch_cancel():
            while not stop.wait(0.3):
                if cancel.is_set() and proc.poll() is None:
                    proc.kill()

        threading.Thread(target=watch_cancel, daemon=True).start()
        progress(0.02, f"{v.label}: đang khởi động")
        try:
            assert proc.stdout is not None
            for line in proc.stdout:
                line = line.rstrip()
                if line:
                    tail = (tail + [line])[-25:]
                for key, val, msg in _PHASES:
                    if key in line:
                        progress(val, f"{v.label}: {msg}")
            proc.wait()
        finally:
            stop.set()
        if cancel.is_set():
            raise Cancelled()
        if proc.returncode != 0 or not dst.exists():
            raise RuntimeError("SeedVR2 lỗi:\n" + "\n".join(tail[-12:]))
        out = np.asarray(Image.open(dst).convert("RGB"), dtype=np.float32) / 255.0
    return out
