"""Đọc / ghi ảnh, giữ nguyên giá trị điểm ảnh, profile màu và kênh trong suốt."""
from __future__ import annotations

import base64
import io
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image, ImageCms, ImageOps

Image.MAX_IMAGE_PIXELS = 400_000_000  # cho phép đọc ảnh rất lớn (ảnh 8K ~ 33 MP)

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}


@dataclass
class SourceImage:
    path: Path
    rgb: np.ndarray                 # HxWx3 float32 0..1
    alpha: np.ndarray | None        # HxW float32 0..1, None nếu ảnh không có vùng trong suốt
    icc: bytes | None               # profile màu gốc, nhúng lại vào ảnh kết quả
    grayscale: bool
    high_bit: bool                  # ảnh gốc 16-bit: xuất PNG/TIFF 16-bit
    file_format: str
    notes: list[str] = field(default_factory=list)

    @property
    def width(self) -> int:
        return self.rgb.shape[1]

    @property
    def height(self) -> int:
        return self.rgb.shape[0]


def load_image(path: str | Path) -> SourceImage:
    path = Path(path)
    im = Image.open(path)
    fmt = im.format or path.suffix.lstrip(".").upper()
    if getattr(im, "n_frames", 1) > 1:
        im.seek(0)
    im.load()
    notes: list[str] = []
    icc = im.info.get("icc_profile")

    transposed = ImageOps.exif_transpose(im)
    if transposed is not im:
        im = transposed

    if im.mode == "CMYK":
        if icc:
            src = ImageCms.ImageCmsProfile(io.BytesIO(icc))
            im = ImageCms.profileToProfile(im, src, ImageCms.createProfile("sRGB"), outputMode="RGB")
        else:
            im = im.convert("RGB")
        icc = None
        notes.append("Ảnh CMYK đã được chuyển sang sRGB.")
    if im.mode == "P":
        im = im.convert("RGBA" if "transparency" in im.info else "RGB")
    if im.mode == "1":
        im = im.convert("L")

    grayscale = im.mode in ("L", "LA", "I", "I;16", "I;16B", "I;16L", "F")
    high_bit = im.mode in ("I", "I;16", "I;16B", "I;16L")

    alpha = None
    if im.mode in ("RGBA", "LA", "PA") or (im.mode in ("RGB", "L") and "transparency" in im.info):
        a = np.asarray(im.convert("RGBA").getchannel("A"), dtype=np.float32) / 255.0
        if a.min() < 1.0:
            alpha = a

    if high_bit:
        g = np.asarray(im, dtype=np.float32)
        g = g / (65535.0 if g.max() > 255 else 255.0)
        rgb = np.repeat(g[..., None], 3, axis=2)
        notes.append("Ảnh xám 16-bit: xử lý ở độ chính xác cao và xuất 16-bit.")
    elif im.mode == "F":
        g = np.clip(np.asarray(im, dtype=np.float32), 0, 1)
        rgb = np.repeat(g[..., None], 3, axis=2)
    elif im.mode in ("RGB;16", "RGBA;16"):
        rgb = np.asarray(im.convert("RGB"), dtype=np.float32) / 255.0
    else:
        rgb = np.asarray(im.convert("RGB"), dtype=np.float32) / 255.0

    return SourceImage(path, np.ascontiguousarray(rgb), alpha, icc, grayscale, high_bit, fmt, notes)


def to_pil(rgb: np.ndarray, alpha: np.ndarray | None, grayscale: bool, high_bit: bool) -> Image.Image:
    """Lượng tử hoá một lần duy nhất ở bước cuối (làm tròn, không cắt bớt)."""
    rgb = np.clip(rgb, 0, 1)
    if grayscale:
        g = rgb.mean(axis=2)
        if high_bit:
            return Image.fromarray(np.round(g * 65535).astype(np.uint16), "I;16")
        im = Image.fromarray(np.round(g * 255).astype(np.uint8), "L")
        if alpha is not None:
            im = Image.merge("LA", [im, Image.fromarray(np.round(np.clip(alpha, 0, 1) * 255).astype(np.uint8), "L")])
        return im
    im = Image.fromarray(np.round(rgb * 255).astype(np.uint8), "RGB")
    if alpha is not None:
        im.putalpha(Image.fromarray(np.round(np.clip(alpha, 0, 1) * 255).astype(np.uint8), "L"))
    return im


def save_image(im: Image.Image, path: Path, fmt: str, icc: bytes | None, jpeg_quality: int = 95) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    kw: dict = {}
    if icc:
        kw["icc_profile"] = icc
    fmt = fmt.upper()
    if fmt == "JPG":
        if im.mode in ("RGBA", "LA"):
            # JPG không có kênh trong suốt: ghép lên nền trắng
            bg = Image.new("RGB", im.size, (255, 255, 255))
            bg.paste(im.convert("RGBA"), mask=im.convert("RGBA").getchannel("A"))
            im = bg
        if im.mode == "I;16":
            im = Image.fromarray((np.asarray(im, dtype=np.float32) / 257.0).round().astype(np.uint8), "L")
        im.save(path, "JPEG", quality=jpeg_quality, subsampling=0, optimize=True, **kw)
    elif fmt == "TIFF":
        im.save(path, "TIFF", compression="tiff_lzw", **kw)
    else:
        im.save(path, "PNG", compress_level=6, **kw)
    return path


def preview_data_url(rgb: np.ndarray, max_side: int = 4096, quality: int = 90) -> str:
    """Ảnh xem trước (JPEG base64) gửi sang giao diện; không dùng để lưu kết quả."""
    im = Image.fromarray(np.round(np.clip(rgb, 0, 1) * 255).astype(np.uint8), "RGB")
    if max(im.size) > max_side:
        s = max_side / max(im.size)
        im = im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=quality, subsampling=0)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def crop_data_url(rgb: np.ndarray) -> str:
    """Vùng cắt xem 1:1, PNG để không thêm nhiễu nén vào phần so sánh chi tiết."""
    im = Image.fromarray(np.round(np.clip(rgb, 0, 1) * 255).astype(np.uint8), "RGB")
    buf = io.BytesIO()
    im.save(buf, "PNG", compress_level=1)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
