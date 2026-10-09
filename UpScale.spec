# -*- mode: python ; coding: utf-8 -*-
# Đóng gói AIEZO UpScale thành thư mục chạy được (onedir). Chạy: build.ps1
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

# diffusers đọc thông tin phiên bản (dist-info) của các gói khi chạy: phải chép kèm, không thì lỗi
# "No package metadata was found for requests" và coi như không có torch.
metadata = copy_metadata("diffusers", recursive=True)
for _pkg in ("torch", "torchvision", "safetensors", "gguf", "opencv-python", "omegaconf",
             "rotary-embedding-torch", "einops", "psutil", "tqdm", "numpy", "pillow"):
    metadata += copy_metadata(_pkg)

# SeedVR2 chạy bằng runpy từ engines/seedvr2 nên PyInstaller không tự thấy các thư viện nó import
seedvr2_deps = (
    collect_submodules("diffusers.models") + collect_submodules("diffusers.utils")
    + collect_submodules("omegaconf") + collect_submodules("rotary_embedding_torch")
    + collect_submodules("gguf") + collect_submodules("einops")
    + ["cv2", "psutil", "tqdm", "safetensors", "safetensors.torch", "torchvision", "diffusers"]
)
hidden = collect_submodules("spandrel") + collect_submodules("webview") + ["clr"] + seedvr2_deps + ["httpx"]

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[("frontend/dist", "frontend/dist"), ("models", "models"), ("engines", "engines")]
    + collect_data_files("diffusers") + collect_data_files("gguf") + metadata,
    hiddenimports=hidden,
    excludes=["tkinter", "scipy", "skimage", "pandas", "IPython", "jupyter", "rapidocr", "onnxruntime", "segno", "fastapi", "uvicorn"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AIEZO UpScale",
    console=False,
    icon="packaging/upscale.ico",
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="AIEZO UpScale")
