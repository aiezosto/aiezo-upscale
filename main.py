"""AIEZO UpScale: cửa sổ ứng dụng desktop (WebView2 của Windows), không mở trình duyệt, không cần mạng."""
from __future__ import annotations

import logging
import sys
import warnings

warnings.filterwarnings("ignore")

if len(sys.argv) > 1 and sys.argv[1] == "--seedvr2":
    # Tiến trình con chạy SeedVR2 (app/seedvr2_engine.py gọi lại chính chương trình này)
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    # Không được nạp torch trước CLI: CLI đặt PYTORCH_CUDA_ALLOC_CONF trước khi import torch
    import runpy

    from app.paths import RESOURCE_DIR

    _engine = RESOURCE_DIR / "engines" / "seedvr2"
    sys.argv = [str(_engine / "inference_cli.py")] + sys.argv[2:]
    sys.path.insert(0, str(_engine))
    runpy.run_path(str(_engine / "inference_cli.py"), run_name="__main__")
    sys.exit(0)

from app import APP_NAME  # noqa: E402
from app.paths import FRONTEND_DIST, LOG_FILE  # noqa: E402

logging.basicConfig(filename=LOG_FILE, level=logging.INFO, encoding="utf-8",
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def main() -> None:
    import webview
    from webview.dom import DOMEventHandler

    from app.api import Api

    index = FRONTEND_DIST / "index.html"
    if not index.exists():
        raise SystemExit(f"Thiếu giao diện: {index}. Chạy 'npm run build' trong thư mục frontend.")

    api = Api()
    window = webview.create_window(
        APP_NAME, url=str(index), js_api=api,
        width=1440, height=900, min_size=(1100, 700), background_color="#050706", text_select=False,
    )
    api._attach(window)

    def on_loaded():
        # Kéo thả file: pywebview cung cấp đường dẫn đầy đủ của file thả vào cửa sổ
        def on_drop(e):
            files = e.get("dataTransfer", {}).get("files", [])
            paths = [f["pywebviewFullPath"] for f in files if f.get("pywebviewFullPath")]
            if paths:
                api.on_drop(paths)

        doc = window.dom.document
        doc.events.dragover += DOMEventHandler(lambda e: None, True, True)
        doc.events.drop += DOMEventHandler(on_drop, True, True)

    window.events.loaded += on_loaded
    webview.start(gui="edgechromium", debug="--debug" in sys.argv, private_mode=False)


def selftest() -> None:
    """Kiểm tra bản đóng gói: GPU, nạp model, chạy 1 ảnh nhỏ qua toàn bộ quy trình. Ghi kết quả vào nhật ký."""
    import tempfile
    import threading
    from pathlib import Path

    import numpy as np
    from PIL import Image

    from app.imaging import load_image
    from app.models import MODELS, ModelManager, device_info, pick_device
    from app.pipeline import Pipeline, Settings

    dev = pick_device()
    logging.info("selftest device: %s", device_info(dev))
    rng = np.random.default_rng(0)
    img = (rng.random((96, 128, 3)) * 255).astype(np.uint8)
    p = Path(tempfile.gettempdir()) / "aiezo_upscale_selftest.png"
    Image.fromarray(img).save(p)
    pl = Pipeline(ModelManager(dev))
    src = load_image(p)
    for key in MODELS:
        s = Settings.from_dict({"target": "x2", "engine": "local", "model": key})
        r = pl.restore(src, s, None, lambda f, m: None, threading.Event())
        res = pl.finish(src, r, s)
        logging.info("selftest %s OK -> %dx%d psnr=%s", key, res.width, res.height, res.report["psnr"])
    from app import seedvr2_engine as SV

    for v in SV.VARIANTS:
        if not SV.installed(v):
            logging.info("selftest seedvr2 %s SKIPPED (chưa có model)", v)
            continue
        s = Settings.from_dict({"target": "x2", "engine": "seedvr2", "seedvr2": v})
        r = pl.restore(src, s, None, lambda f, m: None, threading.Event())
        res = pl.finish(src, r, s)
        logging.info("selftest seedvr2 %s OK -> %dx%d psnr=%s", v, res.width, res.height, res.report["psnr"])
    logging.info("selftest PASSED")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        try:
            selftest()
        except Exception:
            logging.exception("selftest FAILED")
            sys.exit(1)
        sys.exit(0)
    try:
        main()
    except Exception:
        logging.exception("fatal")
        raise
