"""Zero-shot ROI-crop preprocessing: before YOLO, cut out neighboring shelves/
background that sit entirely inside the frame (docs/specs/mvp-design.md section 7,
"ROI-Crop Preprocessing"). Uses CLIPSeg (no training) to score "keep" prompts
(product, shelf) vs. "exclude" prompts (floor, ceiling, person) per pixel, lists
every connected component of (keep AND NOT exclude) above a minimum size, scores
each by center-bias + sharpness (2026-07-28, see DEFAULT_COMPONENT_WEIGHTS), and
crops to the winner's bounding box.

Mirrors the paper referenced in that spec entry (VISAPP 2026, "Retail Shelf
Monitoring Using Deep Hough Transform and Object Detection"):
    ROI = (product ∪ shelf) ∧ ¬(floor ∪ roof)

Known limit (2026-07-28, docs/log-figures/2026-07-28-roi-crop-component-selection.md):
on all 5 demo photos, at every threshold tested (0.35-0.80), the mask never
fragments into more than 1 candidate component -- target shelf and an adjacent
neighbor shelf fuse into a single blob whenever both sit at eye level with no
floor/ceiling gap between them in frame. Component-selection scoring only helps
when the mask actually produces >=2 separate candidates; it cannot split an
already-fused blob. 2/5 demo images (test2, test5) hit this and stay uncropped
by ROI-crop -- accepted as a residual-risk case per the spec, not fixed further.

Must never block a scan: if the mask is empty, too small, or has no reasonable
connected component, crop_to_roi returns the ORIGINAL image with a logged reason
instead of raising — see RoiCropResult.applied/reason.
"""
from dataclasses import dataclass
from typing import List, Optional, Tuple

import cv2
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image
from transformers import CLIPSegForImageSegmentation, CLIPSegProcessor

MODEL_ID = "CIDAS/clipseg-rd64-refined"

# "shelf edge" catches the metal shelf frame itself so a nearly-empty shelf still
# registers a keep signal even where no product currently sits on it.
KEEP_PROMPTS = ["product", "store shelf", "shelf edge"]
EXCLUDE_PROMPTS = ["floor", "ceiling", "person", "empty aisle background"]

# Benchmarked by sweeping {0.3..0.7} (step 0.05) on the 5 demo shelf photos,
# scoring each threshold's largest-connected-component bbox by IoU against a
# ground-truth ROI box per image (the employee's own manual crop, template-
# matched back into the original image) -- see
# docs/log-figures/2026-07-28-roi-crop-threshold-benchmark.md for the full sweep.
# 0.55 is the highest-avg-IoU threshold (0.795) with zero fallbacks across all
# 5 images; thresholds >=0.6 score higher on some individual images but collapse
# on the 2 most perspective-skewed photos (IoU down to 0.48-0.62) and 0.70
# triggers an outright fallback on one image -- not a guess, a measured tradeoff.
DEFAULT_THRESHOLD = 0.55

# Fallback trigger: the largest connected component must cover at least this
# fraction of the image, otherwise treat the mask as too unreliable to crop by.
DEFAULT_MIN_AREA_RATIO = 0.05


@dataclass
class RoiCropResult:
    image: Image.Image
    applied: bool
    reason: str
    bbox: Optional[Tuple[int, int, int, int]] = None


def load_model_clipseg() -> Tuple[CLIPSegForImageSegmentation, CLIPSegProcessor]:
    model = CLIPSegForImageSegmentation.from_pretrained(MODEL_ID)
    model.eval()
    processor = CLIPSegProcessor.from_pretrained(MODEL_ID)
    return model, processor


def predict_prompt_masks(
    model: CLIPSegForImageSegmentation,
    processor: CLIPSegProcessor,
    image: Image.Image,
    prompts: List[str],
) -> np.ndarray:
    """Returns per-prompt sigmoid probability maps, resized to image.size: (len(prompts), H, W)."""
    inputs = processor(text=prompts, images=[image] * len(prompts), padding=True, return_tensors="pt")
    with torch.no_grad():
        logits = model(**inputs).logits
    if logits.dim() == 2:  # a single prompt collapses the batch dim
        logits = logits.unsqueeze(0)
    probs = torch.sigmoid(logits)
    resized = F.interpolate(
        probs.unsqueeze(1), size=(image.height, image.width), mode="bilinear", align_corners=False
    ).squeeze(1)
    return resized.numpy()


