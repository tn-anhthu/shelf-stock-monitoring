import io

import requests
from PIL import Image

from src.catalog.image_fetcher import default_http_get, fetch_sku_images


class FakeResponse:
    def __init__(self, content: bytes):
        self.content = content

    def raise_for_status(self):
        pass


def _jpeg_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (4, 4)).save(buf, format="JPEG")
    return buf.getvalue()


def test_fetch_sku_images_writes_numbered_files(tmp_path):
    calls = []

    def fake_get(url, timeout=10):
        calls.append(url)
        return FakeResponse(_jpeg_bytes())

    paths = fetch_sku_images(
        "choco_pie_orion",
        ["https://example.com/a.jpg", "https://example.com/b.jpg"],
        str(tmp_path),
        http_get=fake_get,
    )

    assert paths == [
        str(tmp_path / "choco_pie_orion" / "1.jpg"),
        str(tmp_path / "choco_pie_orion" / "2.jpg"),
    ]
    assert (tmp_path / "choco_pie_orion" / "1.jpg").read_bytes() == _jpeg_bytes()
    assert (tmp_path / "choco_pie_orion" / "2.jpg").read_bytes() == _jpeg_bytes()
    assert calls == ["https://example.com/a.jpg", "https://example.com/b.jpg"]


def test_fetch_sku_images_skips_url_returning_non_image_content(tmp_path):
    def fake_get(url, timeout=10):
        return FakeResponse(b"<!DOCTYPE html><html>not an image</html>")

    paths = fetch_sku_images(
        "haohao_prem_bosate",
        ["https://cooponline.vn/some-product-page", "https://example.com/real.jpg"],
        str(tmp_path),
        http_get=lambda url, timeout=10: FakeResponse(_jpeg_bytes()) if "real" in url else fake_get(url),
    )

    assert paths == [str(tmp_path / "haohao_prem_bosate" / "2.jpg")]
    assert not (tmp_path / "haohao_prem_bosate" / "1.jpg").exists()


def test_fetch_sku_images_skips_url_on_persistent_fetch_error(tmp_path):
    def always_fails(url, timeout=10):
        raise requests.exceptions.SSLError("cert chain broken")

    paths = fetch_sku_images(
        "some_sku",
        ["https://broken-cert.example.com/a.jpg"],
        str(tmp_path),
        http_get=always_fails,
    )

    assert paths == []
    assert not (tmp_path / "some_sku" / "1.jpg").exists()


def test_fetch_sku_images_empty_urls_returns_empty_list(tmp_path):
    paths = fetch_sku_images("some_sku", [], str(tmp_path), http_get=lambda url, timeout=10: None)
    assert paths == []


def test_fetch_sku_images_skips_download_when_file_already_exists(tmp_path):
    sku_dir = tmp_path / "yomost_nho"
    sku_dir.mkdir(parents=True)
    (sku_dir / "1.jpg").write_bytes(b"manually-added-image")

    def fail_if_called(url, timeout=10):
        raise AssertionError("http_get should not be called when the image file already exists")

    paths = fetch_sku_images(
        "yomost_nho",
        ["https://www.dutchlady.com.vn/sites/default/files/2026-03/Nho.png"],
        str(tmp_path),
        http_get=fail_if_called,
    )

    assert paths == [str(sku_dir / "1.jpg")]
    assert (sku_dir / "1.jpg").read_bytes() == b"manually-added-image"


def test_default_http_get_sends_referer_matching_url_domain():
    captured = {}

    def fake_get(url, headers=None, timeout=10):
        captured["headers"] = headers
        return FakeResponse(b"ok")

    default_http_get("https://cdn.example.com/path/img.jpg", _get=fake_get)

    assert captured["headers"]["Referer"] == "https://cdn.example.com/"
    assert "User-Agent" in captured["headers"]


def test_default_http_get_retries_after_transient_failure_then_succeeds():
    calls = []

    def flaky_get(url, headers=None, timeout=10):
        calls.append(url)
        if len(calls) == 1:
            raise requests.exceptions.RequestException("boom")
        return FakeResponse(b"ok")

    response = default_http_get("https://example.com/a.jpg", _get=flaky_get)

    assert len(calls) == 2
    assert response.content == b"ok"


def test_default_http_get_raises_last_exception_after_exhausting_retries():
    calls = []

    def always_fails(url, headers=None, timeout=10):
        calls.append(url)
        raise requests.exceptions.RequestException("boom")

    try:
        default_http_get("https://example.com/a.jpg", max_retries=2, _get=always_fails)
        raised = False
    except requests.exceptions.RequestException:
        raised = True

    assert raised
    assert len(calls) == 3
