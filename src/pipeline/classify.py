"""Match a shelf crop's embedding against the catalog's stored embeddings to
get a top_k shortlist by cosine similarity (reusing the retrieval logic from
src/classification/benchmark/retrieve.py — category_id there is a plain dict
key, so sku_id strings work identically at runtime), then have Claude verify
which shortlisted SKU (or none) the actual crop image matches.

The LLM verifies every crop with a valid embedding, not just close top1/top2
calls — src/pipeline/llm_escalation.py's docstring covers why cosine
similarity alone isn't trustworthy enough to skip this for confident-looking
scores. images_dir is forwarded to escalate_to_llm so it can show each
candidate's own catalog reference photo instead of relying on its name alone
— see that module's docstring for the BOSS Cà Phê misclassification this
was added to fix.

Split into two phases so callers (src/pipeline/scan.py::run_scan,
scripts/visualize_scan_e2e.py) can run them differently: rank_candidates is
cheap cosine math sharing the SigLIP2 model, so it stays sequential per box;
verify_with_llm is a network call, so classify_crops_parallel runs it
concurrently across boxes via a thread pool (I/O-bound, not GPU/CPU-bound —
threading is enough, no need for multiprocessing). classify_crop remains a
thin wrapper doing both phases for one box, so existing single-box callers
don't need to change.
"""
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Tuple

import numpy as np
from PIL import Image

from src.classification.benchmark.retrieve import cosine_similarity
from src.pipeline.llm_escalation import escalate_to_llm, escalate_to_llm_gemini


def load_catalog_embeddings(catalog_items: List[Dict]) -> List[Tuple[str, np.ndarray]]:
    return [(item["sku_id"], np.load(item["embedding_path"])) for item in catalog_items]


def rank_candidates(
    crop_embedding: Optional[np.ndarray],
    catalog_embeddings: List[Tuple[str, np.ndarray]],
    top_k: int = 5,
) -> List[Tuple[str, float]]:
    if crop_embedding is None or not catalog_embeddings:
        return []
    scored = [(sku_id, cosine_similarity(crop_embedding, embedding)) for sku_id, embedding in catalog_embeddings]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored[:top_k]


ZERO_USAGE = {"input_tokens": 0, "output_tokens": 0}


def _escalate(llm_client, crop_image, candidates, images_dir):
    """Dispatches to the LLM provider named by the LLM_PROVIDER env var
    (anthropic | gemini, default anthropic -- see .env.example). The caller
    is responsible for constructing an llm_client matching that same
    provider (anthropic.Anthropic vs. google.genai.Client); this function
    only decides which escalate_to_llm* function's shape to call it with."""
    provider = os.environ.get("LLM_PROVIDER", "anthropic")
    if provider == "gemini":
        return escalate_to_llm_gemini(llm_client, crop_image, candidates, images_dir=images_dir)
    return escalate_to_llm(llm_client, crop_image, candidates, images_dir=images_dir)


def verify_with_llm(
    crop_image: Optional[Image.Image],
    ranked: List[Tuple[str, float]],
    catalog_items: List[Dict],
    llm_client,
    images_dir: str = "data/catalog/images",
) -> Tuple[Optional[str], float, str, Dict[str, int], List[Tuple[str, float]]]:
    """Returns (sku_id, score, reasoning, usage, ranked). reasoning is escalate_to_llm's
    own explanation for the answer — for human review/debugging (see
    data/scan_viz/review.xlsx's llm_reasoning column), not used in any
    decision here. usage is escalate_to_llm's token count, for cost tracking
    in scripts/visualize_scan_e2e.py. ranked is the same top-k (sku_id,
    score) shortlist passed in as the `ranked` argument — returned so
    callers can log which SKUs SigLIP2 actually shortlisted for the LLM
    (see data/scan_viz/review.xlsx's top5_candidates column), to separate
    retrieval failures (true SKU never reached the shortlist) from
    reasoning failures (it did, but the LLM still picked wrong)."""
    if not ranked:
        return None, 0.0, "", dict(ZERO_USAGE), []

    names_by_sku = {item["sku_id"]: item.get("name", item["sku_id"]) for item in catalog_items}
    candidates = [(sku_id, names_by_sku.get(sku_id, sku_id)) for sku_id, _ in ranked]

    answer, reasoning, usage = _escalate(llm_client, crop_image, candidates, images_dir)

    if answer == "unknown":
        return None, ranked[0][1], reasoning, usage, ranked
    matched_score = next(score for sku_id, score in ranked if sku_id == answer)
    return answer, matched_score, reasoning, usage, ranked


def classify_crop(
    crop_image: Optional[Image.Image],
    crop_embedding: Optional[np.ndarray],
    catalog_embeddings: List[Tuple[str, np.ndarray]],
    catalog_items: List[Dict],
    llm_client,
    top_k: int = 5,
    images_dir: str = "data/catalog/images",
) -> Tuple[Optional[str], float, str, Dict[str, int], List[Tuple[str, float]]]:
    ranked = rank_candidates(crop_embedding, catalog_embeddings, top_k=top_k)
    return verify_with_llm(crop_image, ranked, catalog_items, llm_client, images_dir=images_dir)


def classify_crops_parallel(
    items: List[Tuple[Optional[Image.Image], List[Tuple[str, float]]]],
    catalog_items: List[Dict],
    llm_client,
    images_dir: str = "data/catalog/images",
    max_workers: int = 10,
) -> List[Tuple[Optional[str], float, str, Dict[str, int], List[Tuple[str, float]]]]:
    """Run verify_with_llm for every (crop_image, ranked) pair concurrently.

    Preserves input order regardless of which thread finishes first (relies
    on ThreadPoolExecutor.map, which yields results in call order even though
    the calls themselves run concurrently) — callers depend on this to line
    detections back up with their original box index. One item's LLM call
    failing (timeout, rate limit, malformed JSON surviving escalate_to_llm's
    own retries) never crashes the batch: it's logged and that item falls
    back to (None, top1_score, <error note>, zero usage, its own ranked
    shortlist) instead — a failed call's actual token usage (if any was
    billed before the failure) isn't recoverable here, so it's excluded from
    the cost estimate rather than guessed. llm_client is assumed thread-safe
    for concurrent calls, same as any standard HTTP client
    (anthropic.Anthropic is, via its underlying httpx connection pool).
    """

    def _run(item):
        crop_image, ranked = item
        try:
            return verify_with_llm(crop_image, ranked, catalog_items, llm_client, images_dir=images_dir)
        except Exception as e:
            fallback_score = ranked[0][1] if ranked else 0.0
            note = f"LLM verification failed: {e!r}"
            print(f"classify_crops_parallel: {note}, falling back to unknown (score={fallback_score:.3f})")
            return None, fallback_score, note, dict(ZERO_USAGE), ranked

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        return list(executor.map(_run, items))
