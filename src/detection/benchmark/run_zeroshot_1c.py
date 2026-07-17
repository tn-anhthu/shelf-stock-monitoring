"""Zero-shot open-vocabulary detection via Grounding DINO (transformers integration).

Model: IDEA-Research/grounding-dino-tiny (smallest variant, best fit for local M4 inference).
License: Apache-2.0, public, no gated access — no API key/token needed.
No training, no checkpoint download beyond the base model weights (~0.2B params).

Known risk: no benchmark for Grounding DINO on dense/overlapping retail shelves was
found during spec research (see docs/superpowers/specs/2026-07-17-detection-benchmark-design.md)
— this module's smoke test is genuinely the first data point for this use case, not a
confirmation of published results.

Smoke-tested 2026-07-17 on one real SKU-110K image (121 ground-truth boxes): the plan's
suggested default box_threshold=0.3 with prompt "product." returns a single box spanning
nearly the entire image (a degenerate whole-shelf detection, not per-product boxes) —
same with prompt "item.". Lowering box_threshold to 0.15 with "product." gave 41 boxes,
a much more plausible per-product count (still well under 121, an early signal that
zero-shot recall on this dense a scene may be limited). "product on shelf." at 0.3 gave
19 boxes — better than the degenerate case but worse than the lower threshold. Default
below reflects the best of these three empirically, not a published recommendation.

Requires MPS (Apple Silicon) or CPU. Run this on the M4 MacBook Pro.

Grounding DINO's mask-generation step uses `aten::_cummax_helper`, which has no MPS
kernel (confirmed 2026-07-17 on torch 2.5.1) — PYTORCH_ENABLE_MPS_FALLBACK=1 lets that
one op silently run on CPU while the rest of the model still runs on MPS. Set here
(not just as an ambient env var) so it applies regardless of how this module is invoked.
"""
import os

os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

from typing import List, Tuple

import torch
from PIL import Image
from transformers import AutoProcessor, AutoModelForZeroShotObjectDetection

from src.detection.benchmark.metrics import Box

MODEL_ID = "IDEA-Research/grounding-dino-tiny"


def load_model_1c() -> Tuple[AutoProcessor, AutoModelForZeroShotObjectDetection]:
    processor = AutoProcessor.from_pretrained(MODEL_ID)
    model = AutoModelForZeroShotObjectDetection.from_pretrained(MODEL_ID).to("mps")
    return processor, model


def detect_1c(
    processor,
    model,
    image: Image.Image,
    text_prompt: str = "product.",
    box_threshold: float = 0.15,
    text_threshold: float = 0.25,
) -> List[Box]:
    # Text queries must be lowercase and end with a dot (per the model's official
    # usage example on Hugging Face) — "product." already satisfies this.
    inputs = processor(images=image, text=text_prompt, return_tensors="pt").to("mps")
    with torch.no_grad():
        outputs = model(**inputs)

    results = processor.post_process_grounded_object_detection(
        outputs,
        inputs["input_ids"],
        threshold=box_threshold,  # renamed from box_threshold in transformers>=4.49
        text_threshold=text_threshold,
        target_sizes=[image.size[::-1]],
    )[0]

    boxes: List[Box] = [tuple(box.tolist()) for box in results["boxes"]]
    return boxes
