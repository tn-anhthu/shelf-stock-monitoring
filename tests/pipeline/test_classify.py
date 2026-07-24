import base64
import io
import json
import random
import time
from types import SimpleNamespace

import numpy as np
from PIL import Image

from src.pipeline.classify import (
    classify_crop,
    classify_crops_parallel,
    load_catalog_embeddings,
    rank_candidates,
    verify_with_llm,
)


FAKE_USAGE = SimpleNamespace(input_tokens=100, output_tokens=20)


class FakeMessages:
    def __init__(self, answer, reasoning=""):
        self.answer = answer
        self.reasoning = reasoning
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        text = json.dumps({"reasoning": self.reasoning, "answer": self.answer})
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)], usage=FAKE_USAGE)


class FakeLLMClient:
    def __init__(self, answer, reasoning=""):
        self.messages = FakeMessages(answer, reasoning)


def _candidate_sku_id(kwargs):
    """Pull the sku_id out of the (single) '- sku_id: name' candidate line
    sent in a request — used by fakes below that need to answer per-item."""
    text_blocks = [c["text"] for c in kwargs["messages"][0]["content"] if c["type"] == "text"]
    candidate_line = next(t for t in text_blocks if t.startswith("- "))
    return candidate_line[2:].split(":")[0]


class DelayedFakeMessages:
    def __init__(self, answer, delay=0.0):
        self.answer = answer
        self.delay = delay

    def create(self, **kwargs):
        time.sleep(self.delay)
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=json.dumps({"answer": self.answer}))], usage=FAKE_USAGE
        )


class DelayedFakeLLMClient:
    def __init__(self, answer, delay=0.0):
        self.messages = DelayedFakeMessages(answer, delay)


class EchoingFakeMessages:
    """Answers with whatever sku_id is the (single) candidate in the prompt,
    sleeping for a per-sku_id delay first — lets a test construct completion
    order deliberately out of sync with input order."""

    def __init__(self, delay_by_sku):
        self.delay_by_sku = delay_by_sku

    def create(self, **kwargs):
        sku_id = _candidate_sku_id(kwargs)
        time.sleep(self.delay_by_sku.get(sku_id, 0))
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=json.dumps({"answer": sku_id}))], usage=FAKE_USAGE
        )


class EchoingFakeLLMClient:
    def __init__(self, delay_by_sku):
        self.messages = EchoingFakeMessages(delay_by_sku)


class SometimesFailingFakeMessages:
    def __init__(self, failing_sku_id):
        self.failing_sku_id = failing_sku_id

    def create(self, **kwargs):
        sku_id = _candidate_sku_id(kwargs)
        if sku_id == self.failing_sku_id:
            raise RuntimeError("simulated network failure")
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=json.dumps({"answer": sku_id}))], usage=FAKE_USAGE
        )


class SometimesFailingFakeLLMClient:
    def __init__(self, failing_sku_id):
        self.messages = SometimesFailingFakeMessages(failing_sku_id)


CROP_IMAGE = Image.new("RGB", (10, 10))


def test_classify_crop_returns_llm_answer_and_its_own_ranked_score():
    # LLM picks the 2nd-best cosine match, not the top1 — score returned must
    # be that candidate's own similarity, not the top1 score.
    catalog_embeddings = [
        ("choco_pie_orion", np.array([1.0, 0.0])),
        ("coke_330", np.array([0.9, 0.1])),
    ]
    catalog_items = [
        {"sku_id": "choco_pie_orion", "name": "Chocopie"},
        {"sku_id": "coke_330", "name": "Coke"},
    ]
    llm_client = FakeLLMClient(answer="coke_330")

    sku_id, score, _reasoning, _usage, _ranked = classify_crop(
        CROP_IMAGE, np.array([1.0, 0.0]), catalog_embeddings, catalog_items, llm_client
    )

    assert sku_id == "coke_330"
    assert 0.0 < score < 1.0


def test_classify_crop_unknown_returns_none_with_top1_score():
    catalog_embeddings = [("choco_pie_orion", np.array([1.0, 0.0]))]
    catalog_items = [{"sku_id": "choco_pie_orion", "name": "Chocopie"}]
    llm_client = FakeLLMClient(answer="unknown")

    sku_id, score, _reasoning, _usage, _ranked = classify_crop(
        CROP_IMAGE, np.array([1.0, 0.0]), catalog_embeddings, catalog_items, llm_client
    )

    assert sku_id is None
    assert abs(score - 1.0) < 1e-6


def test_classify_crop_returns_llm_reasoning_alongside_answer():
    catalog_embeddings = [("choco_pie_orion", np.array([1.0, 0.0]))]
    catalog_items = [{"sku_id": "choco_pie_orion", "name": "Chocopie"}]
    llm_client = FakeLLMClient(answer="choco_pie_orion", reasoning="Logo và font khớp hoàn toàn")

    _sku_id, _score, reasoning, _usage, _ranked = classify_crop(
        CROP_IMAGE, np.array([1.0, 0.0]), catalog_embeddings, catalog_items, llm_client
    )

    assert reasoning == "Logo và font khớp hoàn toàn"


