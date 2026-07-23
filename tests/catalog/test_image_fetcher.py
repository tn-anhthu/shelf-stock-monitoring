import requests

from src.catalog.image_fetcher import default_http_get, fetch_sku_images


class FakeResponse:
    def __init__(self, content: bytes):
        self.content = content

    def raise_for_status(self):
        pass


def test_fetch_sku_images_writes_numbered_files(tmp_path):
    calls = []

    def fake_get(url, timeout=10):
        calls.append(url)
        return FakeResponse(b"fake-image-bytes-" + url.encode())

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
    assert (tmp_path / "choco_pie_orion" / "1.jpg").read_bytes() == b"fake-image-bytes-https://example.com/a.jpg"
    assert (tmp_path / "choco_pie_orion" / "2.jpg").read_bytes() == b"fake-image-bytes-https://example.com/b.jpg"
    assert calls == ["https://example.com/a.jpg", "https://example.com/b.jpg"]


def test_fetch_sku_images_empty_urls_returns_empty_list(tmp_path):
    paths = fetch_sku_images("some_sku", [], str(tmp_path), http_get=lambda url, timeout=10: None)
    assert paths == []


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
