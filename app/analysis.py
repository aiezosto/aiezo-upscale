"""Đo đạc ảnh: độ phân giải thực (ảnh đã bị phóng mờ trước đó), độ khớp và độ nét."""
from __future__ import annotations

import math

import torch
import torch.nn.functional as F

LUMA = torch.tensor([0.2126, 0.7152, 0.0722]).view(1, 3, 1, 1)


def luma(x: torch.Tensor) -> torch.Tensor:
    return (x * LUMA.to(x.device, x.dtype)).sum(1, keepdim=True)


def resize(x: torch.Tensor, size_hw: tuple[int, int]) -> torch.Tensor:
    """Bicubic; khi thu nhỏ có chống răng cưa (antialias) để không sinh nhiễu giả."""
    h, w = size_hw
    if x.shape[-2:] == (h, w):
        return x
    down = h < x.shape[-2] or w < x.shape[-1]
    return F.interpolate(x, size=(h, w), mode="bicubic", align_corners=False, antialias=down)


def gaussian_kernel(sigma: float) -> torch.Tensor:
    r = max(1, math.ceil(sigma * 3))
    t = torch.arange(-r, r + 1, dtype=torch.float32)
    g = torch.exp(-(t ** 2) / (2 * sigma * sigma))
    return g / g.sum()


def gaussian_blur(x: torch.Tensor, sigma: float) -> torch.Tensor:
    if sigma <= 0:
        return x
    g = gaussian_kernel(sigma).to(x.device, x.dtype)
    c = x.shape[1]
    r = (len(g) - 1) // 2
    xp = F.pad(x, (r, r, r, r), mode="replicate")
    xp = F.conv2d(xp, g.view(1, 1, 1, -1).repeat(c, 1, 1, 1), groups=c)
    return F.conv2d(xp, g.view(1, 1, -1, 1).repeat(c, 1, 1, 1), groups=c)


# ------------------------------------------------------------- độ phân giải thực

def _analysis_crop(y: torch.Tensor, max_side: int = 2048) -> torch.Tensor:
    """Phân tích trên vùng giữa ảnh (tối đa 2048 px) để nhanh; không thu nhỏ vì cần giữ tần số gốc."""
    _, _, h, w = y.shape
    ch, cw = min(h, max_side), min(w, max_side)
    t, l = (h - ch) // 2, (w - cw) // 2
    return y[:, :, t:t + ch, l:l + cw]


ROUNDTRIP_THRESHOLD = 0.06


@torch.inference_mode()
def estimate_effective_scale(rgb: torch.Tensor) -> tuple[float, dict]:
    """Ước lượng ảnh thực chất chứa chi tiết tới tỉ lệ s bao nhiêu so với kích thước hiện tại.

    Thu ảnh về tỉ lệ s rồi phóng lại: nếu ảnh vốn đã bị phóng nhoè từ ảnh nhỏ hơn thì gần như
    không mất gì. R(s) = năng lượng mất ở tỉ lệ s / năng lượng mất ở tỉ lệ 0.25. Lấy s nhỏ nhất
    mà R(s) còn dưới ngưỡng 0.06 (ngưỡng chọn từ thử nghiệm có đáp án trên ảnh mẫu; sai số
    nghiêng về phía an toàn: ước lượng cao hơn thực tế, không bao giờ bỏ chi tiết thật).
    """
    y = _analysis_crop(luma(rgb))
    h, w = y.shape[-2:]
    loss = {}
    for i in range(19, 4, -1):
        s = i / 20
        r = resize(resize(y, (max(8, round(h * s)), max(8, round(w * s)))), (h, w))
        loss[s] = float(((y - r) ** 2).mean())
    base = loss[0.25] or 1e-12
    est = 1.0
    for i in range(19, 4, -1):
        s = i / 20
        if loss[s] / base > ROUNDTRIP_THRESHOLD:
            break
        est = s
    return est, {"r95": loss[0.95] / base}


# ------------------------------------------------------------- khử bạc màu & làm nét

