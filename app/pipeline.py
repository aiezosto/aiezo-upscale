"""Quy trình làm nét + phóng to.

1. Đo độ phân giải thực: ảnh đã bị phóng nhoè trước đó (ảnh chụp màn hình, ảnh tải lại nhiều lần)
   chỉ chứa chi tiết tới một kích thước nhỏ hơn. Kích thước này là chuẩn để bám ảnh gốc và đo độ khớp.
2. Model AI trên máy (x4, không GAN) chạy trên toàn bộ điểm ảnh gốc, tái tạo cạnh sắc và khử nhiễu
   nén. Cần hơn x4 thì chạy lượt 2 bằng model trung thực HAT-L trên ảnh đã sạch.
3. Thu/phóng về đúng kích thước đích (2K / 4K / 8K theo cạnh dài).
4. Bám ảnh gốc (back-projection): thu kết quả về kích thước thực, so với ảnh gốc, bù phần chênh
   lệch tần số thấp. Kết quả luôn khớp với ảnh gốc về hình khối, màu và vị trí: AI không thể
   thêm vật thể hay đổi màu.
5. Tăng nét không viền sáng (tuỳ chọn) và tăng tương phản (tuỳ chọn, mặc định tắt).
6. Đo độ khớp (PSNR / SSIM so với ảnh gốc) và độ nét (năng lượng biên) để người dùng kiểm chứng.
"""
from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

from . import analysis as A
from . import google_engine
from .imaging import SourceImage, crop_data_url, preview_data_url, save_image, to_pil
from .models import MODELS, Cancelled, ModelManager, ProgressFn, fmt_secs, run_x4

TARGETS = {"2K": 2560, "4K": 3840, "8K": 7680}
FAITHFUL_MODEL = "faithful"
SEEDVR2_MAX_PIXELS = 9_500_000  # đo trên RTX 3060 12 GB


def seedvr2_max_pixels() -> int:
    if not torch.cuda.is_available():
        return SEEDVR2_MAX_PIXELS
    vram = torch.cuda.get_device_properties(0).total_memory / 1024 ** 3
    return int(SEEDVR2_MAX_PIXELS * min(1.0, vram / 12.0))


@dataclass
class Settings:
    target: str = "4K"              # 2K | 4K | 8K | x2 | x4 | custom
    custom_long: int = 3840
    model: str = "restore"          # model cổ điển khi engine = local
    engine: str = "seedvr2"         # seedvr2 (trên máy) | fal (SeedVR2 qua API) | local (model cổ điển) | google
    seedvr2: str = "7b_sharp"       # 3b | 7b_sharp
    fidelity: float = 0.5           # 0..1 mức bám ảnh gốc (0.5 cho PSNR tốt nhất khi thử có đáp án)
    sharpen: float = 0.5            # 0..1 làm nét (giải chập); 0.5 = 15 vòng, mức thử nghiệm cho ảnh rõ nhất không viền
    contrast: bool = False
    out_format: str = "PNG"         # PNG | JPG | TIFF
    jpeg_quality: int = 95
    out_dir: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "Settings":
        s = cls()
        for k, v in d.items():
            if hasattr(s, k):
                setattr(s, k, v)
        s.fidelity = float(min(1, max(0, s.fidelity)))
        s.sharpen = float(min(1, max(0, s.sharpen)))
        return s


def target_size(w: int, h: int, s: Settings) -> tuple[int, int]:
    """(rộng, cao) đích, giữ đúng tỉ lệ ảnh gốc."""
    if s.target in TARGETS:
        long_side = TARGETS[s.target]
    elif s.target == "x2":
        long_side = max(w, h) * 2
    elif s.target == "x4":
        long_side = max(w, h) * 4
    else:
        long_side = int(min(16384, max(64, s.custom_long)))
    # Làm tròn nửa lên (giống Math.round ở giao diện) để kích thước hiện trước khi chạy khớp kết quả
    if w >= h:
        return long_side, max(1, int(h * long_side / w + 0.5))
    return max(1, int(w * long_side / h + 0.5)), long_side