def test_classify_crop_none_embedding_returns_none_and_zero_without_calling_llm():
    catalog_embeddings = [("choco_pie_orion", np.array([1.0, 0.0]))]
    catalog_items = [{"sku_id": "choco_pie_orion", "name": "Chocopie"}]
    llm_client = FakeLLMClient(answer="choco_pie_orion")

    sku_id, score, reasoning, usage, ranked = classify_crop(CROP_IMAGE, None, catalog_embeddings, catalog_items, llm_client)

    assert sku_id is None
    assert score == 0.0
    assert reasoning == ""
    assert usage == {"input_tokens": 0, "output_tokens": 0}
    assert ranked == []
    assert llm_client.messages.calls == []


def test_classify_crop_empty_catalog_returns_none_and_zero_without_calling_llm():
    llm_client = FakeLLMClient(answer="unknown")

    sku_id, score, reasoning, usage, ranked = classify_crop(CROP_IMAGE, np.array([1.0, 0.0]), [], [], llm_client)

    assert sku_id is None
    assert score == 0.0
    assert reasoning == ""
    assert usage == {"input_tokens": 0, "output_tokens": 0}
    assert ranked == []
    assert llm_client.messages.calls == []


def test_classify_crop_limits_candidates_to_top_k():
    catalog_embeddings = [(f"sku_{i}", np.array([1.0 - i * 0.01, i * 0.01])) for i in range(10)]
    catalog_items = [{"sku_id": f"sku_{i}", "name": f"Product {i}"} for i in range(10)]
    llm_client = FakeLLMClient(answer="sku_0")

    classify_crop(CROP_IMAGE, np.array([1.0, 0.0]), catalog_embeddings, catalog_items, llm_client, top_k=3)

    content = llm_client.messages.calls[0]["messages"][0]["content"]
    candidate_lines = [c["text"] for c in content if c["type"] == "text" and c["text"].startswith("- sku_")]
    assert len(candidate_lines) == 3


def test_classify_crop_passes_images_dir_through_to_llm_escalation(tmp_path):
    sku_dir = tmp_path / "choco_pie_orion"
    sku_dir.mkdir()
    Image.new("RGB", (5, 5)).save(sku_dir / "1.jpg")

    catalog_embeddings = [("choco_pie_orion", np.array([1.0, 0.0]))]
    catalog_items = [{"sku_id": "choco_pie_orion", "name": "Chocopie"}]
    llm_client = FakeLLMClient(answer="choco_pie_orion")

    classify_crop(
        CROP_IMAGE,
        np.array([1.0, 0.0]),
        catalog_embeddings,
        catalog_items,
        llm_client,
        images_dir=str(tmp_path),
    )

    content = llm_client.messages.calls[0]["messages"][0]["content"]
    image_blocks = [c for c in content if c["type"] == "image"]
    assert len(image_blocks) == 2  # crop image + choco_pie_orion's reference image


def test_rank_candidates_returns_top_k_sorted_by_score():
    catalog_embeddings = [(f"sku_{i}", np.array([1.0 - i * 0.1, i * 0.1])) for i in range(5)]

    ranked = rank_candidates(np.array([1.0, 0.0]), catalog_embeddings, top_k=3)

    assert len(ranked) == 3
    assert [sku_id for sku_id, _ in ranked] == ["sku_0", "sku_1", "sku_2"]
    scores = [score for _, score in ranked]
    assert scores == sorted(scores, reverse=True)


def test_rank_candidates_empty_when_embedding_missing_or_catalog_empty():
    catalog_embeddings = [("choco_pie_orion", np.array([1.0, 0.0]))]

    assert rank_candidates(None, catalog_embeddings) == []
    assert rank_candidates(np.array([1.0, 0.0]), []) == []


def test_verify_with_llm_returns_none_and_zero_without_calling_llm_when_ranked_empty():
    llm_client = FakeLLMClient(answer="choco_pie_orion")

    sku_id, score, reasoning, usage, ranked = verify_with_llm(CROP_IMAGE, [], [], llm_client)

    assert sku_id is None
    assert score == 0.0
    assert reasoning == ""
    assert usage == {"input_tokens": 0, "output_tokens": 0}
    assert ranked == []
    assert llm_client.messages.calls == []


