"""Danh mục model AI chạy trên máy và chạy model theo từng ô (tile) để không thiếu bộ nhớ GPU."""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable

import torch
import torch.nn.functional as F

from .paths import MODELS_DIR


@dataclass(frozen=True)
class ModelInfo:
    key: str
    file: str
    label: str
    description: str
    tile: int          # cạnh ô (px ảnh vào) mặc định cho GPU 12 GB
    license: str
    source: str


# Mặc định dùng model huấn luyện theo hướng trung thực (PSNR / L1). Model GAN ("detail") chỉ là lựa
# chọn có gắn nhãn: nó tự vẽ thêm kết cấu không có trong ảnh gốc. Không dùng model khôi phục khuôn mặt.
MODELS: dict[str, ModelInfo] = {}


def _register(m: ModelInfo) -> None:
    MODELS[m.key] = m


# Thứ tự và lựa chọn dựa trên thử nghiệm có đáp án (ảnh nét → làm hỏng → khôi phục → so với ảnh nét):
# Real-ESRNet khớp ảnh thật tốt nhất với ảnh vỡ/nhoè; model GAN (DAT2 RealWebPhoto) nét hơn nhưng
# lệch ảnh thật nhiều hơn cả phóng bicubic nên bị loại.
_register(ModelInfo(
    "restore", "RealESRNet_x4plus.pth", "Real-ESRNet",
    "Ảnh vỡ, nhoè, nén, ảnh chụp màn hình, ảnh mạng xã hội. Khử vỡ và làm nét, không GAN.",
    384, "BSD-3-Clause", "github.com/xinntao/Real-ESRGAN"))
_register(ModelInfo(
    "restore_alt", "003_realSR_BSRGAN_DFO_s64w8_SwinIR-M_x4_PSNR.pth", "SwinIR Real-SR",
    "Phương án đối chiếu cho ảnh vỡ/nhoè (kiến trúc khác, cũng không GAN). Dùng khi muốn so sánh.",
    256, "Apache-2.0", "github.com/JingyunLiang/SwinIR"))
_register(ModelInfo(
    "detail", "RealESRGAN_x4plus.pth", "Real-ESRGAN (tái tạo chi tiết – có vẽ thêm)",
    "Model GAN: nét như Remini/Topaz/Upscayl nhưng TỰ VẼ THÊM vân vải, tóc, sạn… không có trong ảnh gốc. "
    "Bước Bám ảnh gốc vẫn giữ đúng hình khối và màu.",
    384, "BSD-3-Clause", "github.com/xinntao/Real-ESRGAN"))
_register(ModelInfo(
    "faithful", "HAT-L_SRx4_ImageNet-pretrain.safetensors", "HAT-L",
    "Ảnh đã rõ, sạch nhưng nhỏ. Phóng sát ảnh gốc nhất, không khử nhiễu nén. Chậm hơn.",
    256, "MIT", "github.com/XPixelGroup/HAT"))


class Cancelled(Exception):
    pass


ProgressFn = Callable[[float, str], None]


def pick_device() -> torch.device:
    return torch.device("cuda") if torch.cuda.is_available() else torch.device("cpu")


def device_info(device: torch.device) -> dict:
    if device.type == "cuda":
        p = torch.cuda.get_device_properties(device)
        return {"type": "cuda", "name": p.name, "vram_gb": round(p.total_memory / 1024**3, 1),
                "label": f"{p.name} · {p.total_memory / 1024**3:.0f} GB"}
    return {"type": "cpu", "name": "CPU", "vram_gb": 0, "label": "CPU (không có GPU NVIDIA, chạy chậm)"}


class ModelManager:
    """Nạp model khi cần, giữ tối đa 1 model trong VRAM."""

    def __init__(self, device: torch.device):
        self.device = device
        self._key: str | None = None
        self._model = None
        self._lock = threading.Lock()

    def available(self) -> list[ModelInfo]:
        return [m for m in MODELS.values() if (MODELS_DIR / m.file).exists()]

    def get(self, key: str):
        from spandrel import ModelLoader

        with self._lock:
            if self._key == key:
                return self._model
            info = MODELS[key]
            path = MODELS_DIR / info.file
            if not path.exists():
                raise FileNotFoundError(f"Thiếu file model: {path.name}")
            self.unload()
            desc = ModelLoader(device=self.device).load_from_file(path)
            if desc.scale != 4:
                raise ValueError(f"Model {info.file} có hệ số x{desc.scale}, ứng dụng cần model x4")
            desc.eval()
            self._model, self._key = desc, key
            return desc

    def unload(self) -> None:
        self._model, self._key = None, None
        if self.device.type == "cuda":
            torch.cuda.empty_cache()


