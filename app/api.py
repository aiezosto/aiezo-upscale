"""Cầu nối giữa giao diện (window.pywebview.api.*) và lõi xử lý Python.

Mọi xử lý nặng chạy trong 1 luồng nền; tiến độ gửi về giao diện qua window.__upscale.onEvent(...).
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import threading
import time
import traceback
from pathlib import Path

from . import APP_NAME, APP_VERSION, google_engine
from . import settings as cfgmod
from .imaging import IMAGE_EXTS, SourceImage, load_image, preview_data_url
from .models import MODELS, Cancelled, ModelManager, device_info, pick_device
from .paths import MODELS_DIR
from .pipeline import TARGETS, Pipeline, Settings, seedvr2_max_pixels, target_size

log = logging.getLogger("upscale")
AIEZO_URL = "https://aiezo.net"


class Api:
    def __init__(self):
        self._window = None
        self._cfg = cfgmod.load()
        self._device = pick_device()
        self._pipeline = Pipeline(ModelManager(self._device))
        self._sources: dict[str, SourceImage] = {}
        self._worker: threading.Thread | None = None
        self._cancel = threading.Event()
        self._last_emit = 0.0
    def _attach(self, window) -> None:
        self._window = window

    # ------------------------------------------------------------- tiện ích nội bộ

    def _emit(self, kind: str, payload: dict, throttle: bool = False) -> None:
        if self._window is None:
            return
        now = time.time()
        if throttle and now - self._last_emit < 0.1:
            return
        self._last_emit = now
        msg = json.dumps({"type": kind, **payload}, ensure_ascii=False)
        try:
            self._window.evaluate_js(f"window.__upscale && window.__upscale.onEvent({msg})")
        except Exception:
            log.exception("emit failed")

    def _source(self, path: str) -> SourceImage:
        src = self._sources.get(path)
        if src is None:
            src = load_image(path)
            self._sources = {path: src}  # chỉ giữ ảnh đang mở để không đầy RAM
        return src

    def _busy(self) -> bool:
        return self._worker is not None and self._worker.is_alive()

    def _run(self, fn, *args) -> dict:
        if self._busy():
            return {"ok": False, "error": "Đang xử lý ảnh khác, vui lòng đợi."}
        self._cancel.clear()
        self._worker = threading.Thread(target=fn, args=args, daemon=True)
        self._worker.start()
        return {"ok": True}

    # ------------------------------------------------------------- khởi động

    def init(self) -> dict:
        models = [{"key": m.key, "label": m.label, "description": m.description,
                   "installed": (MODELS_DIR / m.file).exists(), "license": m.license, "source": m.source}
                  for m in MODELS.values()]
        from . import seedvr2_engine as SV

        seedvr2 = [{"key": v.key, "label": v.label, "description": v.description, "installed": SV.installed(v.key)}
                   for v in SV.VARIANTS.values()]
        return {"app": APP_NAME, "version": APP_VERSION, "device": device_info(self._device),
                "models": models, "seedvr2": seedvr2, "settings": cfgmod.public_view(self._cfg),
                "targets": TARGETS, "seedvr2_max_pixels": seedvr2_max_pixels()}

    def open_aiezo(self, path: str = "") -> dict:
        """Mở web AIEZO bằng trình duyệt mặc định (chỉ đúng tên miền AIEZO)."""
        import webbrowser

        path = path if path.startswith("/") else "/"
        webbrowser.open(AIEZO_URL + path)
        return {"ok": True}

    def save_settings(self, patch: dict) -> dict:
        for k, v in patch.items():
            if k in self._cfg and k != "google":
                self._cfg[k] = v
        cfgmod.save(self._cfg)
        return {"ok": True}

    # ------------------------------------------------------------- chọn ảnh

    def pick_images(self) -> list[dict]:
        import webview

        exts = ";".join(f"*{e}" for e in sorted(IMAGE_EXTS))
        paths = self._window.create_file_dialog(webview.FileDialog.OPEN, allow_multiple=True,
                                                file_types=(f"Ảnh ({exts})", "Tất cả (*.*)"))
        return self.describe(list(paths or []))

    def describe(self, paths: list[str]) -> list[dict]:
        """Thông tin cơ bản (không đọc toàn bộ ảnh) để hiện danh sách."""
        from PIL import Image

        out = []
        for p in paths:
            pp = Path(p)
            if pp.suffix.lower() not in IMAGE_EXTS or not pp.is_file():
                continue
            try:
                with Image.open(pp) as im:
                    w, h = im.size
                    if im.getexif().get(0x0112) in (5, 6, 7, 8):  # ảnh xoay 90° theo EXIF
                        w, h = h, w
                out.append({"path": str(pp), "name": pp.name, "width": w, "height": h, "bytes": pp.stat().st_size})
            except Exception as e:
                out.append({"path": str(pp), "name": pp.name, "error": f"Không đọc được ảnh: {e}"})
        return out

    def on_drop(self, paths: list[str]) -> None:
        items = []
        for p in paths:
            pp = Path(p)
            if pp.is_dir():
                items += [str(f) for f in sorted(pp.iterdir()) if f.suffix.lower() in IMAGE_EXTS]
            else:
                items.append(str(pp))
        self._emit("dropped", {"items": self.describe(items)})

    def open_image(self, path: str) -> dict:
        """Đọc ảnh, đo độ phân giải thực và trả ảnh xem trước."""
        try:
            src = self._source(path)
            info = self._pipeline.analyze(src)
            return {"ok": True, "path": path, "name": src.path.name, "width": src.width, "height": src.height,
                    "format": src.file_format, "has_alpha": src.alpha is not None, "notes": src.notes,
                    "preview": preview_data_url(src.rgb, 2400), **info}
        except Exception as e:
            log.exception("open_image")
            return {"ok": False, "error": f"Không mở được ảnh: {e}"}

    def output_size(self, path: str, settings: dict) -> dict:
        src = self._sources.get(path)
        if src is None:
            return {}
        w, h = target_size(src.width, src.height, Settings.from_dict(settings))
        return {"width": w, "height": h}

    # ------------------------------------------------------------- xử lý 1 ảnh

    def start(self, path: str, settings: dict) -> dict:
        return self._run(self._job_single, path, settings)

    def _job_single(self, path: str, settings: dict) -> None:
        t0 = time.time()
        try:
            s = Settings.from_dict(settings)
            src = self._source(path)
            self._emit("progress", {"value": 0.01, "message": "Đang chuẩn bị"})
            g = cfgmod.google_runtime(self._cfg) if s.engine == "google" else None
            r = self._pipeline.restore(src, s, g, lambda f, m: self._emit("progress", {"value": f, "message": m}, True),
                                       self._cancel, cfgmod.fal_key(self._cfg))
            self._emit("progress", {"value": 0.95, "message": "Đang khử bạc màu, làm nét, đo độ khớp"})
            res = self._pipeline.finish(src, r, s)
            self._emit("progress", {"value": 0.98, "message": "Đang tạo ảnh xem trước"})
            pv = self._pipeline.previews()
            self._emit("done", {"report": res.report, "notes": res.notes, **pv,
                                "total_seconds": round(time.time() - t0, 1)})
        except Cancelled:
            self._emit("cancelled", {})
        except Exception as e:
            log.error("job failed\n%s", traceback.format_exc())
            self._emit("error", {"message": str(e)})

    def cancel(self) -> dict:
        self._cancel.set()
        return {"ok": True}

    def crop(self, cx: float, cy: float, size: int = 420) -> dict:
        try:
            return {"ok": True, **self._pipeline.crop(cx, cy, size)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def save_result(self, settings: dict) -> dict:
        try:
            s = Settings.from_dict(settings)
            p = self._pipeline.save(Path(s.out_dir or self._cfg["out_dir"]), s)
            return {"ok": True, "path": str(p)}
        except Exception as e:
            log.exception("save")
            return {"ok": False, "error": f"Không lưu được ảnh: {e}"}

    # ------------------------------------------------------------- hàng loạt

    def start_batch(self, paths: list[str], settings: dict) -> dict:
        return self._run(self._job_batch, paths, settings)

    def _job_batch(self, paths: list[str], settings: dict) -> None:
        s = Settings.from_dict(settings)
        out_dir = Path(s.out_dir or self._cfg["out_dir"])
        g = cfgmod.google_runtime(self._cfg) if s.engine == "google" else None
        n = len(paths)
        for i, p in enumerate(paths):
            if self._cancel.is_set():
                self._emit("batch_item", {"index": i, "status": "cancelled"})
                continue
            self._emit("batch_item", {"index": i, "status": "running"})
            try:
                src = self._source(p)
                info = self._pipeline.analyze(src)
                si = Settings.from_dict({**settings, "contrast": settings.get("contrast", "auto") is True
                                         or (settings.get("contrast") == "auto" and info["suggest_contrast"])})

                def prog(f, m, i=i):
                    self._emit("progress", {"value": (i + f) / n, "message": f"Ảnh {i + 1}/{n}: {m}"}, True)

                r = self._pipeline.restore(src, si, g, prog, self._cancel, cfgmod.fal_key(self._cfg))
                res = self._pipeline.finish(src, r, si)
                saved = self._pipeline.save(out_dir, si)
                self._emit("batch_item", {"index": i, "status": "done", "path": str(saved),
                                          "out_w": res.width, "out_h": res.height,
                                          "psnr": res.report["psnr"], "ssim": res.report["ssim"],
                                          "level": res.report["level"]})
            except Cancelled:
                self._emit("batch_item", {"index": i, "status": "cancelled"})
            except Exception as e:
                log.error("batch item failed\n%s", traceback.format_exc())
                self._emit("batch_item", {"index": i, "status": "error", "error": str(e)})
        self._pipeline.clear()
        self._emit("batch_done", {"out_dir": str(out_dir)})

    # ------------------------------------------------------------- thư mục

    def choose_folder(self) -> str | None:
        import webview

        r = self._window.create_file_dialog(webview.FileDialog.FOLDER, directory=self._cfg["out_dir"])
        if r:
            self._cfg["out_dir"] = r[0]
            cfgmod.save(self._cfg)
            return r[0]
        return None

    def open_path(self, path: str) -> None:
        p = Path(path)
        if p.is_file():
            subprocess.Popen(["explorer", "/select,", str(p)])
        else:
            p.mkdir(parents=True, exist_ok=True)
            os.startfile(str(p))  # noqa: S606 - thư mục người dùng chọn

    # ------------------------------------------------------------- Google (tuỳ chọn)

    def set_google(self, patch: dict) -> dict:
        g = self._cfg["google"]
        for k in ("enabled", "auth", "service_account_file", "project", "location", "preservation", "enhance_input"):
            if k in patch:
                g[k] = patch[k]
        if "api_key" in patch:
            g["api_key_enc"] = cfgmod.encrypt(patch["api_key"].strip())
        cfgmod.save(self._cfg)
        return {"ok": True, "settings": cfgmod.public_view(self._cfg)}

    def set_fal(self, api_key: str) -> dict:
        self._cfg.setdefault("fal", {})["api_key_enc"] = cfgmod.encrypt(api_key.strip())
        cfgmod.save(self._cfg)
        return {"ok": True, "settings": cfgmod.public_view(self._cfg)}

    def test_fal(self) -> dict:
        from . import fal_engine

        try:
            return {"ok": True, "message": fal_engine.test_key(cfgmod.fal_key(self._cfg))}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def pick_service_account(self) -> str | None:
        import webview

        r = self._window.create_file_dialog(webview.FileDialog.OPEN, file_types=("Khoá JSON (*.json)",))
        return r[0] if r else None

    def test_google(self) -> dict:
        try:
            return {"ok": True, "message": google_engine.test_connection(cfgmod.google_runtime(self._cfg))}
        except Exception as e:
            return {"ok": False, "error": str(e)}
