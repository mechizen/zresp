"""コンテンツ配信エンドポイント (Dresp の多形式配信・動的画像生成に相当).

CDN キャッシュ / 圧縮 / 画像最適化(Polish) / WAF のファイル検査などの検証に使う。
"""

from __future__ import annotations

from fastapi import APIRouter, Response
from fastapi.responses import JSONResponse

from app.services.content import (
    BINARY_SAMPLE_EXTS,
    IMAGE_FORMATS,
    MEDIA_TYPES,
    clamp_dimension,
    render_image,
    sample_bytes,
)

router = APIRouter(prefix="/content", tags=["content"])

_CACHE_HEADERS = {"Cache-Control": "public, max-age=300"}


@router.get("/sample.{ext}")
async def content_sample(ext: str) -> Response:
    """拡張子に応じたサンプルコンテンツを配信する (例 `/content/sample.png`)。"""
    ext = ext.lower()
    if ext not in MEDIA_TYPES:
        return JSONResponse(
            {"error": f"unsupported extension: {ext!r}", "supported": sorted(MEDIA_TYPES)},
            status_code=400,
        )
    result = sample_bytes(ext)
    if result is None and ext in BINARY_SAMPLE_EXTS:
        return JSONResponse(
            {
                "error": f"no bundled sample for .{ext}",
                "hint": f"app/static/samples/sample.{ext} を置くと配信されます。",
            },
            status_code=404,
        )
    if result is None:  # 到達しない想定だが保険
        return JSONResponse({"error": "could not generate sample"}, status_code=500)
    body, media_type = result
    return Response(content=body, media_type=media_type, headers=_CACHE_HEADERS)


@router.get("/image/{spec}")
async def content_image(spec: str) -> Response:
    """`{WIDTH}x{HEIGHT}.{png|jpg|gif|webp}` で任意サイズの画像を生成する。"""
    if "." not in spec:
        return JSONResponse({"error": "spec must be like 640x480.png"}, status_code=400)
    dims, ext = spec.rsplit(".", 1)
    ext = ext.lower()
    if ext not in IMAGE_FORMATS:
        return JSONResponse(
            {"error": f"unsupported image format: {ext!r}", "supported": sorted(IMAGE_FORMATS)},
            status_code=400,
        )
    if "x" not in dims.lower():
        return JSONResponse({"error": "dimensions must be like 640x480"}, status_code=400)
    w_str, h_str = dims.lower().split("x", 1)
    try:
        width = clamp_dimension(int(w_str))
        height = clamp_dimension(int(h_str))
    except ValueError:
        return JSONResponse({"error": f"invalid dimensions: {dims!r}"}, status_code=400)

    body = render_image(width, height, ext)
    return Response(content=body, media_type=MEDIA_TYPES[ext], headers=_CACHE_HEADERS)
