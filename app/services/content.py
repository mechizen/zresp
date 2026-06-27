"""各種コンテンツタイプのサンプル生成 (Dresp の多形式配信に相当).

テキスト系・PDF・画像は動的生成する。動画やフォント等の生成困難なバイナリは
`app/static/samples/` に置かれたファイルがあれば配信する。
"""

from __future__ import annotations

import io
import json
from pathlib import Path

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "static" / "samples"

# 拡張子 → Content-Type
MEDIA_TYPES: dict[str, str] = {
    "html": "text/html; charset=utf-8",
    "htm": "text/html; charset=utf-8",
    "txt": "text/plain; charset=utf-8",
    "css": "text/css; charset=utf-8",
    "js": "text/javascript; charset=utf-8",
    "mjs": "text/javascript; charset=utf-8",
    "json": "application/json",
    "xml": "application/xml",
    "svg": "image/svg+xml",
    "pdf": "application/pdf",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "webp": "image/webp",
    "mp4": "video/mp4",
    "webm": "video/webm",
    "ttf": "font/ttf",
    "woff": "font/woff",
    "woff2": "font/woff2",
}

# Pillow の保存フォーマット名
IMAGE_FORMATS: dict[str, str] = {
    "png": "PNG",
    "jpg": "JPEG",
    "jpeg": "JPEG",
    "gif": "GIF",
    "webp": "WEBP",
}

# 生成が困難なため、bundled サンプルファイルから配信する拡張子
BINARY_SAMPLE_EXTS = {"mp4", "webm", "ttf", "woff", "woff2"}

_DEFAULT_IMAGE_SIZE = (320, 240)
_MAX_IMAGE_DIM = 4096


def _text_body(ext: str) -> str:
    if ext in ("html", "htm"):
        return (
            '<!DOCTYPE html><html lang="ja"><head><meta charset="utf-8">'
            "<title>zresp sample</title></head>"
            "<body><h1>zresp sample HTML</h1><p>Cloudflare 検証用オリジンのサンプルページです。</p>"
            "</body></html>"
        )
    if ext == "css":
        return "body { font-family: system-ui; color: #f6821f; } /* zresp sample css */"
    if ext in ("js", "mjs"):
        return "// zresp sample js\nconsole.log('zresp sample', new Date().toISOString());"
    if ext == "xml":
        return '<?xml version="1.0" encoding="UTF-8"?>\n<zresp><sample>true</sample></zresp>'
    if ext == "svg":
        return (
            '<svg xmlns="http://www.w3.org/2000/svg" width="320" height="240">'
            '<rect width="100%" height="100%" fill="#171a21"/>'
            '<text x="20" y="40" fill="#f6821f" font-family="sans-serif" font-size="20">'
            "zresp sample svg</text></svg>"
        )
    if ext == "json":
        return json.dumps({"server": "zresp", "sample": True, "type": "json"}, ensure_ascii=False)
    # txt とその他
    return "zresp sample text — Cloudflare 検証用オリジン."


def text_sample(ext: str) -> tuple[bytes, str]:
    """テキスト系サンプルを (body, media_type) で返す."""
    return _text_body(ext).encode("utf-8"), MEDIA_TYPES[ext]


def render_image(width: int, height: int, ext: str) -> bytes:
    """指定サイズの画像を生成して返す (png/jpg/gif/webp)."""
    from PIL import Image, ImageDraw

    fmt = IMAGE_FORMATS[ext]
    img = Image.new("RGB", (width, height), (23, 26, 33))
    draw = ImageDraw.Draw(img)
    # 枠線と対角線で寸法を視認しやすくする
    draw.rectangle([0, 0, width - 1, height - 1], outline=(246, 130, 31))
    draw.line([0, 0, width - 1, height - 1], fill=(42, 47, 58))
    draw.line([0, height - 1, width - 1, 0], fill=(42, 47, 58))
    draw.text((6, 6), f"zresp {width}x{height} {ext}", fill=(125, 211, 252))

    buf = io.BytesIO()
    save_kwargs: dict[str, object] = {}
    if fmt == "GIF":
        img = img.convert("P")
    img.save(buf, format=fmt, **save_kwargs)
    return buf.getvalue()


def minimal_pdf(text: str = "zresp sample PDF") -> bytes:
    """xref を正しく計算した最小構成の有効な PDF を生成する."""
    stream = f"BT /F1 18 Tf 20 100 Td ({text}) Tj ET".encode()
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 144] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets: list[int] = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"

    xref_pos = len(out)
    size = len(objects) + 1
    out += f"xref\n0 {size}\n".encode()
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {size} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF".encode()
    return bytes(out)


def sample_bytes(ext: str) -> tuple[bytes, str] | None:
    """拡張子に応じたサンプルを (body, media_type) で返す。未対応なら None。"""
    ext = ext.lower()
    if ext not in MEDIA_TYPES:
        return None
    if ext in IMAGE_FORMATS:
        return render_image(*_DEFAULT_IMAGE_SIZE, ext), MEDIA_TYPES[ext]
    if ext == "pdf":
        return minimal_pdf(), MEDIA_TYPES[ext]
    if ext in BINARY_SAMPLE_EXTS:
        path = SAMPLES_DIR / f"sample.{ext}"
        if path.is_file():
            return path.read_bytes(), MEDIA_TYPES[ext]
        return None  # サンプルファイル未配置
    return text_sample(ext)


def clamp_dimension(value: int) -> int:
    return max(1, min(value, _MAX_IMAGE_DIM))
