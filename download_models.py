"""Tải các file model vào thư mục models/ và kiểm tra SHA-256 (chỉ cần khi thiếu file)."""
import hashlib
import sys
import urllib.request
from pathlib import Path

MODELS_DIR = Path(__file__).resolve().parent / "models"

# (tên file, link tải chính thức / bản sao, SHA-256, dung lượng byte)
MODELS = [
    ("RealESRNet_x4plus.pth",
     "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.1/RealESRNet_x4plus.pth",
     "a820b9bde89a874d7599d545567308ce6c128fc8754a53208eda016d40aa81df", 67040989),
    ("003_realSR_BSRGAN_DFO_s64w8_SwinIR-M_x4_PSNR.pth",
     "https://github.com/JingyunLiang/SwinIR/releases/download/v0.0/003_realSR_BSRGAN_DFO_s64w8_SwinIR-M_x4_PSNR.pth",
     "1fd8fed99684bd271db55563e4906d36459cf535446820053f7a1081d4781dc5", 67129849),
    ("RealESRGAN_x4plus.pth",
     "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth",
     "4fa0d38905f75ac06eb49a7951b426670021be3018265fd191d2125df9d682f1", 67040989),
    # Bản gốc của tác giả HAT nằm trên Google Drive; đây là bản safetensors trên Hugging Face.
    ("HAT-L_SRx4_ImageNet-pretrain.safetensors",
     "https://huggingface.co/GraydientPlatformAPI/safetensor-upscalers/resolve/main/HAT-L_SRx4_ImageNet-pretrain.safetensors",
     "da04ee70eeed8d143b264f244a7582295f7ef78d42f5f6e6dac9c0f92e91d7ab", 165299287),
    # SeedVR2 (ByteDance Seed, Apache-2.0), bản đóng gói cho ComfyUI-SeedVR2_VideoUpscaler
    ("seedvr2/ema_vae_fp16.safetensors",
     "https://huggingface.co/numz/SeedVR2_comfyUI/resolve/main/ema_vae_fp16.safetensors",
     "20678548f420d98d26f11442d3528f8b8c94e57ee046ef93dbb7633da8612ca1", 501324814),
    ("seedvr2/seedvr2_ema_3b_fp8_e4m3fn.safetensors",
     "https://huggingface.co/numz/SeedVR2_comfyUI/resolve/main/seedvr2_ema_3b_fp8_e4m3fn.safetensors",
     "3bf1e43ebedd570e7e7a0b1b60d6a02e105978f505c8128a241cde99a8240cff", 3391544696),
    ("seedvr2/seedvr2_ema_7b_sharp-Q4_K_M.gguf",
     "https://huggingface.co/AInVFX/SeedVR2_comfyUI/resolve/main/seedvr2_ema_7b_sharp-Q4_K_M.gguf",
     "7aed800ac4eb8e0d18569a954c0ff35f5a1caa3ed5d920e66cc31405f75b6e69", 4758306592),
]


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    MODELS_DIR.mkdir(exist_ok=True)
    bad = 0
    for name, url, digest, size in MODELS:
        dst = MODELS_DIR / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists() and dst.stat().st_size == size and sha256(dst) == digest:
            print(f"OK      {name}")
            continue
        print(f"Đang tải {name} ({size / 1e6:.0f} MB)…")
        tmp = dst.with_suffix(dst.suffix + ".part")
        urllib.request.urlretrieve(url, tmp)
        if sha256(tmp) != digest:
            tmp.unlink()
            print(f"LỖI     {name}: SHA-256 không khớp, đã xoá file tải về")
            bad += 1
            continue
        tmp.replace(dst)
        print(f"OK      {name}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
