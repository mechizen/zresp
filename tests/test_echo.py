from fastapi.testclient import TestClient


def _category(payload: dict, cid: str) -> dict | None:
    for cat in payload["categories"]:
        if cat["id"] == cid:
            return cat
    return None


def test_healthz(client: TestClient) -> None:
    res = client.get("/healthz")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_echo_classifies_cloudflare_headers(client: TestClient) -> None:
    res = client.get(
        "/api/echo",
        headers={
            "CF-Connecting-IP": "203.0.113.7",
            "CF-Ray": "8abc1234-NRT",
            "CF-Bot-Score": "12",
            "X-Forwarded-For": "203.0.113.7, 10.0.0.1",
        },
    )
    assert res.status_code == 200
    body = res.json()

    assert body["cf_ray"] == "8abc1234-NRT"
    assert body["client_ip"]["best_guess"] == "203.0.113.7"
    assert body["client_ip"]["x_forwarded_for_chain"] == ["203.0.113.7", "10.0.0.1"]

    # HTTP/2 ではヘッダ名は小文字化される (TestClient/Cloudflare 経由とも同様)
    conn = _category(body, "cloudflare_connection")
    assert conn is not None
    assert conn["headers"].get("cf-connecting-ip") == "203.0.113.7"

    bot = _category(body, "bot_management")
    assert bot is not None
    assert bot["headers"].get("cf-bot-score") == "12"


def test_echo_parses_json_body(client: TestClient) -> None:
    res = client.post("/api/echo", json={"hello": "world", "n": 1})
    assert res.status_code == 200
    body = res.json()
    assert body["method"] == "POST"
    assert body["body"]["json_value"] == {"hello": "world", "n": 1}


def test_inspect_html(client: TestClient) -> None:
    res = client.get("/inspect", headers={"CF-Ray": "ray-123"})
    assert res.status_code == 200
    assert "Request Inspector" in res.text
    assert "ray-123" in res.text


def test_echo_txt_format(client: TestClient) -> None:
    res = client.get("/api/echo.txt", headers={"CF-Ray": "ray-9"})
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/plain")
    assert "method:" in res.text
    assert "ray-9" in res.text


def test_echo_xml_format(client: TestClient) -> None:
    res = client.get("/api/echo.xml")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("application/xml")
    assert "<request>" in res.text


def test_echo_html_redirects_to_inspect(client: TestClient) -> None:
    res = client.get("/api/echo.html", follow_redirects=False)
    assert res.status_code in (302, 307)
    assert res.headers["location"] == "/inspect"


def test_echo_unsupported_format(client: TestClient) -> None:
    res = client.get("/api/echo.foo")
    assert res.status_code == 400
