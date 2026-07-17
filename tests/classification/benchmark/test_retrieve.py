import numpy as np

from src.classification.benchmark.retrieve import cosine_similarity, rank_categories


def test_cosine_similarity_identical_vectors_returns_one():
    v = np.array([1.0, 2.0, 3.0])
    assert abs(cosine_similarity(v, v) - 1.0) < 1e-9


def test_cosine_similarity_orthogonal_vectors_returns_zero():
    a = np.array([1.0, 0.0])
    b = np.array([0.0, 1.0])
    assert abs(cosine_similarity(a, b) - 0.0) < 1e-9


def test_cosine_similarity_opposite_vectors_returns_negative_one():
    a = np.array([1.0, 0.0])
    b = np.array([-1.0, 0.0])
    assert abs(cosine_similarity(a, b) - (-1.0)) < 1e-9


def test_rank_categories_orders_by_descending_similarity():
    query = np.array([1.0, 0.0])
    catalog = [
        (10, np.array([0.0, 1.0])),   # orthogonal -> similarity 0
        (20, np.array([1.0, 0.0])),   # identical -> similarity 1
        (30, np.array([0.9, 0.1])),   # close -> similarity high but < 1
    ]
    ranking = rank_categories(query, catalog)
    assert ranking == [20, 30, 10]


def test_rank_categories_takes_max_similarity_per_category_not_average():
    query = np.array([1.0, 0.0])
    catalog = [
        (10, np.array([1.0, 0.0])),    # category 10, exemplar A: identical -> sim 1
        (10, np.array([0.0, 1.0])),    # category 10, exemplar B: orthogonal -> sim 0
        (20, np.array([0.7, 0.7])),    # category 20, only exemplar: sim ~0.707
    ]
    # category 10's BEST exemplar (sim=1) beats category 20's only exemplar (sim~0.707)
    ranking = rank_categories(query, catalog)
    assert ranking[0] == 10


def test_rank_categories_empty_catalog_returns_empty():
    assert rank_categories(np.array([1.0, 0.0]), []) == []
