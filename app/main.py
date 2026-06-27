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
    description=(
        "指示どおりのHTTPレスポンスを返す、従順で柔軟なWebサーバ"
    ),
)

app.mount("/static", StaticFiles(directory=str(_BASE_DIR / "static")), name="static")
app.include_router(echo.router)
app.include_router(cache.router)
app.include_router(response.router)
app.include_router(content.router)


# ランディングページに表示する検証ツール一覧
_TOOLS = [
    ("リクエスト・インスペクタ (HTML)", "/inspect", "Cloudflare 付与ヘッダを分類して表示"),
    ("リクエスト・インスペクタ (JSON)", "/api/echo", "全リクエスト情報を JSON で返す"),
    ("キャッシュ確認プローブ", "/cache/timestamp", "リロードで値が固定ならキャッシュ提供"),
    (
        "キャッシュ指示の制御",
        "/cache/control?public=true&max_age=120",
        "任意の Cache-Control を設定",
    ),
    ("ETag / 条件付きリクエスト", "/cache/etag", "If-None-Match で 304 を確認"),
    ("任意サイズ本文 / Range", "/cache/bytes/1mb", "Range で 206 Partial Content"),
    ("Vary によるキャッシュキー", "/cache/vary?by=Accept-Encoding", "ヘッダ値ごとに別キャッシュ"),
    ("任意ステータスコード", "/response/status/503", "エラー応答 / ステータス別の挙動"),
    ("リダイレクト (Location)", "/response/status/301?location=/api/echo", "3xx + Location ヘッダ"),
    ("リダイレクトチェーン", "/response/redirect/3", "3 回リダイレクトして終点で 200"),
    ("レスポンス遅延", "/response/delay/2", "2 秒待ってから応答(タイムアウト検証)"),
    ("Cookie 設定", "/response/cookie?name=sid&value=abc&samesite=Lax", "属性付き Cookie"),
    ("任意レスポンスヘッダ", "/response/headers?X-Foo=bar", "クエリをヘッダとして付与"),
    ("動的画像生成", "/content/image/640x480.png", "指定サイズの画像を生成"),
    ("コンテンツ配信", "/content/sample.pdf", "png/jpg/svg/pdf/html/css/js/json など"),
    ("多形式 Echo", "/api/echo.xml", "json / txt / xml / html"),
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
            "tools": _TOOLS,
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