@dataclass
class Restored:
    """Kết quả bước AI (tốn thời gian), giữ lại để chỉnh tinh chỉnh mà không phải chạy lại AI."""
    key: tuple
    sr: torch.Tensor          # 1x3xHxW kích thước đích, CPU
    ref: torch.Tensor         # ảnh gốc ở độ phân giải thực, CPU
    effective: float
    effective_auto: float
    steps: list[str]
    seconds: float


@dataclass
class Result:
    out_rgb: np.ndarray
    out_alpha: np.ndarray | None
    width: int
    height: int
    report: dict
    notes: list[str] = field(default_factory=list)


class Pipeline:
    def __init__(self, manager: ModelManager):
        self.mm = manager
        self.device = manager.device
        self._cache: Restored | None = None
        self.last_src: SourceImage | None = None
        self.last_result: Result | None = None
        self._auto_scale: dict[str, tuple[float, dict]] = {}

    # ------------------------------------------------------------- phân tích ảnh vào

    def analyze(self, src: SourceImage) -> dict:
        key = str(src.path)
        if key not in self._auto_scale:
            x = torch.from_numpy(src.rgb).permute(2, 0, 1)[None].to(self.device)
            scale, info = A.estimate_effective_scale(x)
            info["range"] = A.levels_range(x)
            self._auto_scale[key] = (scale, info)
            del x
        scale, info = self._auto_scale[key]
        lo, hi = info["range"]
        return {"effective": scale, "effective_w": round(src.width * scale), "effective_h": round(src.height * scale),
                "luma_lo": round(lo, 3), "luma_hi": round(hi, 3),
                # Ảnh bạc màu / mờ sương = điểm đen bị nâng (vùng tối nhất vẫn xám). Ảnh chỉ thiếu vùng
                # trắng (như cảnh tối) không phải bạc màu, không tự bật.
                "suggest_contrast": lo > 0.06}

    # ------------------------------------------------------------- bước AI

    def cache_key(self, src: SourceImage, s: Settings, google_cfg: dict | None) -> tuple:
        tw, th = target_size(src.width, src.height, s)
        eff = self.analyze(src)["effective"]
        model_id = {"local": s.model, "seedvr2": s.seedvr2, "fal": "fal-seedvr2"}.get(s.engine, "")
        return (str(src.path), model_id, s.engine, round(eff, 3), tw, th,
                google_cfg.get("preservation") if (s.engine == "google" and google_cfg) else None)

    def is_cached(self, src: SourceImage, s: Settings, google_cfg: dict | None) -> bool:
        """True nếu bước AI đã có sẵn (chỉ đổi tinh chỉnh) — không tốn lượt."""
        return self._cache is not None and self._cache.key == self.cache_key(src, s, google_cfg)

    def restore(self, src: SourceImage, s: Settings, google_cfg: dict | None,
                progress: ProgressFn, cancel: threading.Event, fal_key: str = "") -> Restored:
        t0 = time.time()
        W, H = src.width, src.height
        tw, th = target_size(W, H, s)
        auto = self.analyze(src)["effective"]
        eff = auto
        key = self.cache_key(src, s, google_cfg)
        if self._cache is not None and self._cache.key == key:
            return self._cache
        self._cache = None

        steps: list[str] = []
        x = torch.from_numpy(src.rgb).permute(2, 0, 1)[None].contiguous()
        bw, bh = max(16, round(W * eff)), max(16, round(H * eff))
        if (bw, bh) != (W, H):
            ref = A.resize(x, (bh, bw)).clamp(0, 1)
            steps.append(f"Ảnh gốc thực chất chỉ chứa chi tiết tới khoảng {bw}×{bh} px "
                         f"({eff * 100:.0f}% kích thước file), phần còn lại là nhoè do bị phóng trước đó")
        else:
            ref = x
        need = max(tw / W, th / H)

        if s.engine == "google":
            sr = self._google(x, need, (th, tw), google_cfg or {}, steps, progress)
        elif s.engine == "seedvr2":
            sr = self._seedvr2(x, (th, tw), s.seedvr2, steps, progress, cancel)
        elif s.engine == "fal":
            sr = self._fal(x, need, (th, tw), fal_key, steps, progress, cancel)
        else:
            sr = self._local(x, need, (th, tw), s.model, steps, progress, cancel)

        r = Restored(key, sr, ref, eff, auto, steps, time.time() - t0)
        self._cache = r
        return r

    def _local(self, img, need, size_hw, model_key, steps, progress, cancel) -> torch.Tensor:
        th, tw = size_hw
        info = MODELS[model_key]
        two_pass = need > 4
        span = 0.5 if two_pass else 1.0

        def p1(f, msg):
            progress(0.02 + 0.9 * span * f, f"Lượt 1 · {info.label}: {msg}")

        desc = self.mm.get(model_key)
        progress(0.02, f"Lượt 1 · {info.label}: đang chạy")
        out = run_x4(desc, img, info.tile, p1, cancel)
        steps.append(f"Lượt 1: {info.label} x4 → {out.shape[-1]}×{out.shape[-2]} px")

        if two_pass:
            # Lượt 2 trên ảnh đã sạch: thu về đúng 1/4 kích thước đích rồi chạy model trung thực.
            mid = (math.ceil(th / 4), math.ceil(tw / 4))
            out = A.resize(out, mid).clamp(0, 1)
            fi = MODELS[FAITHFUL_MODEL]
            desc = self.mm.get(FAITHFUL_MODEL)

            def p2(f, msg):
                progress(0.47 + 0.45 * f, f"Lượt 2 · {fi.label}: {msg}")

            out = run_x4(desc, out, fi.tile, p2, cancel)
            steps.append(f"Lượt 2: {fi.label} x4 trên ảnh {mid[1]}×{mid[0]} px → {out.shape[-1]}×{out.shape[-2]} px")
            if need > 16:
                steps.append(f"Cần phóng x{need:.1f} > x16: phần vượt chỉ là nội suy bicubic, không thêm chi tiết.")

        if out.shape[-2:] != (th, tw):
            verb = "Thu nhỏ" if out.shape[-1] > tw else "Phóng"
            out = A.resize(out, (th, tw)).clamp(0, 1)
            steps.append(f"{verb} về kích thước đích {tw}×{th} px (bicubic chống răng cưa)")
        return out

    def _seedvr2(self, img, size_hw, variant, steps, progress, cancel) -> torch.Tensor:
        from . import seedvr2_engine as SV

        th, tw = size_hw
        v = SV.VARIANTS[variant]
        rgb = img[0].permute(1, 2, 0).numpy()
        self.mm.unload()  # trả VRAM cho tiến trình SeedVR2
        if not torch.cuda.is_available():
            raise RuntimeError("SeedVR2 cần card đồ hoạ NVIDIA. Máy này không có: hãy chọn bộ xử lý “Cổ điển” "
                               "hoặc “SeedVR2 API” (fal.ai).")
        # GPU 12 GB chạy được SeedVR2 tới ~9.5 MP ảnh ra (thử: 4008×2256 chạy được, 7674×4320 hết VRAM).
        # Card ít VRAM hơn: giảm giới hạn theo tỉ lệ (ước lượng, chưa thử trên card khác RTX 3060 12 GB).
        limit = seedvr2_max_pixels()
        if th * tw <= limit:
            out = SV.run(rgb, min(th, tw), variant, lambda f, m: progress(0.02 + 0.9 * f, m), cancel)
            steps.append(f"{v.label} (diffusion, trên máy) → {out.shape[1]}×{out.shape[0]} px")
            t = torch.from_numpy(out).permute(2, 0, 1)[None].contiguous()
        else:
            s = math.sqrt(limit / (th * tw))
            mh, mw = int(th * s), int(tw * s)
            out = SV.run(rgb, min(mh, mw), variant, lambda f, m: progress(0.02 + 0.6 * f, m), cancel)
            steps.append(f"{v.label} (diffusion, trên máy) → {out.shape[1]}×{out.shape[0]} px "
                         f"(giới hạn bộ nhớ GPU 12 GB)")
            t = torch.from_numpy(out).permute(2, 0, 1)[None].contiguous()
            info = MODELS["restore"]
            desc = self.mm.get("restore")
            t = run_x4(desc, t, info.tile, lambda f, m: progress(0.62 + 0.3 * f, f"Phóng tiếp lên đích · {info.label}: {m}"),
                       cancel)
            self.mm.unload()
            steps.append(f"Phóng tiếp bằng {info.label} x4 trên ảnh đã sạch → {t.shape[-1]}×{t.shape[-2]} px")
        if t.shape[-2:] != (th, tw):
            t = A.resize(t, (th, tw)).clamp(0, 1)
            steps.append(f"Đưa về đúng kích thước đích {tw}×{th} px")
        return t

    def _fal(self, img, need, size_hw, api_key, steps, progress, cancel) -> torch.Tensor:
        from . import fal_engine

        th, tw = size_hw
        rgb = img[0].permute(1, 2, 0).numpy()
        factor = min(10.0, max(1.0, need))
        out = fal_engine.run(rgb, factor, api_key, progress, cancel)
        cost = fal_engine.estimate_cost(out.shape[1], out.shape[0])
        steps.append(f"SeedVR2 trên máy chủ fal.ai x{factor:.2f} → {out.shape[1]}×{out.shape[0]} px "
                     f"(ước tính {cost:.3f} USD)")
        t = torch.from_numpy(out).permute(2, 0, 1)[None].contiguous()
        if t.shape[-2:] != (th, tw):
            t = A.resize(t, (th, tw)).clamp(0, 1)
            steps.append(f"Đưa về đúng kích thước đích {tw}×{th} px")
        return t

    def _google(self, img, need, size_hw, cfg, steps, progress) -> torch.Tensor:
        th, tw = size_hw
        h, w = img.shape[-2:]
        factor = google_engine.pick_factor(w, h, need)
        if factor is None:
            raise ValueError("Ảnh quá lớn cho Google Imagen Upscale (ảnh ra tối đa 17 MP). Hãy dùng chế độ trên máy.")
        progress(0.1, f"Đang gửi ảnh lên Google Imagen Upscale ({factor})…")
        rgb = img[0].permute(1, 2, 0).numpy()
        out = google_engine.upscale(rgb, factor, cfg)
        steps.append(f"Google {google_engine.MODEL_ID} {factor} → {out.shape[1]}×{out.shape[0]} px")
        t = torch.from_numpy(out).permute(2, 0, 1)[None].contiguous()
        if t.shape[-2:] != (th, tw):
            t = A.resize(t, (th, tw)).clamp(0, 1)
            steps.append(f"Đưa về kích thước đích {tw}×{th} px (bicubic)")
        progress(0.92, "Đã nhận ảnh từ Google")
        return t

    # ------------------------------------------------------------- tinh chỉnh (nhanh)

    @torch.inference_mode()
    def finish(self, src: SourceImage, r: Restored, s: Settings) -> Result:
        dev = self.device
        out = r.sr.to(dev)
        ref = r.ref.to(dev)
        th, tw = out.shape[-2:]
        rh, rw = ref.shape[-2:]
        steps = list(r.steps)
        k = tw / rw  # 1 px ở độ phân giải thực = k px ở ảnh kết quả

        # 4. Bám ảnh gốc: chỉ bù chênh lệch tần số thấp (đã làm mờ nhẹ) để không đưa lại nhiễu nén.
        if s.fidelity > 0:
            for _ in range(3):
                d = ref - A.resize(out, (rh, rw))
                d = A.gaussian_blur(d, 1.0)
                out = (out + s.fidelity * A.resize(d, (th, tw))).clamp_(0, 1)
            steps.append(f"Bám ảnh gốc {s.fidelity * 100:.0f}%: kéo hình khối và màu về khớp ảnh gốc")

        # 5a. Khử bạc màu: kéo điểm đen / điểm trắng (đo trên vùng giữa ảnh, bỏ viền như thanh trạng thái
        # điện thoại). Biến đổi tuyến tính, như nhau cho 3 kênh nên không đổi tông màu, không thêm chi tiết.
        lo, hi = 0.0, 1.0
        if s.contrast:
            lo, hi = A.levels_range(ref)
            # Chỉ kéo điểm trắng khi ảnh vốn có vùng gần trắng (≥ 0.9): cảnh tối không bị làm sáng sai
            hi = max(hi, 0.9) if hi >= 0.9 else 1.0
            if hi - lo > 0.05 and (lo > 0.01 or hi < 0.99):
                out = ((out - lo) / (hi - lo)).clamp_(0, 1)
                steps.append(f"Khử bạc màu: kéo dải sáng {lo:.2f}–{hi:.2f} về 0–1")
            else:
                lo, hi = 0.0, 1.0

        # 5b. Làm nét bằng giải chập Richardson–Lucy: khôi phục phần chi tiết bị nhoè từ chính dữ liệu
        # ảnh (không vẽ thêm). Chạy sau bước AI vì AI đã khử nhiễu nén; nếu không, giải chập sẽ khuếch
        # đại ô vuông JPEG. Kẹp theo min/max lân cận để không sinh viền sáng quanh cạnh.
        if s.sharpen > 0:
            # σ = 0.3 px ở độ phân giải thực, quy ra px ảnh kết quả; giới hạn 0.8..1.5 px. Hệ số chọn từ thử
            # nghiệm trên ảnh thật: lớn hơn (σ 1.9, 15 vòng) sinh viền đậm quanh người và cạnh.
            # Thanh trượt tăng cả số vòng lẫn σ (x0.7 ở 0 % → x1.3 ở 100 %); ở 50 % đúng mức đã kiểm chứng.
            sigma = min(1.5, max(0.8, 0.3 * k)) * (0.7 + 0.6 * s.sharpen)
            iters = max(1, round(20 * s.sharpen))
            out = A.richardson_lucy(out, sigma, iters)
            steps.append(f"Làm nét {s.sharpen * 100:.0f}%: giải chập Richardson–Lucy {iters} vòng, "
                         f"độ nhoè σ={sigma:.2f} px (kênh sáng, chặn viền sáng)")

        # Kênh trong suốt: phóng bicubic (không cho AI xử lý alpha)
        alpha = None
        if src.alpha is not None:
            a = torch.from_numpy(src.alpha)[None, None].to(dev)
            alpha = A.resize(a, (th, tw)).clamp(0, 1)[0, 0].cpu().numpy()

        # 6. Đo đạc. Độ khớp: thu kết quả về độ phân giải thực, so với ảnh gốc (đã áp cùng mức khử bạc
        # màu để chỉ đo khác biệt về chi tiết). Độ nét: so với ảnh gốc phóng bicubic (cùng mức khử bạc màu).
        ref_l = ((ref - lo) / (hi - lo)).clamp(0, 1)
        back = A.resize(out, (rh, rw)).clamp(0, 1)
        p, ss = A.psnr(back, ref_l), A.ssim(back, ref_l)
        orig = torch.from_numpy(src.rgb).permute(2, 0, 1)[None].to(dev)
        base_up = ((A.resize(orig, (th, tw)) - lo) / (hi - lo)).clamp(0, 1)
        e_before, e_after = A.edge_energy(base_up), A.edge_energy(out)
        del base_up, orig, back, ref_l

        if p >= 36 and ss >= 0.96:
            level, verdict = "good", "Rất khớp ảnh gốc: hình khối, màu, vị trí giữ nguyên; không có chi tiết lạ."
        elif p >= 30 and ss >= 0.90:
            level, verdict = "ok", ("Khớp tốt: giữ nguyên người, vật, bố cục; sai khác là chi tiết nhỏ do AI tái tạo."
                                    if s.engine in ("seedvr2", "fal", "google")
                                    else "Khớp tốt. Sai khác chủ yếu do đã khử nhiễu nén và làm nét cạnh.")
        else:
            level, verdict = "low", "Độ khớp thấp: nên giảm mức Làm nét hoặc tăng Bám ảnh gốc rồi kiểm tra lại."

        rgb = out[0].permute(1, 2, 0).float().cpu().numpy()
        report = {
            "src_w": src.width, "src_h": src.height, "out_w": tw, "out_h": th,
            "ref_w": rw, "ref_h": rh,
            "effective": r.effective,
            "psnr": round(p, 2) if math.isfinite(p) else 99.0, "ssim": round(ss, 4),
            "sharp_gain": round(e_after / e_before, 2) if e_before > 0 else None,
            "level": level, "verdict": verdict,
            "steps": steps, "ai_seconds": round(r.seconds, 1), "ai_time": fmt_secs(r.seconds),
        }
        res = Result(rgb, alpha, tw, th, report, list(src.notes))
        self.last_src, self.last_result = src, res
        return res

    # ------------------------------------------------------------- xem trước & lưu

    def previews(self, max_side: int = 4096) -> dict:
        src, res = self.last_src, self.last_result
        assert src is not None and res is not None
        s = min(1.0, max_side / max(res.width, res.height))
        pw, ph = max(1, round(res.width * s)), max(1, round(res.height * s))
        orig = torch.from_numpy(src.rgb).permute(2, 0, 1)[None].to(self.device)
        before = A.resize(orig, (ph, pw)).clamp(0, 1)[0].permute(1, 2, 0).cpu().numpy()
        return {"before": preview_data_url(before, max_side), "after": preview_data_url(res.out_rgb, max_side),
                "preview_w": pw, "preview_h": ph}

    def crop(self, cx: float, cy: float, size: int = 420) -> dict:
        """Vùng 1:1 tại (cx, cy) (0..1) của ảnh kết quả, kèm cùng vùng của ảnh gốc phóng bicubic."""
        src, res = self.last_src, self.last_result
        assert src is not None and res is not None
        size = min(size, res.width, res.height)
        x0 = int(min(max(0, cx * res.width - size / 2), res.width - size))
        y0 = int(min(max(0, cy * res.height - size / 2), res.height - size))
        after = res.out_rgb[y0:y0 + size, x0:x0 + size]
        sx, sy = src.width / res.width, src.height / res.height
        orig = torch.from_numpy(src.rgb).permute(2, 0, 1)[None]
        ox0, oy0 = int(x0 * sx), int(y0 * sy)
        ox1, oy1 = min(src.width, math.ceil((x0 + size) * sx) + 1), min(src.height, math.ceil((y0 + size) * sy) + 1)
        region = orig[:, :, oy0:oy1, ox0:ox1]
        up = A.resize(region, (round((oy1 - oy0) / sy), round((ox1 - ox0) / sx))).clamp(0, 1)
        offx, offy = round((x0 * sx - ox0) / sx), round((y0 * sy - oy0) / sy)
        before = up[0, :, offy:offy + size, offx:offx + size].permute(1, 2, 0).numpy()
        return {"before": crop_data_url(before), "after": crop_data_url(after), "x": x0, "y": y0, "size": size}

    def save(self, out_dir: Path, s: Settings) -> Path:
        src, res = self.last_src, self.last_result
        assert src is not None and res is not None
        label = s.target if s.target in TARGETS or s.target in ("x2", "x4") else f"{res.width}px"
        ext = {"PNG": ".png", "JPG": ".jpg", "TIFF": ".tif"}.get(s.out_format.upper(), ".png")
        base = f"{src.path.stem}_{label}_{res.width}x{res.height}"
        path = out_dir / f"{base}{ext}"
        i = 2
        while path.exists():
            path = out_dir / f"{base} ({i}){ext}"
            i += 1
        im = to_pil(res.out_rgb, res.out_alpha, src.grayscale, src.high_bit)
        return save_image(im, path, s.out_format, src.icc, s.jpeg_quality)

    def clear(self) -> None:
        self._cache = None
        self.last_result = None
