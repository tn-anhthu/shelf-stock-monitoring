import numpy as np
from PIL import Image, ImageDraw

from src.pipeline.roi_crop import (
    ComponentCandidate,
    center_bias_score,
    combine_keep_exclude,
    crop_to_roi_from_mask,
    laplacian_sharpness,
    largest_connected_component_bbox,
    list_connected_components,
    select_best_component,
)


def test_largest_connected_component_bbox_picks_biggest_blob():
    mask = np.zeros((100, 100), dtype=bool)
    mask[10:20, 10:20] = True  # small blob, 100px
    mask[40:90, 40:90] = True  # big blob, 2500px
    assert largest_connected_component_bbox(mask, min_area_ratio=0.01) == (40, 40, 90, 90)


def test_largest_connected_component_bbox_returns_none_for_empty_mask():
    mask = np.zeros((100, 100), dtype=bool)
    assert largest_connected_component_bbox(mask, min_area_ratio=0.01) is None


def test_largest_connected_component_bbox_returns_none_below_min_area_ratio():
    mask = np.zeros((100, 100), dtype=bool)
    mask[0:5, 0:5] = True  # 25px out of 10000 = 0.25%, below a 5% floor
    assert largest_connected_component_bbox(mask, min_area_ratio=0.05) is None


def test_combine_keep_exclude_keeps_only_pixels_above_threshold_and_not_excluded():
    # 2 keep prompts, 2 exclude prompts, 4x4 image
    keep_probs = np.zeros((2, 4, 4))
    keep_probs[0, 0:2, 0:2] = 0.9  # top-left corner: strong "product" signal
    keep_probs[1, 2:4, 2:4] = 0.9  # bottom-right corner: strong "shelf" signal
    exclude_probs = np.zeros((2, 4, 4))
    exclude_probs[0, 2:4, 2:4] = 0.9  # "floor" overlaps the bottom-right "shelf" hit

    mask = combine_keep_exclude(keep_probs, exclude_probs, threshold=0.5)

    assert mask[0:2, 0:2].all()  # kept: strong keep signal, no exclude overlap
    assert not mask[2:4, 2:4].any()  # dropped: keep signal cancelled by exclude
    assert not mask[0:2, 2:4].any()  # never had a keep signal


def test_crop_to_roi_from_mask_applies_bbox_crop():
    image = Image.new("RGB", (100, 100), (255, 0, 0))
    mask = np.zeros((100, 100), dtype=bool)
    mask[20:80, 30:70] = True

    result = crop_to_roi_from_mask(image, mask, min_area_ratio=0.01)

    assert result.applied is True
    assert result.reason == "ok"
    assert result.bbox == (30, 20, 70, 80)
    assert result.image.size == (40, 60)


def test_crop_to_roi_from_mask_falls_back_to_original_on_empty_mask():
    image = Image.new("RGB", (100, 100), (255, 0, 0))
    mask = np.zeros((100, 100), dtype=bool)

    result = crop_to_roi_from_mask(image, mask, min_area_ratio=0.01)

    assert result.applied is False
    assert result.reason == "mask_empty_or_too_small"
    assert result.image is image
    assert result.bbox is None


def test_crop_to_roi_from_mask_falls_back_when_component_too_small():
    image = Image.new("RGB", (100, 100), (255, 0, 0))
    mask = np.zeros((100, 100), dtype=bool)
    mask[0:3, 0:3] = True  # 9px out of 10000 = 0.09%, below the 5% default floor

    result = crop_to_roi_from_mask(image, mask, min_area_ratio=0.05)

    assert result.applied is False
    assert result.reason == "mask_empty_or_too_small"
    assert result.image is image


# --- Component-selection scoring (2026-07-28c): center-bias + sharpness, added
# to disambiguate multiple candidate components when the mask itself doesn't
# fuse target-shelf and neighbor-shelf into one blob (see roi_crop.py module
# docstring for why this never actually fires on the 5 demo photos -- these
# tests validate the mechanism on synthetic multi-component masks instead). ---


def test_list_connected_components_returns_every_blob_above_floor_sorted_by_area():
    mask = np.zeros((100, 100), dtype=bool)
    mask[10:20, 10:20] = True  # 100px, small
    mask[40:90, 40:90] = True  # 2500px, big
    candidates = list_connected_components(mask, min_area_ratio=0.005)
    assert len(candidates) == 2
    assert candidates[0].bbox == (40, 40, 90, 90)  # biggest first
    assert candidates[1].bbox == (10, 10, 20, 20)


def test_list_connected_components_drops_blobs_below_floor():
    mask = np.zeros((100, 100), dtype=bool)
    mask[0:3, 0:3] = True  # 9px, below a 5% floor
    mask[40:90, 40:90] = True  # 2500px, above
    candidates = list_connected_components(mask, min_area_ratio=0.05)
    assert len(candidates) == 1
    assert candidates[0].bbox == (40, 40, 90, 90)


def test_center_bias_score_prefers_bbox_closer_to_image_center():
    image_size = (100, 100)  # (width, height)
    centered = (40, 40, 60, 60)  # centroid at (50, 50) == image center
    corner = (0, 0, 20, 20)  # centroid at (10, 10), far from center
    assert center_bias_score(centered, image_size) > center_bias_score(corner, image_size)
    assert center_bias_score(centered, image_size) == 1.0  # dead center -> max score


def test_laplacian_sharpness_scores_noisy_region_higher_than_flat_region():
    rng = np.random.default_rng(0)
    sharp = Image.fromarray(rng.integers(0, 255, (100, 100, 3), dtype=np.uint8))
    flat = Image.new("RGB", (100, 100), (128, 128, 128))
    assert laplacian_sharpness(sharp, (0, 0, 100, 100)) > laplacian_sharpness(flat, (0, 0, 100, 100))


def test_select_best_component_picks_centered_sharp_blob_over_big_offcenter_blurry_one():
    # Big blob in the top-left corner (like a large, blurry neighbor shelf) vs.
    # a smaller, centered, sharp blob (the in-focus target shelf) -- the
    # combined score should favor the centered+sharp one even though it's
    # smaller in area, matching the "target shelf is usually closer to the
    # focal plane and closer to frame center" hypothesis from the spec.
    image = Image.new("RGB", (200, 200), (128, 128, 128))
    draw = ImageDraw.Draw(image)
    rng = np.random.default_rng(1)
    noise = rng.integers(0, 255, (60, 60, 3), dtype=np.uint8)
    image.paste(Image.fromarray(noise), (70, 70))  # centered sharp patch, 60x60=3600px

    big_offcenter = ComponentCandidate(bbox=(0, 0, 90, 90), area_ratio=0.2)  # 8100px, blurry corner
    small_centered_sharp = ComponentCandidate(bbox=(70, 70, 130, 130), area_ratio=0.09)  # 3600px

    best = select_best_component([big_offcenter, small_centered_sharp], image, weights=(1.0, 1.0, 1.0))

    assert best is small_centered_sharp


def test_select_best_component_returns_none_for_empty_candidate_list():
    image = Image.new("RGB", (100, 100))
    assert select_best_component([], image) is None


def test_select_best_component_trivially_returns_sole_candidate():
    # The real-world case confirmed on all 5 demo photos: the mask never
    # fragments into >1 component, so scoring has nothing to discriminate --
    # the sole candidate must always win regardless of weights.
    image = Image.new("RGB", (100, 100))
    only = ComponentCandidate(bbox=(10, 10, 90, 90), area_ratio=0.64)
    assert select_best_component([only], image) is only