def combine_keep_exclude(keep_probs: np.ndarray, exclude_probs: np.ndarray, threshold: float) -> np.ndarray:
    """keep_probs/exclude_probs: (num_prompts, H, W) -> boolean ROI mask (H, W)."""
    keep_mask = keep_probs.max(axis=0) >= threshold
    exclude_mask = exclude_probs.max(axis=0) >= threshold
    return keep_mask & ~exclude_mask


def largest_connected_component_bbox(
    mask: np.ndarray, min_area_ratio: float = DEFAULT_MIN_AREA_RATIO
) -> Optional[Tuple[int, int, int, int]]:
    """mask: boolean (H, W) -> (x1, y1, x2, y2) of the largest True-connected blob,
    or None if the mask is empty or the largest blob is under min_area_ratio of
    the image."""
    mask_u8 = mask.astype(np.uint8)
    num_labels, _labels, stats, _centroids = cv2.connectedComponentsWithStats(mask_u8, connectivity=8)
    if num_labels <= 1:  # only the background label (0) exists -> mask is all-False
        return None

    areas = stats[1:, cv2.CC_STAT_AREA]
    best_idx = int(np.argmax(areas)) + 1
    area = int(stats[best_idx, cv2.CC_STAT_AREA])
    total_area = mask.shape[0] * mask.shape[1]
    if total_area == 0 or area / total_area < min_area_ratio:
        return None

    x = int(stats[best_idx, cv2.CC_STAT_LEFT])
    y = int(stats[best_idx, cv2.CC_STAT_TOP])
    w = int(stats[best_idx, cv2.CC_STAT_WIDTH])
    h = int(stats[best_idx, cv2.CC_STAT_HEIGHT])
    return (x, y, x + w, y + h)


@dataclass
class ComponentCandidate:
    bbox: Tuple[int, int, int, int]
    area_ratio: float  # component area / total image area, in [0, 1]


def list_connected_components(mask: np.ndarray, min_area_ratio: float) -> List[ComponentCandidate]:
    """All connected blobs of `mask` at or above min_area_ratio, largest first.
    Unlike largest_connected_component_bbox this doesn't pick a winner -- it's
    the candidate list select_best_component scores over."""
    mask_u8 = mask.astype(np.uint8)
    num_labels, _labels, stats, _centroids = cv2.connectedComponentsWithStats(mask_u8, connectivity=8)
    total_area = mask.shape[0] * mask.shape[1]
    if total_area == 0:
        return []

    candidates = []
    for i in range(1, num_labels):  # label 0 is background
        area = int(stats[i, cv2.CC_STAT_AREA])
        ratio = area / total_area
        if ratio < min_area_ratio:
            continue
        x = int(stats[i, cv2.CC_STAT_LEFT])
        y = int(stats[i, cv2.CC_STAT_TOP])
        w = int(stats[i, cv2.CC_STAT_WIDTH])
        h = int(stats[i, cv2.CC_STAT_HEIGHT])
        candidates.append(ComponentCandidate(bbox=(x, y, x + w, y + h), area_ratio=ratio))

    candidates.sort(key=lambda c: c.area_ratio, reverse=True)
    return candidates


def center_bias_score(bbox: Tuple[int, int, int, int], image_size: Tuple[int, int]) -> float:
    """1.0 when bbox is centered on the image, decaying linearly to 0.0 at the
    farthest a bbox center can be (a corner). image_size = (width, height)."""
    width, height = image_size
    x1, y1, x2, y2 = bbox
    bbox_cx, bbox_cy = (x1 + x2) / 2, (y1 + y2) / 2
    img_cx, img_cy = width / 2, height / 2
    dist = ((bbox_cx - img_cx) ** 2 + (bbox_cy - img_cy) ** 2) ** 0.5
    max_dist = ((img_cx) ** 2 + (img_cy) ** 2) ** 0.5
    if max_dist == 0:
        return 1.0
    return 1.0 - min(dist / max_dist, 1.0)


def laplacian_sharpness(image: Image.Image, bbox: Tuple[int, int, int, int]) -> float:
    """Variance of the Laplacian inside bbox, as a focus proxy: in-focus regions
    have more high-frequency edge content than blurry/out-of-focus ones."""
    region = image.crop(tuple(int(v) for v in bbox)).convert("L")
    region_np = np.array(region)
    if region_np.size == 0:
        return 0.0
    return float(cv2.Laplacian(region_np, cv2.CV_64F).var())


