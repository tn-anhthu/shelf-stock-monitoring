# Classification Benchmark Results — CLIP vs SigLIP2

**Date run:** 2026-07-18
**Dataset:** RPC (`benjamintli/retail-product-checkout`) — catalog from train split (single-object
exemplars), test crops from test split ground-truth boxes (checkout scenes).
**Subset size:** 105 crops, 16 categories,
48 catalog images.

## Results

| Model | Top-1 accuracy | Top-5 accuracy | Avg inference time/crop | Evaluated | Skipped (no catalog entry) |
|---|---|---|---|---|---|
| CLIP (openai/clip-vit-base-patch32) | 0.295 | 0.743 | 0.012s | 105 | 0 |
| SigLIP2 (google/siglip2-base-patch16-224) | 0.676 | 0.952 | 0.025s | 105 | 0 |

## Decision

**Model chosen: SigLIP2**

SigLIP2 outperforms CLIP substantially and unambiguously:
- Top-1 accuracy: SigLIP2 0.676 vs CLIP 0.295 (+38.1 percentage points)
- Top-5 accuracy: SigLIP2 0.952 vs CLIP 0.743 (+20.9 percentage points)

This decision follows the design spec's decision rule (see `docs/superpowers/specs/2026-07-17-classification-benchmark-design.md`, section "Ngưỡng quyết định"):
- "Model có top-1 accuracy cao hơn rõ rệt → chọn model đó cho Phase 2."

SigLIP2's top-1 accuracy is substantially higher, making it the clear choice. The performance gap is large enough that secondary considerations (inference time: CLIP 0.012s vs SigLIP2 0.025s) do not outweigh the accuracy advantage.

**Confidence in result:** Task 9's visual sanity check (already approved) inspected 5 sample crops and their CLIP predictions, confirming:
- All crops show real single products (not whole shelves or empty images)
- Predicted categories are semantically plausible and related to true categories
- No evidence of data pipeline bugs

The accuracy numbers are trustworthy, and SigLIP2 is recommended for Phase 2 integration.

**Caveat on absolute numbers:** these accuracy figures are measured against a 16-category subset of RPC's full 200-category catalog, and should not be assumed to hold at full 200-category scale — a larger, harder catalog will likely yield lower absolute top-1/top-5 accuracy for both models. The *relative* CLIP-vs-SigLIP2 ranking, not the absolute magnitudes, is the load-bearing conclusion here.

## Next spec

Phase 2 continuation: integrate SigLIP2 embedding retrieval + full catalog from RPC, then evaluate end-to-end performance on real Vietnamese retail checkout images (Future Work per design spec). If Phase 2 meets expected accuracy targets, proceed to Phase 3 (Depth multiplier) or finalize MVP; otherwise, reassess model selection or dataset augmentation.
