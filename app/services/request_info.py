"""受信したリクエストを正規化し、Cloudflare が付与するヘッダを意味別に分類する.

このサーバは Cloudflare の背後に立つ「オリジン」として動く前提なので、
クライアント実 IP は TCP ピア (cloudflared/プロキシ) ではなく
`CF-Connecting-IP` 等のヘッダから読み取る必要がある。
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from fastapi import Request
from pydantic import BaseModel, Field

# 1 リクエストで本文を保持・表示する上限 (これを超える本文はメタデータのみ表示)
_BODY_PREVIEW_LIMIT = 64 * 1024


class HeaderCategory(BaseModel):
    """1 つのヘッダ分類グループ (UI ではセクションとして表示)."""

    id: str
    title: str
    description: str
    headers: dict[str, str] = Field(default_factory=dict)


class ClientIpInfo(BaseModel):
    """クライアント IP の解決結果 (どのヘッダから来たかを区別して提示)."""

    socket_peer: str | None = None  # TCP ピア = cloudflared / ロードバランサ
    cf_connecting_ip: str | None = None  # Cloudflare が付与する実クライアント IP
    true_client_ip: str | None = None  # Enterprise: True-Client-IP managed transform
    x_real_ip: str | None = None
    x_forwarded_for: str | None = None
    x_forwarded_for_chain: list[str] = Field(default_factory=list)
    best_guess: str | None = None  # 実クライアント IP の最有力候補


class BodyInfo(BaseModel):
    """リクエスト本文の概要."""

    size: int
    content_type: str | None = None
    text: str | None = None
    json_value: Any | None = None
    form: dict[str, str] | None = None
    truncated: bool = False


class RequestInfo(BaseModel):
    """インスペクタが返すリクエスト全体の構造化情報."""

    method: str
    path: str
    query_string: str
    query_params: dict[str, list[str]]
    http_version: str
    scheme: str
    cf_ray: str | None
    client_ip: ClientIpInfo
    categories: list[HeaderCategory]
    headers: dict[str, str]
    cookies: dict[str, str]
    body: BodyInfo
    timestamp: str


# 分類定義: 優先度順 (先に一致したカテゴリに割り当てる)。
# ヘッダ名はすべて小文字で比較する。
_CATEGORY_DEFS: list[tuple[str, str, str, set[str]]] = [
    (
        "cloudflare_connection",
        "Cloudflare 接続・識別",
        "Cloudflare がオリジンへ常時付与する接続情報。実クライアント IP やリクエスト ID。",
        {
            "cf-connecting-ip",
            "cf-connecting-ipv6",
            "cf-pseudo-ipv4",
            "cf-ray",
            "cf-visitor",
            "cf-worker",
            "cf-ew-via",
            "cdn-loop",
            "true-client-ip",
            "x-forwarded-for",
            "x-forwarded-proto",
            "x-real-ip",
        },
    ),
    (
        "bot_management",
        "Bot Management",
        "Managed Transform『Add bot protection headers』有効時に付与"
        " (Enterprise + Bot Management)。",
        {"cf-bot-score", "cf-verified-bot", "cf-ja3-hash", "cf-ja4"},
    ),
    (
        "mtls",
        "mTLS / クライアント証明書 (API Shield)",
        "Transform Rule の Client-Cert(RFC9440) や"
        " Managed Transform『Add TLS client auth headers』。",
        {
            "client-cert",
            "client-cert-chain",
            "cf-cert-presented",
            "cf-cert-verified",
            "cf-cert-revoked",
            "cf-cert-issuer-dn",
            "cf-cert-subject-dn",
            "cf-cert-issuer-dn-rfc2253",
            "cf-cert-subject-dn-rfc2253",
            "cf-cert-issuer-dn-legacy",
            "cf-cert-subject-dn-legacy",
            "cf-cert-serial",
            "cf-cert-issuer-serial",
            "cf-cert-fingerprint-sha256",
            "cf-cert-fingerprint-sha1",
            "cf-cert-not-before",
            "cf-cert-not-after",
            "cf-cert-ski",
            "cf-cert-issuer-ski",
        },
    ),
    (
        "access",
        "Cloudflare Access / JWT",
        "Zero Trust Access が付与する認証アサーション。API Shield JWT 検証のトークンもここで確認。",
        {
            "cf-access-jwt-assertion",
            "cf-access-authenticated-user-email",
            "cf-access-client-id",
        },
    ),
    (
        "geo",
        "訪問者ロケーション",
        "Managed Transform『Add visitor location headers』で付与される地理情報。",
        {
            "cf-ipcountry",
            "cf-ipcity",
            "cf-ipcontinent",
            "cf-iplongitude",
            "cf-iplatitude",
            "cf-region",
            "cf-region-code",
            "cf-metro-code",
            "cf-postal-code",
            "cf-timezone",
        },
    ),
    (
        "security_detection",
        "セキュリティ検知",
        "漏洩クレデンシャル / 悪意あるアップロード検知の Managed Transform ヘッダ。",
        {"exposed-credential-check", "malicious-uploads-detection"},
    ),
]

_STANDARD_CATEGORY = (
    "standard",
    "標準・その他ヘッダ",
    "ブラウザ等が送信した通常のリクエストヘッダ。",
)


def _classify(name: str) -> str:
    lowered = name.lower()
    for cid, _title, _desc, names in _CATEGORY_DEFS:
        if lowered in names:
            return cid
    return _STANDARD_CATEGORY[0]


def _raw_headers(request: Request) -> dict[str, str]:
    """元の大文字小文字を保ったヘッダ辞書 (重複キーはカンマ連結)."""
    result: dict[str, str] = {}
    for raw_name, raw_value in request.headers.raw:
        name = raw_name.decode("latin-1")
        value = raw_value.decode("latin-1")
        if name in result:
            result[name] = f"{result[name]}, {value}"
        else:
            result[name] = value
    return result


def _build_categories(headers: dict[str, str]) -> list[HeaderCategory]:
    buckets: dict[str, dict[str, str]] = {cid: {} for cid, *_ in _CATEGORY_DEFS}
    buckets[_STANDARD_CATEGORY[0]] = {}
    for name, value in headers.items():
        buckets[_classify(name)][name] = value

    categories: list[HeaderCategory] = []
    for cid, title, desc, _names in _CATEGORY_DEFS:
        if buckets[cid]:
            categories.append(
                HeaderCategory(id=cid, title=title, description=desc, headers=buckets[cid])
            )
    sid, stitle, sdesc = _STANDARD_CATEGORY
    if buckets[sid]:
        categories.append(
            HeaderCategory(id=sid, title=stitle, description=sdesc, headers=buckets[sid])
        )
    return categories


def _resolve_scheme(request: Request, headers: dict[str, str]) -> str:
    """元のクライアント→Cloudflare 間のスキームを推定する."""
    lower = {k.lower(): v for k, v in headers.items()}
    visitor = lower.get("cf-visitor")
    if visitor:
        try:
            scheme = json.loads(visitor).get("scheme")
            if isinstance(scheme, str):
                return scheme
        except (json.JSONDecodeError, AttributeError):
            pass
    if "x-forwarded-proto" in lower:
        return lower["x-forwarded-proto"].split(",")[0].strip()
    return request.url.scheme


def _resolve_client_ip(request: Request, headers: dict[str, str]) -> ClientIpInfo:
    lower = {k.lower(): v for k, v in headers.items()}
    xff = lower.get("x-forwarded-for")
    chain = [part.strip() for part in xff.split(",")] if xff else []
    cf_ip = lower.get("cf-connecting-ip")
    true_ip = lower.get("true-client-ip")
    socket_peer = request.client.host if request.client else None
    best = cf_ip or true_ip or (chain[0] if chain else None) or socket_peer
    return ClientIpInfo(
        socket_peer=socket_peer,
        cf_connecting_ip=cf_ip,
        true_client_ip=true_ip,
        x_real_ip=lower.get("x-real-ip"),
        x_forwarded_for=xff,
        x_forwarded_for_chain=chain,
        best_guess=best,
    )


async def _build_body(request: Request) -> BodyInfo:
    raw = await request.body()
    content_type = request.headers.get("content-type")
    info = BodyInfo(size=len(raw), content_type=content_type)
    if not raw:
        return info

    if len(raw) > _BODY_PREVIEW_LIMIT:
        info.truncated = True
        return info

    try:
        text = raw.decode("utf-8")
        info.text = text
    except UnicodeDecodeError:
        return info

    ctype = (content_type or "").lower()
    if "json" in ctype:
        try:
            info.json_value = json.loads(text)
        except json.JSONDecodeError:
            pass
    elif "application/x-www-form-urlencoded" in ctype or "multipart/form-data" in ctype:
        try:
            form = await request.form()
            info.form = {
                key: (value if isinstance(value, str) else getattr(value, "filename", "<file>"))
                for key, value in form.multi_items()
            }
        except Exception:  # noqa: BLE001 — フォーム解析失敗時は本文テキストのみで十分
            pass
    return info


async def build_request_info(request: Request) -> RequestInfo:
    """FastAPI の Request から構造化された RequestInfo を生成する."""
    headers = _raw_headers(request)
    query_params: dict[str, list[str]] = {}
    for key in request.query_params:
        query_params[key] = request.query_params.getlist(key)

    return RequestInfo(
        method=request.method,
        path=request.url.path,
        query_string=request.url.query,
        query_params=query_params,
        http_version=request.scope.get("http_version", ""),
        scheme=_resolve_scheme(request, headers),
        cf_ray=request.headers.get("cf-ray"),
        client_ip=_resolve_client_ip(request, headers),
        categories=_build_categories(headers),
        headers=headers,
        cookies=dict(request.cookies),
        body=await _build_body(request),
        timestamp=datetime.now(UTC).isoformat(),
    )
