"""Cài đặt người dùng lưu ở %APPDATA%\\AIEZO UpScale\\settings.json.

Khoá API Google được mã hoá bằng Windows DPAPI (chỉ tài khoản Windows hiện tại giải mã được).
"""
from __future__ import annotations

import base64
import ctypes
import json
import sys

from .paths import DEFAULT_OUTPUT_DIR, SETTINGS_FILE

DEFAULTS: dict = {
    "theme": "dark",
    "out_dir": str(DEFAULT_OUTPUT_DIR),
    "out_format": "PNG",
    "jpeg_quality": 95,
    "target": "4K",
    "custom_long": 3840,
    "engine": "seedvr2",            # seedvr2 | fal | local | google
    "seedvr2": "7b_sharp",
    "model": "restore",
    "fidelity": 0.5,
    "sharpen": 0.5,                 # làm nét thêm cho model cổ điển
    "sharpen_ai": 0.0,              # làm nét thêm cho SeedVR2 (bản thân đã nét)
    "fidelity_ai": 0.5,             # bám ảnh gốc cho SeedVR2
    "fal": {"api_key_enc": ""},
    "google": {
        "enabled": False,
        "auth": "api_key",          # api_key (Vertex AI express) | service_account
        "api_key_enc": "",
        "service_account_file": "",
        "project": "",
        "location": "us-central1",
        "preservation": 0.9,
        "enhance_input": True,
    },
}


class _Blob(ctypes.Structure):
    # DWORD = 32-bit không dấu; viết thẳng c_uint32 để module nạp được cả trên máy chủ Linux
    _fields_ = [("cbData", ctypes.c_uint32), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _dpapi(data: bytes, protect: bool) -> bytes:
    if sys.platform != "win32":
        return data
    crypt32, kernel32 = ctypes.windll.crypt32, ctypes.windll.kernel32
    buf = ctypes.create_string_buffer(data, len(data))
    inp, out = _Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))), _Blob()
    fn = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
    if not fn(ctypes.byref(inp), None, None, None, None, 0, ctypes.byref(out)):
        raise OSError("DPAPI lỗi")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        kernel32.LocalFree(out.pbData)


def encrypt(text: str) -> str:
    return base64.b64encode(_dpapi(text.encode("utf-8"), True)).decode("ascii") if text else ""


def decrypt(blob: str) -> str:
    if not blob:
        return ""
    try:
        return _dpapi(base64.b64decode(blob), False).decode("utf-8")
    except Exception:
        return ""


def _merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in over.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _merge(out[k], v)
        elif k in out:
            out[k] = v
    return out


def load() -> dict:
    try:
        return _merge(DEFAULTS, json.loads(SETTINGS_FILE.read_text("utf-8")))
    except Exception:
        return json.loads(json.dumps(DEFAULTS))


def save(cfg: dict) -> None:
    SETTINGS_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), "utf-8")


def public_view(cfg: dict) -> dict:
    """Bản gửi sang giao diện: không bao giờ gửi khoá API, chỉ báo đã có hay chưa."""
    v = json.loads(json.dumps(cfg))
    g = v["google"]
    g["has_api_key"] = bool(g.pop("api_key_enc", ""))
    v["fal"] = {"has_api_key": bool(v.get("fal", {}).pop("api_key_enc", ""))}
    return v


def fal_key(cfg: dict) -> str:
    return decrypt(cfg.get("fal", {}).get("api_key_enc", ""))


def google_runtime(cfg: dict) -> dict:
    g = dict(cfg["google"])
    g["api_key"] = decrypt(g.pop("api_key_enc", ""))
    return g
