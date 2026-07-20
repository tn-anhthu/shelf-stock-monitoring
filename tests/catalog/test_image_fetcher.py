from src.catalog.image_fetcher import fetch_sku_images


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