def _starts(length: int, tile: int, overlap: int) -> list[int]:
    if length <= tile:
        return [0]
    step = tile - overlap
    s = list(range(0, length - tile, step))
    s.append(length - tile)
    return s


def _ramp(n: int, ov: int, first: bool, last: bool) -> torch.Tensor:
    w = torch.ones(n)
    if ov > 0:
        r = (torch.arange(ov, dtype=torch.float32) + 0.5) / ov
        if not first:
            w[:ov] = torch.minimum(w[:ov], r)
        if not last:
            w[-ov:] = torch.minimum(w[-ov:], r.flip(0))
    return w


@torch.inference_mode()
def run_x4(desc, img: torch.Tensor, tile: int, progress: ProgressFn | None = None,
           cancel: threading.Event | None = None, label: str = "") -> torch.Tensor:
    """img: 1x3xHxW float32 (0..1) trên CPU. Trả về 1x3x4Hx4W trên CPU.

    Ảnh được đệm phản chiếu 16 px để mép ảnh không bị méo; các ô chồng nhau và được trộn
    bằng trọng số tuyến tính nên không có đường nối giữa các ô.
    """
    device = next(desc.model.parameters()).device
    pad = 16
    _, _, h, w = img.shape
    mode = "reflect" if min(h, w) > pad else "replicate"
    x = F.pad(img, (pad, pad, pad, pad), mode=mode)
    H, W = x.shape[-2:]

    while True:
        try:
            out = _tiles(desc, x, H, W, tile, device, progress, cancel, label)
            break
        except torch.cuda.OutOfMemoryError:
            torch.cuda.empty_cache()
            if tile <= 64:
                raise RuntimeError("Không đủ bộ nhớ GPU ngay cả với ô 64 px.")
            tile //= 2
            if progress:
                progress(0.0, f"{label}Thiếu VRAM, giảm ô xuống {tile} px và chạy lại")
    return out[:, :, pad * 4:(pad + h) * 4, pad * 4:(pad + w) * 4]


def _tiles(desc, x, H, W, tile, device, progress, cancel, label) -> torch.Tensor:
    ov = min(32, tile // 4)
    ys, xs = _starts(H, tile, ov), _starts(W, tile, ov)
    out = torch.zeros(1, 3, H * 4, W * 4)
    wsum_y = torch.zeros(H * 4)
    wsum_x = torch.zeros(W * 4)
    wy = [_ramp(min(tile, H - y) * 4, ov * 4, y == 0, y + tile >= H) for y in ys]
    wx = [_ramp(min(tile, W - x0) * 4, ov * 4, x0 == 0, x0 + tile >= W) for x0 in xs]
    for y, r in zip(ys, wy):
        wsum_y[y * 4:y * 4 + len(r)] += r
    for x0, r in zip(xs, wx):
        wsum_x[x0 * 4:x0 * 4 + len(r)] += r

    total, done, t0 = len(ys) * len(xs), 0, time.time()
    for y, ry in zip(ys, wy):
        for x0, rx in zip(xs, wx):
            if cancel is not None and cancel.is_set():
                raise Cancelled()
            th, tw = min(tile, H - y), min(tile, W - x0)
            patch = x[:, :, y:y + th, x0:x0 + tw].to(device)
            res = desc(patch).float().clamp_(0, 1).cpu()
            res *= (ry[:, None] * rx[None, :])
            out[:, :, y * 4:(y + th) * 4, x0 * 4:(x0 + tw) * 4] += res
            done += 1
            if progress:
                el = time.time() - t0
                eta = el / done * (total - done)
                progress(done / total, f"{label}ô {done}/{total} · còn khoảng {fmt_secs(eta)}")
    out /= wsum_y[None, None, :, None]
    out /= wsum_x[None, None, None, :]
    return out


def fmt_secs(s: float) -> str:
    s = int(round(s))
    return f"{s // 60} phút {s % 60:02d} giây" if s >= 60 else f"{s} giây"
