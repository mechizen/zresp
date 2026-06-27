"""リクエスト・インスペクタ (JSON / 多形式).

受信したリクエストの全容と、Cloudflare が付与したヘッダの分類を返す。
HTML 版インスペクタは main.py の `/inspect` を参照。
"""

from xml.sax import saxutils

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse

from app.services.request_info import RequestInfo, build_request_info

router = APIRouter(prefix="/api", tags=["echo"])

_ALL_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]


@router.api_route("/echo", methods=_ALL_METHODS)
async def echo(request: Request) -> RequestInfo:
    """受信したリクエストをそのまま構造化して返す (全 HTTP メソッド対応)."""
    return await build_request_info(request)


# /api/inspect は /api/echo の別名 (HTML 版 /inspect と対になる JSON エンドポイント)
@router.api_route("/inspect", methods=_ALL_METHODS)
async def inspect(request: Request) -> RequestInfo:
    """`/api/echo` のエイリアス。"""
    return await build_request_info(request)


@router.api_route("/echo.{ext}", methods=_ALL_METHODS)
async def echo_format(ext: str, request: Request) -> Response:
    """形式を指定してリクエスト情報を返す (`/api/echo.txt` `/api/echo.xml` など)。"""
    ext = ext.lower()
    if ext in ("html", "htm"):
        return RedirectResponse("/inspect")
    info = await build_request_info(request)
    if ext == "json":
        return JSONResponse(info.model_dump())
    if ext == "txt":
        return Response(_to_text(info), media_type="text/plain; charset=utf-8")
    if ext == "xml":
        return Response(_to_xml(info), media_type="application/xml")
    return JSONResponse(
        {"error": f"unsupported format: {ext!r}", "supported": ["json", "txt", "xml", "html"]},
        status_code=400,
    )


def _to_text(info: RequestInfo) -> str:
    lines = [
        "zresp request inspector",
        f"timestamp: {info.timestamp}",
        f"method:    {info.method}",
        f"path:      {info.path}",
        f"query:     {info.query_string}",
        f"scheme:    {info.scheme}",
        f"cf_ray:    {info.cf_ray}",
        "",
        "[client_ip]",
        f"best_guess:       {info.client_ip.best_guess}",
        f"cf_connecting_ip: {info.client_ip.cf_connecting_ip}",
        f"socket_peer:      {info.client_ip.socket_peer}",
        f"x_forwarded_for:  {info.client_ip.x_forwarded_for}",
        "",
    ]
    for cat in info.categories:
        lines.append(f"[{cat.id}] {cat.title}")
        lines.extend(f"{key}: {value}" for key, value in cat.headers.items())
        lines.append("")
    return "\n".join(lines)


def _to_xml(info: RequestInfo) -> str:
    esc = saxutils.escape
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        "<request>",
        f"  <method>{esc(info.method)}</method>",
        f"  <path>{esc(info.path)}</path>",
        f"  <scheme>{esc(info.scheme)}</scheme>",
        f"  <cfRay>{esc(info.cf_ray or '')}</cfRay>",
        f"  <clientIp>{esc(info.client_ip.best_guess or '')}</clientIp>",
        "  <headers>",
    ]
    for cat in info.categories:
        for key, value in cat.headers.items():
            parts.append(f'    <header name="{esc(key)}">{esc(value)}</header>')
    parts.extend(["  </headers>", "</request>"])
    return "\n".join(parts)