def test_verify_with_llm_returns_llm_reasoning_alongside_answer():
    llm_client = FakeLLMClient(answer="choco_pie_orion", reasoning="Trùng khớp logo")
    ranked = [("choco_pie_orion", 0.9)]
    catalog_items = [{"sku_id": "choco_pie_orion", "name": "Chocopie"}]

    _sku_id, _score, reasoning, _usage, _ranked = verify_with_llm(CROP_IMAGE, ranked, catalog_items, llm_client)

    assert reasoning == "Trùng khớp logo"


def test_verify_with_llm_returns_llm_token_usage():
    llm_client = FakeLLMClient(answer="choco_pie_orion")
    ranked = [("choco_pie_orion", 0.9)]
    catalog_items = [{"sku_id": "choco_pie_orion", "name": "Chocopie"}]

    _sku_id, _score, _reasoning, usage, _ranked = verify_with_llm(CROP_IMAGE, ranked, catalog_items, llm_client)

    assert usage == {"input_tokens": 100, "output_tokens": 20}


def test_classify_crops_parallel_runs_concurrently_not_sequentially():
    delay = 0.2
    n = 5
    llm_client = DelayedFakeLLMClient(answer="choco_pie_orion", delay=delay)
    catalog_items = [{"sku_id": "choco_pie_orion", "name": "Chocopie"}]
    items = [(CROP_IMAGE, [("choco_pie_orion", 0.9)]) for _ in range(n)]

    start = time.monotonic()
    results = classify_crops_parallel(items, catalog_items, llm_client, max_workers=n)
    elapsed = time.monotonic() - start

    assert len(results) == n
    assert all(sku_id == "choco_pie_orion" and score == 0.9 for sku_id, score, _reasoning, _usage, _ranked in results)
    # sequential would take n * delay (1.0s); parallel should be close to a
    # single delay, well under half the sequential time.
    assert elapsed < delay * n / 2


def test_classify_crops_parallel_preserves_order_despite_out_of_order_completion():
    # item 0 finishes LAST (longest delay), item 2 finishes FIRST (no delay).
    delay_by_sku = {"sku_0": 0.3, "sku_1": 0.15, "sku_2": 0.0}
    llm_client = EchoingFakeLLMClient(delay_by_sku)
    catalog_items = [{"sku_id": f"sku_{i}", "name": f"Product {i}"} for i in range(3)]
    items = [(CROP_IMAGE, [(f"sku_{i}", 0.9)]) for i in range(3)]

    results = classify_crops_parallel(items, catalog_items, llm_client, max_workers=3)

    assert [sku_id for sku_id, _score, _reasoning, _usage, _ranked in results] == ["sku_0", "sku_1", "sku_2"]


def _fingerprint_color(i):
    # Widely-separated per-index colors across all 3 channels, decoded via
    # nearest-neighbor match rather than inverting a formula -- a naive
    # single-channel/tight-spacing encoding was tried first and produced
    # false-positive "mismatches" purely from ordinary JPEG lossy-compression
    # rounding on a solid-color block, not any real bug. Multipliers are
    # coprime with 256 and with each other to spread N<=60 indices far apart
    # in RGB space, tolerating that rounding noise.
    return ((i * 97) % 256, (i * 151) % 256, (i * 211) % 256)


class FingerprintingMessages:
    """Decodes the crop image actually embedded in the request (the first
    image content block, per llm_escalation.py's ordering) via nearest-color
    match against every known target, and answers with THAT recovered
    index's sku_id -- proving the image bytes classify_crops_parallel/
    escalate_to_llm sent for this call really are this item's own crop, not
    some other item's (which downstream verify_with_llm can only turn into a
    real, non-crashing answer if the candidate list handed to the same call
    also names that same sku_id)."""

    def __init__(self, n):
        self.targets = [_fingerprint_color(i) for i in range(n)]

    def _nearest_index(self, rgb):
        return min(range(len(self.targets)), key=lambda i: sum((a - b) ** 2 for a, b in zip(rgb, self.targets[i])))

    def create(self, **kwargs):
        time.sleep(random.uniform(0, 0.03))  # force interleaved/out-of-order completion
        content = kwargs["messages"][0]["content"]
        first_image = next(c for c in content if c["type"] == "image")
        raw = base64.standard_b64decode(first_image["source"]["data"])
        decoded = Image.open(io.BytesIO(raw)).convert("RGB")
        recovered_index = self._nearest_index(decoded.getpixel((0, 0)))
        text = json.dumps({"reasoning": "fingerprint echo", "answer": f"sku_{recovered_index}"})
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)], usage=FAKE_USAGE)


class FingerprintingLLMClient:
    def __init__(self, n):
        self.messages = FingerprintingMessages(n)


