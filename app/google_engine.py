"""Tuỳ chọn: phóng ảnh bằng Google Imagen Upscale (Vertex AI, trả phí theo ảnh).

Chỉ chạy khi người dùng bật và nhập khoá. Mặc định ứng dụng dùng model trên máy.
- Model: imagen-4.0-upscale-preview, hệ số x2 / x4, ảnh vào tối đa 10 MB, ảnh ra tối đa 17 MP.
- Chỉ có trên Vertex AI (Google Cloud), không có trên Gemini Developer API (AI Studio).
- Imagen là model tạo sinh: có thể thêm chi tiết. Ứng dụng đặt image_preservation_factor cao và
  sau đó vẫn chạy bước "bám ảnh gốc" như với model trên máy để kéo kết quả về khớp ảnh gốc.
"""
from __future__ import annotations

import io

import numpy as np
from PIL import Image

MODEL_ID = "imagen-4.0-upscale-preview"
MAX_INPUT_BYTES = 10 * 1024 * 1024
MAX_OUTPUT_PIXELS = 17_000_000


def _client(cfg: dict):
    from google import genai

    mode = cfg.get("auth", "api_key")
    if mode == "service_account":
        from google.oauth2 import service_account

        creds = service_account.Credentials.from_service_account_file(
            cfg["service_account_file"], scopes=["https://www.googleapis.com/auth/cloud-platform"])
        project = cfg.get("project") or creds.project_id
        return genai.Client(vertexai=True, project=project, location=cfg.get("location") or "us-central1",
                            credentials=creds)
    if not cfg.get("api_key"):
        raise ValueError("Chưa nhập khoá API Google Cloud (Vertex AI) trong Cài đặt.")
    return genai.Client(vertexai=True, api_key=cfg["api_key"])


def pick_factor(w: int, h: int, need: float) -> str | None:
    """Chọn x2/x4 nhỏ nhất đạt kích thước cần, không vượt giới hạn 17 MP; None nếu x2 đã vượt."""
    for f, name in ((2, "x2"), (4, "x4")):
        if w * h * f * f > MAX_OUTPUT_PIXELS:
            return None if f == 2 else "x2"
        if f >= need:
            return name
    return "x4"


def upscale(rgb: np.ndarray, factor: str, cfg: dict) -> np.ndarray:
    from google.genai import types

    im = Image.fromarray(np.round(np.clip(rgb, 0, 1) * 255).astype(np.uint8), "RGB")
    buf = io.BytesIO()
    im.save(buf, "PNG")
    data, mime = buf.getvalue(), "image/png"
    if len(data) > MAX_INPUT_BYTES:
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=97, subsampling=0)
        data, mime = buf.getvalue(), "image/jpeg"
        if len(data) > MAX_INPUT_BYTES:
            raise ValueError("Ảnh vào lớn hơn giới hạn 10 MB của Google Imagen Upscale.")

    client = _client(cfg)
    resp = client.models.upscale_image(
        model=MODEL_ID,
        image=types.Image(image_bytes=data, mime_type=mime),
        upscale_factor=factor,
        config=types.UpscaleImageConfig(
            output_mime_type="image/png",
            enhance_input_image=bool(cfg.get("enhance_input", True)),
            image_preservation_factor=float(cfg.get("preservation", 0.9)),
            include_rai_reason=True,
        ),
    )
    imgs = resp.generated_images or []
    if not imgs or imgs[0].image is None or not imgs[0].image.image_bytes:
        reason = imgs[0].rai_filtered_reason if imgs else None
        raise RuntimeError("Google không trả về ảnh" + (f": {reason}" if reason else "."))
    out = Image.open(io.BytesIO(imgs[0].image.image_bytes)).convert("RGB")
    return np.asarray(out, dtype=np.float32) / 255.0


def test_connection(cfg: dict) -> str:
    """Gửi 1 ảnh 64x64 để kiểm tra khoá. Lưu ý: lệnh này có thể bị tính phí 1 ảnh."""
    rgb = np.full((64, 64, 3), 0.5, np.float32)
    rgb[16:48, 16:48] = (0.49, 0.75, 0.32)
    out = upscale(rgb, "x2", cfg)
    return f"Kết nối thành công: Google trả về ảnh {out.shape[1]}×{out.shape[0]} px."
