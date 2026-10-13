# AIEZO UpScale — làm nét & phóng to ảnh lên 2K · 4K · 8K bằng AI

Ứng dụng desktop Windows **miễn phí, mã nguồn mở**: đưa ảnh vỡ / nhoè vào, xuất ảnh 2K, 4K, 8K đã làm nét.
AI chạy ngay trên card đồ hoạ NVIDIA của máy, không cần mạng, không tải ảnh lên đâu.

Một sản phẩm của **[AIEZO](https://aiezo.net)**.

## Tải về & cài đặt

Vào mục **[Releases](../../releases/latest)** → tải **đủ tất cả** các file `AIEZO_UpScale_Setup.part*` vào cùng
một thư mục → bấm đúp `AIEZO_UpScale_Setup.part1.exe` → **Cài đặt**. Xem thêm `HUONG DAN CAI DAT.txt` trong Releases.

Yêu cầu: Windows 10/11 64-bit, card NVIDIA (nên có 8–12 GB VRAM trở lên) với driver mới, ổ trống ~14 GB.
Bộ cài chưa ký số nên Windows có thể cảnh báo: bấm **More info → Run anyway**.

## Tính năng

- **SeedVR2** (ByteDance Seed, diffusion một bước) chạy trên máy: tăng chi tiết mà giữ nguyên người, vật, bố cục.
  Bản 7B sharp (nét nhất) và 3B (nhanh hơn).
- Model cổ điển x4 (Real-ESRNet, SwinIR Real-SR, HAT-L) không vẽ thêm chi tiết; Real-ESRGAN (GAN) có gắn nhãn “có vẽ thêm”.
- 2K / 4K / 8K theo cạnh dài, x2, x4, kích thước tuỳ chỉnh; giữ đúng tỉ lệ, profile màu, nền trong suốt, ảnh 16-bit.
- Đo **độ phân giải thực** của ảnh (ảnh đã bị phóng nhoè trước đó), **bám ảnh gốc** (back-projection),
  **khử bạc màu**, **làm nét bằng giải chập Richardson–Lucy** có chặn viền sáng.
- Báo **độ khớp với ảnh gốc** (PSNR / SSIM) và độ nét so với phóng thường sau mỗi lần chạy.
- So sánh trượt trước/sau, soi 1:1 điểm ảnh thật, xử lý **hàng loạt** cả thư mục.
- Tuỳ chọn trả phí do người dùng tự cấu hình: SeedVR2 qua API fal.ai, Google Imagen Upscale (cần khoá riêng).

Thời gian đo trên RTX 3060 12 GB: ảnh 1672×941 → 4000 px khoảng 50–70 giây (SeedVR2); → 8K khoảng 3 phút
(GPU 12 GB chạy SeedVR2 tới ~9,5 MP, phần còn lại phóng tiếp bằng Real-ESRNet).

## Chạy từ mã nguồn

```bash
python -m venv .venv
.venv\Scripts\pip install torch==2.11.0 torchvision==0.26.0 --index-url https://download.pytorch.org/whl/cu128
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\pip install -r engines\seedvr2\requirements.txt
.venv\Scripts\python download_models.py
cd frontend && npm install && npm run build && cd ..
.venv\Scripts\python main.py
```

`download_models.py` tải các file model (~9 GB) từ nguồn gốc và kiểm tra SHA-256.
Đóng gói EXE: `powershell -ExecutionPolicy Bypass -File build.ps1`. Tự kiểm tra: `main.py --selftest`.

## Cấu trúc

```
main.py               cửa sổ desktop (pywebview + WebView2), --selftest
app/pipeline.py       quy trình làm nét/phóng to, đo kiểm chứng
app/seedvr2_engine.py SeedVR2 chạy trong tiến trình con
app/models.py         model x4 cổ điển, chạy theo ô chống thiếu VRAM
app/analysis.py       độ phân giải thực, khử bạc màu, giải chập, PSNR/SSIM
app/imaging.py        đọc/ghi ảnh (profile màu, alpha, 16-bit)
app/api.py            cầu nối giao diện ↔ Python
engines/seedvr2/      ComfyUI-SeedVR2_VideoUpscaler (Apache-2.0, xem VENDORED_FROM.txt)
frontend/             giao diện React + Tailwind (hệ màu AIEZO)
```

## Giấy phép

- Mã nguồn của dự án: [MIT](LICENSE).
- `engines/seedvr2`: Apache-2.0 (giữ nguyên LICENSE gốc). Font Be Vietnam Pro, Inter, Lexend Exa: SIL OFL 1.1.
- Model: SeedVR2 (Apache-2.0), Real-ESRGAN / Real-ESRNet (BSD-3-Clause), SwinIR (Apache-2.0), HAT (theo giấy phép
  của tác giả tại github.com/XPixelGroup/HAT). File model không nằm trong kho mã; tải bằng `download_models.py`.

---
Ghé **[aiezo.net](https://aiezo.net)** để xem thêm các ứng dụng AI của AIEZO.