# Equal weighting (1, 1, 1) on (area, center-bias, sharpness), each min-max
# normalized across the candidate set before combining. NOT benchmarked
# against the 5 demo photos like DEFAULT_THRESHOLD was -- see
# docs/log-figures/2026-07-28-roi-crop-component-selection.md: every one of the 5
# demo images produces exactly 1 candidate component at every threshold tested
# (0.35-0.80), so there is never more than one candidate to score/discriminate
# between, and no real multi-component example exists in the demo set to tune
# weights against. Equal weighting is a documented default, not a measured one
# -- validated only on synthetic multi-component cases (tests/pipeline/test_roi_crop.py).
DEFAULT_COMPONENT_WEIGHTS = (1.0, 1.0, 1.0)


def score_components(
    candidates: List[ComponentCandidate],
    image: Image.Image,
    weights: Tuple[float, float, float] = DEFAULT_COMPONENT_WEIGHTS,
) -> List[Tuple[ComponentCandidate, float]]:
    """Score each candidate by weighted (area, center-bias, sharpness), each
    min-max normalized across the candidate set so the 3 signals -- which live
    on unrelated scales (a ratio, a [0,1] score, a raw Laplacian variance) --
    are comparable before combining."""
    if not candidates:
        return []

    image_size = image.size
    areas = [c.area_ratio for c in candidates]
    centers = [center_bias_score(c.bbox, image_size) for c in candidates]
    sharps = [laplacian_sharpness(image, c.bbox) for c in candidates]

    def normalize(values: List[float]) -> List[float]:
        lo, hi = min(values), max(values)
        if hi - lo < 1e-9:  # all candidates tied on this signal -> it can't discriminate
            return [1.0] * len(values)
        return [(v - lo) / (hi - lo) for v in values]

    area_n, center_n, sharp_n = normalize(areas), normalize(centers), normalize(sharps)
    w_area, w_center, w_sharp = weights
    scores = [w_area * a + w_center * c + w_sharp * s for a, c, s in zip(area_n, center_n, sharp_n)]
    return list(zip(candidates, scores))


def select_best_component(
    candidates: List[ComponentCandidate],
    image: Image.Image,
    weights: Tuple[float, float, float] = DEFAULT_COMPONENT_WEIGHTS,
) -> Optional[ComponentCandidate]:
    scored = score_components(candidates, image, weights)
    if not scored:
        return None
    return max(scored, key=lambda pair: pair[1])[0]


def crop_to_roi_from_mask(
    image: Image.Image,
    mask: np.ndarray,
    min_area_ratio: float = DEFAULT_MIN_AREA_RATIO,
    weights: Tuple[float, float, float] = DEFAULT_COMPONENT_WEIGHTS,
) -> RoiCropResult:
    candidates = list_connected_components(mask, min_area_ratio)
    best = select_best_component(candidates, image, weights)
    if best is None:
        return RoiCropResult(image=image, applied=False, reason="mask_empty_or_too_small")
    return RoiCropResult(image=image.crop(best.bbox), applied=True, reason="ok", bbox=best.bbox)


def crop_to_roi(
    image: Image.Image,
    model: CLIPSegForImageSegmentation,
    processor: CLIPSegProcessor,
    keep_prompts: List[str] = KEEP_PROMPTS,
    exclude_prompts: List[str] = EXCLUDE_PROMPTS,
    threshold: float = DEFAULT_THRESHOLD,
    min_area_ratio: float = DEFAULT_MIN_AREA_RATIO,
    weights: Tuple[float, float, float] = DEFAULT_COMPONENT_WEIGHTS,
) -> RoiCropResult:
    """Full ROI-crop step: CLIPSeg keep/exclude prompts -> mask -> candidate
    components -> center-bias+sharpness-scored selection -> crop. Never raises
    -- any segmentation failure falls back to the original image with a reason,
    matching crop_to_roi_from_mask's contract for the mask-quality fallbacks."""
    try:
        keep_probs = predict_prompt_masks(model, processor, image, keep_prompts)
        exclude_probs = predict_prompt_masks(model, processor, image, exclude_prompts)
    except Exception as exc:  # segmentation must never block a scan
        return RoiCropResult(image=image, applied=False, reason=f"segmentation_error: {exc}")

    mask = combine_keep_exclude(keep_probs, exclude_probs, threshold)
    return crop_to_roi_from_mask(image, mask, min_area_ratio, weights)
