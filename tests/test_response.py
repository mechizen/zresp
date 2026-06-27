from fastapi.testclient import TestClient


def test_status_passthrough(client: TestClient) -> None:
    res = client.get("/response/status/503")
    assert res.status_code == 503
    assert res.json()["server"] == "zresp"


def test_status_invalid(client: TestClient) -> None:
    res = client.get("/response/status/999")
    assert res.status_code == 400


def test_status_redirect_sets_location(client: TestClient) -> None:
    res = client.get("/response/status/301?location=/api/echo", follow_redirects=False)
    assert res.status_code == 301
    assert res.headers["location"] == "/api/echo"
    assert res.content == b""


def test_redirect_chain(client: TestClient) -> None:
    # 追従せず 1 ホップずつ確認
    res = client.get("/response/redirect/2", follow_redirects=False)
    assert res.status_code == 302
    assert res.headers["location"] == "/response/redirect/1?status=302"

    # 追従すると最終的に 200 + 終点ペイロード
    final = client.get("/response/redirect/2")
    assert final.status_code == 200
    assert "終点" in final.json()["note"]


def test_delay_zero(client: TestClient) -> None:
    res = client.get("/response/delay/0")
    assert res.status_code == 200
    assert res.json()["delay_seconds"] == 0


def test_cookies_set_multiple(client: TestClient) -> None:
    res = client.get("/response/cookies/set?a=1&b=2")
    assert res.status_code == 200
    assert res.cookies.get("a") == "1"
    assert res.cookies.get("b") == "2"


def test_cookie_with_attributes(client: TestClient) -> None:
    res = client.get("/response/cookie?name=sid&value=abc&samesite=Lax&httponly=true")
    assert res.status_code == 200
    set_cookie = [v.lower() for k, v in res.headers.multi_items() if k.lower() == "set-cookie"]
    assert any("sid=abc" in c and "samesite=lax" in c and "httponly" in c for c in set_cookie)


def test_cookie_invalid_samesite(client: TestClient) -> None:
    res = client.get("/response/cookie?name=sid&samesite=bogus")
    assert res.status_code == 400


def test_response_headers_applied(client: TestClient) -> None:
    res = client.get("/response/headers?X-Foo=bar&Cache-Control=no-store")
    assert res.status_code == 200
    assert res.headers["x-foo"] == "bar"
    assert res.headers["cache-control"] == "no-store"
    # Content-Type は保護され上書きされない
    assert res.headers["content-type"].startswith("application/json")
