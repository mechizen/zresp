"""CDN / キャッシュ検証用エンドポイント.

オリジンは `CF-Cache-Status` を受信できないため、レスポンス本文に
オリジン生成時刻 + UUID を載せる。リロードで同じ値が返れば
Cloudflare がキャッシュから提供した、と目視で判定できる。
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from email.utils import formatdate

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse

from app.config import settings
from app.services.payload import origin_payload

router = APIRouter(prefix="/cache", tags=["cache"])

# /cache/etag が返す固定の検証子 (リクエスト間で安定 → 304 を誘発できる)
_ETAG = '"zresp-etag-v1"'
_LAST_MODIFIED = formatdate(1_700_000_000, usegmt=True)
_STREAM_CHUNK = 64 * 1024


@router.get("/timestamp")
async def cache_timestamp(max_age: int = Query(60, ge=0)) -> JSONResponse:
    """キャッシュ確認プローブ。既定で `Cache-Control: public, max-age=60`。"""
    payload = origin_payload(
        "リロードで generated_at / uuid が変わらなければ Cloudflare のキャッシュ提供です。"
    )
    return JSONResponse(payload, headers={"Cache-Control": f"public, max-age={max_age}"})


@router.get("/control")
async def cache_control(
    max_age: int | None = None,
    s_maxage: int | None = None,
    no_store: bool = False,
    no_cache: bool = False,
    public: bool = False,
    private_: bool = Query(False, alias="private"),
    stale_while_revalidate: int | None = None,
    immutable: bool = False,
    expires: int | None = Query(None, description="現在からの秒数で Expires ヘッダを設定"),
    vary: str | None = None,
) -> JSONResponse:
    """クエリで任意の Cache-Control / Expires / Vary を組み立てて返す。"""
    directives: list[str] = []
    if no_store:
        directives.append("no-store")
    if no_cache:
        directives.append("no-cache")
    if public:
        directives.append("public")
    if private_:
        directives.append("private")
    if max_age is not None:
        directives.append(f"max-age={max_age}")
    if s_maxage is not None:
        directives.append(f"s-maxage={s_maxage}")
    if stale_while_revalidate is not None:
        directives.append(f"stale-while-revalidate={stale_while_revalidate}")
    if immutable:
        directives.append("immutable")

    headers: dict[str, str] = {}
    if directives:
        headers["Cache-Control"] = ", ".join(directives)
    if expires is not None:
        headers["Expires"] = formatdate(time.time() + expires, usegmt=True)
    if vary:
        headers["Vary"] = vary

    payload = origin_payload("指定したキャッシュ指示でオリジンが応答しました。")
    payload["applied"] = {
        "Cache-Control": headers.get("Cache-Control"),
        "Expires": headers.get("Expires"),
        "Vary": headers.get("Vary"),
    }
    return JSONResponse(payload, headers=headers)


@router.get("/etag")
async def cache_etag(request: Request, max_age: int = Query(0, ge=0)) -> Response:
    """安定した ETag / Last-Modified を返し、条件付きリクエストに 304 を返す。"""
    headers = {
        "ETag": _ETAG,
        "Last-Modified": _LAST_MODIFIED,
        "Cache-Control": f"public, max-age={max_age}",
    }
    if_none_match = request.headers.get("if-none-match")
    if_modified_since = request.headers.get("if-modified-since")
    matched_etag = if_none_match is not None and (
        if_none_match.strip() == "*" or _ETAG in [tag.strip() for tag in if_none_match.split(",")]
    )
    matched_time = if_modified_since is not None and if_modified_since.strip() == _LAST_MODIFIED
    if matched_etag or matched_time:
        return Response(status_code=304, headers=headers)

    payload = origin_payload(
        "条件付きリクエスト (If-None-Match / If-Modified-Since) で 304 を確認できます。"
    )
    return JSONResponse(payload, headers=headers)


def _parse_size(raw: str) -> int | None:
    """'1024' / '64kb' / '5mb' などをバイト数に変換する。"""
    text = raw.strip().lower()
    units = {
        "": 1,
        "b": 1,
        "k": 1024,
        "kb": 1024,
        "m": 1024**2,
        "mb": 1024**2,
        "g": 1024**3,
        "gb": 1024**3,
    }
    number = text
    unit = ""
    for suffix in ("gb", "mb", "kb", "g", "m", "k", "b"):
        if text.endswith(suffix):
            number, unit = text[: -len(suffix)], suffix
            break
    try:
        value = float(number)
    except ValueError:
        return None
    if value < 0:
        return None
    return int(value * units[unit])


def _byte_stream(start: int, end: int) -> Iterator[bytes]:
    """位置に応じた決定的バイト列 (byte 値 = position & 0xFF) をストリーミングする。"""
    pos = start
    while pos <= end:
        size = min(_STREAM_CHUNK, end - pos + 1)
        yield bytes((i & 0xFF) for i in range(pos, pos + size))
        pos += size


def _parse_range(range_header: str, total: int) -> tuple[int, int] | None:
    """Range ヘッダを (start, end) に解釈する。満たせない場合は None。"""
    if not range_header.startswith("bytes="):
        return None
    spec = range_header[len("bytes=") :].split(",")[0].strip()
    if "-" not in spec:
        return None
    start_s, end_s = spec.split("-", 1)
    try:
        if start_s == "":
            suffix = int(end_s)
            if suffix == 0:
                return None
            start = max(0, total - suffix)
            end = total - 1
        else:
            start = int(start_s)
            end = int(end_s) if end_s else total - 1
    except ValueError:
        return None
    if start > end or start >= total:
        return None
    return start, min(end, total - 1)


@router.get("/bytes/{size}")
async def cache_bytes(size: str, request: Request) -> Response:
    """指定サイズの本文を返す。Range リクエストには 206 Partial Content で応答。"""
    total = _parse_size(size)
    if total is None:
        return JSONResponse({"error": f"invalid size: {size!r}"}, status_code=400)
    if total > settings.max_bytes:
        return JSONResponse(
            {"error": f"size exceeds limit ({settings.max_bytes} bytes)"}, status_code=413
        )

    base_headers = {"Accept-Ranges": "bytes", "Cache-Control": "public, max-age=300"}
    range_header = request.headers.get("range")
    if range_header:
        parsed = _parse_range(range_header, total)
        if parsed is None:
            return Response(
                status_code=416,
                headers={**base_headers, "Content-Range": f"bytes */{total}"},
            )
        start, end = parsed
        length = end - start + 1
        headers = {
            **base_headers,
            "Content-Range": f"bytes {start}-{end}/{total}",
            "Content-Length": str(length),
        }
        return StreamingResponse(
            _byte_stream(start, end),
            status_code=206,
            media_type="application/octet-stream",
            headers=headers,
        )

    headers = {**base_headers, "Content-Length": str(total)}
    return StreamingResponse(
        _byte_stream(0, total - 1),
        media_type="application/octet-stream",
        headers=headers,
    )


@router.get("/vary")
async def cache_vary(
    request: Request,
    by: str = Query("Accept-Encoding", description="Vary 対象のリクエストヘッダ名"),
) -> JSONResponse:
    """指定ヘッダで Vary を設定し、その値ごとに異なる応答を返す (キャッシュキー検証)。"""
    value = request.headers.get(by, "")
    payload = origin_payload(f"このレスポンスは Vary: {by} の値ごとに別々にキャッシュされます。")
    payload["vary_on"] = by
    payload["vary_value"] = value
    return JSONResponse(payload, headers={"Vary": by, "Cache-Control": "public, max-age=60"})
