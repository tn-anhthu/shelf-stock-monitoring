import numpy as np

from src.pipeline.classify import classify_crop, load_catalog_embeddings


def test_classify_crop_returns_best_matching_sku_and_score():
    catalog_embeddings = [
        ("choco_pie_orion", np.array([1.0, 0.0])),
        ("coke_330", np.array([0.0, 1.0])),
    ]
    sku_id, score = classify_crop(np.array([0.9, 0.1]), catalog_embeddings)
    assert sku_id == "choco_pie_orion"
    assert 0.9 < score <= 1.0


def test_classify_crop_empty_catalog_returns_none_and_zero():
    sku_id, score = classify_crop(np.array([1.0, 0.0]), [])
    assert sku_id is None
    assert score == 0.0


def test_load_catalog_embeddings_reads_npy_files(tmp_path):
    embedding = np.array([1.0, 2.0, 3.0])
    npy_path = tmp_path / "choco_pie_orion.npy"
    np.save(npy_path, embedding)

    catalog_items = [{"sku_id": "choco_pie_orion", "embedding_path": str(npy_path)}]
    result = load_catalog_embeddings(catalog_items)

    assert len(result) == 1
    assert result[0][0] == "choco_pie_orion"
    assert np.allclose(result[0][1], embedding)
