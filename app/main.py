"""zresp — 指示どおりのHTTPレスポンスを返す、従順で柔軟なWebサーバ.

オリジンとして、受信リクエストの可視化 (Echo) と
CDN/キャッシュ挙動の検証エンドポイントを提供する。
"""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import __version__
from app.config import settings
from app.routers import cache, content, echo, response
from app.services.request_info import build_request_info

_BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(_BASE_DIR / "templates"))

app = FastAPI(
    title="zresp",
    version=__version__,
    description=("指示どおりのHTTPレスポンスを返す、従順で柔軟なWebサーバ"),
)

app.mount("/static", StaticFiles(directory=str(_BASE_DIR / "static")), name="static")
app.include_router(echo.router)
app.include_router(cache.router)
app.include_router(response.router)
app.include_router(content.router)


# ランディングページに表示する検証ツール一覧 (カテゴリごとにグループ化)
_TOOL_GROUPS = [
    (
        "リクエスト・インスペクタ",
        "受信したリクエストと Cloudflare 付与ヘッダを可視化",
        [
            ("/inspect", "HTML インスペクタ", "CF 付与ヘッダを分類して表示"),
            ("/api/echo", "JSON で全情報", "全リクエスト情報を JSON で返す"),
            ("/api/echo.xml", "多形式 Echo", "json / txt / xml / html を選択"),
        ],
    ),
    (
        "CDN / キャッシュ",
        "キャッシュ・条件付きリクエスト・Range の挙動を検証",
        [
            ("/cache/timestamp", "キャッシュ確認プローブ", "リロードで値が固定ならキャッシュ提供"),
            (
                "/cache/control?public=true&max_age=120",
                "キャッシュ指示の制御",
                "任意の Cache-Control を設定",
            ),
            ("/cache/etag", "ETag / 条件付き", "If-None-Match で 304 を確認"),
            ("/cache/bytes/1mb", "任意サイズ本文 / Range", "Range で 206 Partial Content"),
            ("/cache/vary?by=Accept-Encoding", "Vary キャッシュキー", "ヘッダ値ごとに別キャッシュ"),
        ],
    ),
    (
        "レスポンス整形",
        "ステータス・リダイレクト・遅延・Cookie・ヘッダを自在に",
        [
            ("/response/status/503", "任意ステータスコード", "エラー応答 / ステータス別の挙動"),
            (
                "/response/status/301?location=/api/echo",
                "リダイレクト (Location)",
                "3xx + Location ヘッダ",
            ),
            ("/response/redirect/3", "リダイレクトチェーン", "3 回リダイレクトして終点で 200"),
            ("/response/delay/2", "レスポンス遅延", "2 秒待ってから応答 (タイムアウト検証)"),
            ("/response/cookie?name=sid&value=abc&samesite=Lax", "Cookie 設定", "属性付き Cookie"),
            ("/response/headers?X-Foo=bar", "任意レスポンスヘッダ", "クエリをヘッダとして付与"),
        ],
    ),
    (
        "コンテンツ配信",
        "各種コンテンツタイプの配信と動的画像生成",
        [
            ("/content/image/640x480.png", "動的画像生成", "指定サイズの画像を生成"),
            (
                "/content/sample.pdf",
                "コンテンツ配信",
                "png / jpg / svg / pdf / html / css / js / json など",
            ),
        ],
    ),
]


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def index(request: Request) -> HTMLResponse:
    """ランディングページ。検証ツール一覧と現在のリクエスト要約を表示。"""
    info = await build_request_info(request)
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "app_name": settings.app_name,
            "version": __version__,
            "tool_groups": _TOOL_GROUPS,
            "info": info,
        },
    )


@app.get("/inspect", response_class=HTMLResponse, include_in_schema=False)
async def inspect_html(request: Request) -> HTMLResponse:
    """HTML 版リクエスト・インスペクタ。"""
    info = await build_request_info(request)
    return templates.TemplateResponse(
        request=request,
        name="inspect.html",
        context={"app_name": settings.app_name, "info": info},
    )


@app.get("/healthz", include_in_schema=False)
async def healthz() -> JSONResponse:
    """ヘルスチェック (コンテナ HEALTHCHECK / 死活監視用)."""
    return JSONResponse({"status": "ok", "service": "zresp", "version": __version__})
