from fastapi.testclient import TestClient

_ORIGIN = "https://req-sender.example"


def test_cors_preflight(client: TestClient) -> None:
    res = client.options(
        "/api/echo",
        headers={
            "Origin": _ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "X-Custom, If-None-Match, Range",
        },
    )
    assert res.status_code in (200, 204)
    assert res.headers["access-control-allow-origin"] == "*"
    assert "POST" in res.headers.get("access-control-allow-methods", "")
    # 任意ヘッダ許可: リクエストされたヘッダがそのまま許可される
    assert "x-custom" in res.headers.get("access-control-allow-headers", "").lower()


def test_cors_simple_get(client: TestClient) -> None:
    res = client.get("/api/echo", headers={"Origin": _ORIGIN})
    assert res.status_code == 200
    assert res.headers["access-control-allow-origin"] == "*"
    # JS から全レスポンスヘッダを読めるよう公開
    assert res.headers.get("access-control-expose-headers") == "*"
