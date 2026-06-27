"""汎用レスポンス整形エンドポイント.

ステータスコード・リダイレクト・リダイレクトチェーンなど、キャッシュに依存しない
「オリジンの応答を自在に作る」機能を提供する (Dresp の Set-Status-Code / Location 相当)。
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import JSONResponse

from app.services.payload import origin_payload

router = APIRouter(prefix="/response", tags=["response"])

# リダイレクトチェーンの最大ホップ数 (無限ループ防止)
_MAX_REDIRECT_HOPS = 20
# 遅延の上限秒数
_MAX_DELAY_SECONDS = 30.0
# 任意ヘッダ設定で上書きを禁止するヘッダ (レスポンス破損防止)
_PROTECTED_HEADERS = {"content-length", "content-type", "transfer-encoding", "connection"}


@router.api_route("/status/{code}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"])
async def status_code(
    code: int,
    location: str | None = Query(
        None, description="3xx の場合に Location ヘッダへ設定するリダイレクト先 URL"
    ),
) -> Response:
    """任意のステータスコードで応答する。3xx は `location` で Location ヘッダを付与できる。"""
    if code < 100 or code > 599:
        return JSONResponse({"error": "code must be between 100 and 599"}, status_code=400)

    headers: dict[str, str] = {}
    if location and 300 <= code < 400:
        headers["Location"] = location

    # 本文を持てないステータスは空レスポンスで返す
    if code in (204, 304) or (300 <= code < 400 and "Location" in headers):
        return Response(status_code=code, headers=headers)

    payload = origin_payload(f"ステータスコード {code} をオリジンが返しました。")
    if 300 <= code < 400 and not location:
        payload["hint"] = "3xx には ?location=<URL> を付けると Location ヘッダを設定できます。"
    return JSONResponse(payload, status_code=code, headers=headers)


@router.get("/redirect/{n}")
async def redirect_chain(
    n: int,
    status: int = Query(302, ge=300, le=399, description="各ホップで使うリダイレクトのステータス"),
) -> Response:
    """n 回リダイレクトを繰り返し、最後に 200 を返す (リダイレクト追従の検証)。"""
    if n < 0 or n > _MAX_REDIRECT_HOPS:
        return JSONResponse(
            {"error": f"n must be between 0 and {_MAX_REDIRECT_HOPS}"}, status_code=400
        )
    if n == 0:
        payload = origin_payload("リダイレクトチェーンの終点に到達しました。")
        return JSONResponse(payload)
    return Response(
        status_code=status,
        headers={"Location": f"/response/redirect/{n - 1}?status={status}"},
    )


@router.get("/delay/{seconds}")
async def delay(seconds: float) -> JSONResponse:
    """指定秒数だけ待ってから応答する (タイムアウト検証)。上限は 30 秒。"""
    if seconds < 0:
        return JSONResponse({"error": "seconds must be >= 0"}, status_code=400)
    waited = min(seconds, _MAX_DELAY_SECONDS)
    await asyncio.sleep(waited)
    payload = origin_payload(f"{waited} 秒待機してから応答しました。")
    payload["delay_seconds"] = waited
    return JSONResponse(payload)


@router.get("/cookies/set")
async def set_cookies(request: Request) -> JSONResponse:
    """クエリの各 `key=value` を Set-Cookie として返す (例 `?a=1&b=2`)。"""
    items = dict(request.query_params)
    payload = origin_payload("クエリの各 key=value を Set-Cookie として返しました。")
    payload["cookies"] = items
    resp = JSONResponse(payload)
    for key, value in items.items():
        resp.set_cookie(key=key, value=value)
    return resp


@router.get("/cookie")
async def set_cookie(
    name: str,
    value: str = "",
    max_age: int | None = None,
    path: str = "/",
    domain: str | None = None,
    secure: bool = False,
    httponly: bool = False,
    samesite: str | None = Query(None, description="lax / strict / none"),
) -> JSONResponse:
    """属性付きで 1 つの Cookie を設定する (SameSite / Secure / HttpOnly 等)。"""
    normalized = samesite.lower() if samesite else None
    if normalized is not None and normalized not in ("lax", "strict", "none"):
        return JSONResponse({"error": "samesite must be lax / strict / none"}, status_code=400)
    payload = origin_payload(f"Cookie '{name}' を属性付きで設定しました。")
    resp = JSONResponse(payload)
    resp.set_cookie(
        key=name,
        value=value,
        max_age=max_age,
        path=path,
        domain=domain,
        secure=secure,
        httponly=httponly,
        samesite=normalized,  # type: ignore[arg-type]
    )
    return resp


@router.get("/headers")
async def set_headers(request: Request) -> JSONResponse:
    """クエリの各 `key=value` をレスポンスヘッダとして返す (例 `?X-Foo=bar`)。"""
    applied = {
        key: value
        for key, value in request.query_params.items()
        if key.lower() not in _PROTECTED_HEADERS
    }
    payload = origin_payload("クエリの各 key=value をレスポンスヘッダとして付与しました。")
    payload["headers"] = applied
    return JSONResponse(payload, headers=applied)
