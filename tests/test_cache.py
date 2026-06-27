from fastapi.testclient import TestClient


def test_timestamp_sets_cache_control(client: TestClient) -> None:
    res = client.get("/cache/timestamp")
    assert res.status_code == 200
    assert res.headers["cache-control"] == "public, max-age=60"
    assert "uuid" in res.json()


def test_control_builds_directives(client: TestClient) -> None:
    res = client.get(
        "/cache/control?public=true&max_age=120&stale_while_revalidate=30&vary=Accept-Encoding"
    )
    assert res.status_code == 200
    cc = res.headers["cache-control"]
    assert "public" in cc
    assert "max-age=120" in cc
    assert "stale-while-revalidate=30" in cc
    assert res.headers["vary"] == "Accept-Encoding"


def test_etag_conditional_returns_304(client: TestClient) -> None:
    first = client.get("/cache/etag")
    assert first.status_code == 200
    etag = first.headers["etag"]

    second = client.get("/cache/etag", headers={"If-None-Match": etag})
    assert second.status_code == 304
    assert second.content == b""


def test_bytes_full_body(client: TestClient) -> None:
    res = client.get("/cache/bytes/1024")
    assert res.status_code == 200
    assert res.headers["accept-ranges"] == "bytes"
    assert len(res.content) == 1024
    # 決定的バイト列: byte 値 = position & 0xFF
    assert res.content[0] == 0
    assert res.content[255] == 255


def test_bytes_range_returns_206(client: TestClient) -> None:
    res = client.get("/cache/bytes/1kb", headers={"Range": "bytes=0-99"})
    assert res.status_code == 206
    assert res.headers["content-range"] == "bytes 0-99/1024"
    assert len(res.content) == 100


def test_bytes_invalid_size(client: TestClient) -> None:
    res = client.get("/cache/bytes/notasize")
    assert res.status_code == 400