@torch.inference_mode()
def levels_range(rgb: torch.Tensor) -> tuple[float, float]:
    """Điểm đen / điểm trắng (phân vị 0.5 % / 99.5 % kênh sáng) đo trên vùng giữa ảnh.

    Bỏ 10 % trên/dưới và 5 % trái/phải để thanh trạng thái điện thoại, viền đen... không làm sai số đo.
    """
    _, _, h, w = rgb.shape
    y = luma(rgb[:, :, int(h * 0.1):max(int(h * 0.9), int(h * 0.1) + 1),
                 int(w * 0.05):max(int(w * 0.95), int(w * 0.05) + 1)]).flatten().float()
    if y.numel() > 4_000_000:
        y = y[:: y.numel() // 4_000_000 + 1]
    lo, hi = torch.quantile(y, torch.tensor([0.005, 0.995], device=y.device)).tolist()
    return lo, hi


@torch.inference_mode()
def richardson_lucy(rgb: torch.Tensor, sigma: float, iters: int, tol: float = 0.01) -> torch.Tensor:
    """Giải chập Richardson–Lucy với PSF Gauss trên kênh sáng; cộng phần chênh vào cả 3 kênh.

    Sau đó kẹp kênh sáng trong [min - tol, max + tol] của vùng lân cận bán kính ~1.5σ để chặn
    viền sáng/tối (ringing) quanh cạnh.
    """
    y = luma(rgb)
    u = y.clone()
    for _ in range(iters):
        est = gaussian_blur(u, sigma).clamp(min=1e-4)
        u = u * gaussian_blur(y / est, sigma)
    r = max(1, round(sigma * 1.5))
    mx = F.max_pool2d(F.pad(y, (r, r, r, r), mode="replicate"), 2 * r + 1, 1)
    mn = -F.max_pool2d(F.pad(-y, (r, r, r, r), mode="replicate"), 2 * r + 1, 1)
    u = torch.minimum(torch.maximum(u, mn - tol), mx + tol)
    return (rgb + (u - y)).clamp_(0, 1)


# ------------------------------------------------------------- độ khớp & độ nét

@torch.inference_mode()
def psnr(a: torch.Tensor, b: torch.Tensor) -> float:
    mse = F.mse_loss(a.float(), b.float()).item()
    return float("inf") if mse <= 1e-12 else 10 * math.log10(1.0 / mse)


@torch.inference_mode()
def ssim(a: torch.Tensor, b: torch.Tensor) -> float:
    """SSIM chuẩn (Gauss 11, sigma 1.5) trên kênh sáng."""
    x, y = luma(a.float()), luma(b.float())
    C1, C2 = 0.01 ** 2, 0.03 ** 2
    g = gaussian_kernel(1.5).to(x.device)
    if len(g) != 11:
        g = g[(len(g) - 11) // 2:(len(g) + 11) // 2]
        g = g / g.sum()

    def blur(t):
        t = F.conv2d(t, g.view(1, 1, 1, -1))
        return F.conv2d(t, g.view(1, 1, -1, 1))

    mx, my = blur(x), blur(y)
    sxx = blur(x * x) - mx * mx
    syy = blur(y * y) - my * my
    sxy = blur(x * y) - mx * my
    m = ((2 * mx * my + C1) * (2 * sxy + C2)) / ((mx * mx + my * my + C1) * (sxx + syy + C2))
    return float(m.mean())


@torch.inference_mode()
def edge_energy(x: torch.Tensor) -> float:
    """Độ nét = trung bình độ lớn gradient (Sobel) của kênh sáng, tính theo thang 0..1 mỗi px."""
    y = luma(x.float())
    kx = torch.tensor([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], dtype=torch.float32, device=y.device) / 8
    gx = F.conv2d(y, kx.view(1, 1, 3, 3))
    gy = F.conv2d(y, kx.t().contiguous().view(1, 1, 3, 3))
    return float(torch.sqrt(gx * gx + gy * gy).mean())
