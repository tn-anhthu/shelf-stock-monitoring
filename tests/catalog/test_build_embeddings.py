import numpy as np
from PIL import Image

from src.catalog.build_embeddings import build_sku_embedding, save_embedding


def test_build_sku_embedding_averages_per_image_embeddings(tmp_path):
    img1 = Image.new("RGB", (4, 4))
    img2 = Image.new("RGB", (4, 4))
    img1_path = tmp_path / "1.jpg"
    img2_path = tmp_path / "2.jpg"
    img1.save(img1_path)
    img2.save(img2_path)

    def fake_embed(image):
        # distinguish by image size sum as a stand-in for "different embeddings"
        return np.array([1.0, 0.0]) if image is not None else np.array([0.0, 0.0])

    # fake_embed returns the same vector for both here on purpose to make the
    # averaging assertion exact and independent of image content
    embedding = build_sku_embedding([str(img1_path), str(img2_path)], embed_fn=fake_embed)
    assert np.allclose(embedding, np.array([1.0, 0.0]))


def test_build_sku_embedding_single_image(tmp_path):
    img_path = tmp_path / "1.jpg"
    Image.new("RGB", (4, 4)).save(img_path)

    embedding = build_sku_embedding([str(img_path)], embed_fn=lambda image: np.array([2.0, 4.0]))
    assert np.allclose(embedding, np.array([2.0, 4.0]))


def test_save_embedding_writes_npy_named_by_sku_id(tmp_path):
    embedding = np.array([1.0, 2.0, 3.0])
    path = save_embedding(embedding, "choco_pie_orion", str(tmp_path))
    assert path == str(tmp_path / "choco_pie_orion.npy")
    loaded = np.load(path)
    assert np.allclose(loaded, embedding)
