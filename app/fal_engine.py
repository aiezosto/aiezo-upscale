"""Tuỳ chọn trả phí: SeedVR2 chạy trên máy chủ fal.ai (fal-ai/seedvr/upscale/image).

Giá công bố: 0,001 USD / megapixel ảnh ra (ảnh 4K ≈ 0,008 USD, 8K ≈ 0,033 USD). Cần khoá API fal.ai
(người dùng tự tạo tài khoản tại fal.ai và nạp tiền). Dùng khi muốn 8K bằng SeedVR2 trọn vẹn
(GPU 12 GB không đủ bộ nhớ) hoặc máy không có GPU.
"""
from __future__ import annotations

import base64
import io
import threading
import time

import httpx
import numpy as np
from PIL import Image

from .models import Cancelled, ProgressFn

ENDPOINT = "fal-ai/seedvr/upscale/image"
QUEUE_URL = f"https://queue.fal.run/{ENDPOINT}"
PRICE_PER_MP = 0.001


def estimate_cost(w: int, h: int) -> float:
    return w * h / 1e6 * PRICE_PER_MP


def _data_uri(rgb: np.ndarray) -> str:
    im = Image.fromarray(np.round(np.clip(rgb, 0, 1) * 255).astype(np.uint8), "RGB")
    buf = io.BytesIO()
    im.save(buf, "PNG")
    data, mime = buf.getvalue(), "image/png"
    if len(data) > 8 * 1024 * 1024:  # ảnh vào quá lớn: gửi JPEG chất lượng cao cho nhẹ
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=97, subsampling=0)
        data, mime = buf.getvalue(), "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode(data).decode("ascii")


def run(rgb: np.ndarray, factor: float, api_key: str, progress: ProgressFn,
        cancel: threading.Event, seed: int = 42) -> np.ndarray:
    if not api_key:
        raise ValueError("Chưa nhập khoá API fal.ai trong Cài đặt.")
    factor = float(min(10.0, max(1.0, factor)))
    headers = {"Authorization": f"Key {api_key}"}
    body = {"image_url": _data_uri(rgb), "upscale_mode": "factor", "upscale_factor": round(factor, 3),
            "noise_scale": 0.1, "output_format": "png", "seed": seed}
    with httpx.Client(timeout=httpx.Timeout(120.0, connect=20.0)) as c:
        progress(0.05, "fal.ai: đang gửi ảnh lên máy chủ")
        r = c.post(QUEUE_URL, json=body, headers=headers)
        if r.status_code >= 400:
            raise RuntimeError(f"fal.ai từ chối yêu cầu ({r.status_code}): {r.text[:400]}")
        job = r.json()
        status_url, response_url = job["status_url"], job["response_url"]
        t0 = time.time()
        while True:
            if cancel.is_set():
                try:
                    c.put(job.get("cancel_url", f"{QUEUE_URL}/requests/{job['request_id']}/cancel"), headers=headers)
                finally:
                    raise Cancelled()
            s = c.get(status_url, headers=headers).json()
            st = s.get("status")
            if st == "COMPLETED":
                break
            if st not in ("IN_QUEUE", "IN_PROGRESS"):
                raise RuntimeError(f"fal.ai báo lỗi: {s}")
            el = time.time() - t0
            msg = "đang xếp hàng" if st == "IN_QUEUE" else "đang xử lý"
            progress(min(0.85, 0.1 + el / 120), f"fal.ai: {msg} ({int(el)} giây)")
            if el > 900:
                raise TimeoutError("fal.ai xử lý quá 15 phút.")
            time.sleep(1.5)
        res = c.get(response_url, headers=headers)
        if res.status_code >= 400:
            raise RuntimeError(f"fal.ai trả lỗi ({res.status_code}): {res.text[:400]}")
        url = res.json()["image"]["url"]
        progress(0.9, "fal.ai: đang tải ảnh kết quả về")
        img = c.get(url, timeout=300.0)
        img.raise_for_status()
    out = Image.open(io.BytesIO(img.content)).convert("RGB")
    return np.asarray(out, dtype=np.float32) / 255.0


def test_key(api_key: str) -> str:
    """Gửi ảnh 64x64 phóng x2 (≈ 0,00002 USD) để kiểm tra khoá."""
    rgb = np.full((64, 64, 3), 0.5, np.float32)
    rgb[16:48, 16:48] = (0.49, 0.75, 0.32)
    out = run(rgb, 2, api_key, lambda f, m: None, threading.Event())
    return f"Kết nối fal.ai thành công: nhận ảnh {out.shape[1]}×{out.shape[0]} px."
