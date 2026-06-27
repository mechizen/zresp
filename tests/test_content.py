from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image


def test_sample_html(client: TestClient) -> None:
    res = client.get("/content/sample.html")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/html")
    assert "sample" in res.text.lower()


def test_sample_json(client: TestClient) -> None:
    res = client.get("/content/sample.json")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("application/json")
    assert res.json()["server"] == "zresp"


def test_sample_png_signature(client: TestClient) -> None:
    res = client.get("/content/sample.png")
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/png"
    assert res.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_sample_pdf_is_valid(client: TestClient) -> None:
    res = client.get("/content/sample.pdf")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert res.content.startswith(b"%PDF-")
    assert b"%%EOF" in res.content


def test_sample_binary_without_bundle_returns_404(client: TestClient) -> None:
    res = client.get("/content/sample.mp4")
    assert res.status_code == 404
    assert "hint" in res.json()


def test_sample_unsupported_extension(client: TestClient) -> None:
    res = client.get("/content/sample.foobar")
    assert res.status_code == 400


def test_dynamic_image_dimensions(client: TestClient) -> None:
    res = client.get("/content/image/123x45.png")
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/png"
    img = Image.open(BytesIO(res.content))
    assert img.size == (123, 45)


def test_dynamic_image_jpeg(client: TestClient) -> None:
    res = client.get("/content/image/64x64.jpg")
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/jpeg"


def test_dynamic_image_invalid_dims(client: TestClient) -> None:
    res = client.get("/content/image/abc.png")
    assert res.status_code == 400