def test_classify_crops_parallel_positional_alignment_survives_interspersed_skips():
    # Regression test for a suspected "index i gets index i+1's crop/candidates"
    # bug in classify_crops_parallel. Each real item gets its own distinct
    # fingerprinted crop image (see _fingerprint_color) plus its own index-
    # specific candidate sku_id; a few items are degenerate (cropped=None,
    # ranked=[]) interspersed among them, mirroring what
    # scripts/visualize_scan_e2e.py builds when crop_box() returns None for a
    # box -- to check that a skipped item does NOT shift later items out of
    # position in the returned list.
    n = 20
    skip_indices = {3, 7, 14}

    items = []
    for i in range(n):
        if i in skip_indices:
            items.append((None, []))
        else:
            items.append((Image.new("RGB", (60, 90), color=_fingerprint_color(i)), [(f"sku_{i}", 0.9)]))

    catalog_items = [{"sku_id": f"sku_{i}", "name": f"Product {i}"} for i in range(n)]
    llm_client = FingerprintingLLMClient(n)

    results = classify_crops_parallel(items, catalog_items, llm_client, max_workers=8)

    assert len(results) == n
    for i, (sku_id, score, _reasoning, _usage, _ranked) in enumerate(results):
        if i in skip_indices:
            assert sku_id is None and score == 0.0, f"index {i} (skipped) got {sku_id!r}"
        else:
            assert sku_id == f"sku_{i}", f"index {i} expected sku_{i}, got {sku_id!r}"


def test_classify_crops_parallel_isolates_failures_per_item(capsys):
    llm_client = SometimesFailingFakeLLMClient(failing_sku_id="sku_1")
    catalog_items = [{"sku_id": f"sku_{i}", "name": f"Product {i}"} for i in range(3)]
    items = [(CROP_IMAGE, [(f"sku_{i}", 0.9)]) for i in range(3)]

    results = classify_crops_parallel(items, catalog_items, llm_client, max_workers=3)

    assert results[0][:2] == ("sku_0", 0.9)
    assert results[1][:2] == (None, 0.9)  # LLM call failed -> falls back to top1 score, not None/crash
    assert results[2][:2] == ("sku_2", 0.9)
    # the failure's reasoning field should explain what happened, for debugging in review.xlsx
    assert "simulated network failure" in results[1][2]
    # a failed call's usage isn't recoverable -> excluded from the cost estimate as zero
    assert results[1][3] == {"input_tokens": 0, "output_tokens": 0}
    # failed call still surfaces its own shortlist
    assert results[1][4] == [("sku_1", 0.9)]

    captured = capsys.readouterr()
    assert "sku_1" not in "".join(sku_id or "" for sku_id, _score, _reasoning, _usage, _ranked in results)
    assert "simulated network failure" in captured.out


def test_load_catalog_embeddings_reads_npy_files(tmp_path):
    embedding = np.array([1.0, 2.0, 3.0])
    npy_path = tmp_path / "choco_pie_orion.npy"
    np.save(npy_path, embedding)

    catalog_items = [{"sku_id": "choco_pie_orion", "embedding_path": str(npy_path)}]
    result = load_catalog_embeddings(catalog_items)

    assert len(result) == 1
    assert result[0][0] == "choco_pie_orion"
    assert np.allclose(result[0][1], embedding)


def test_classify_crop_returns_full_ranked_candidate_list():
    catalog_embeddings = [(f"sku_{i}", np.array([1.0 - i * 0.1, i * 0.1])) for i in range(5)]
    catalog_items = [{"sku_id": f"sku_{i}", "name": f"Product {i}"} for i in range(5)]
    llm_client = FakeLLMClient(answer="sku_0")

    _sku_id, _score, _reasoning, _usage, ranked = classify_crop(
        CROP_IMAGE, np.array([1.0, 0.0]), catalog_embeddings, catalog_items, llm_client, top_k=3
    )

    assert [sku_id for sku_id, _score in ranked] == ["sku_0", "sku_1", "sku_2"]


def test_verify_with_llm_returns_the_ranked_list_it_was_given():
    ranked = [("choco_pie_orion", 0.9), ("coke_330", 0.5)]
    catalog_items = [
        {"sku_id": "choco_pie_orion", "name": "Chocopie"},
        {"sku_id": "coke_330", "name": "Coke"},
    ]
    llm_client = FakeLLMClient(answer="coke_330")

    *_rest, returned_ranked = verify_with_llm(CROP_IMAGE, ranked, catalog_items, llm_client)

    assert returned_ranked == ranked


def test_classify_crops_parallel_returns_each_items_ranked_list():
    catalog_items = [{"sku_id": "choco_pie_orion", "name": "Chocopie"}]
    llm_client = FakeLLMClient(answer="choco_pie_orion")
    ranked_a = [("choco_pie_orion", 0.9)]
    ranked_b = [("choco_pie_orion", 0.7)]
    items = [(CROP_IMAGE, ranked_a), (CROP_IMAGE, ranked_b)]

    results = classify_crops_parallel(items, catalog_items, llm_client, max_workers=2)

    assert results[0][4] == ranked_a
    assert results[1][4] == ranked_b
