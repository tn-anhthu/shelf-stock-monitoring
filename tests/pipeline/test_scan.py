import json
import time
from types import SimpleNamespace

import numpy as np
from PIL import Image

from src.catalog.db import create_tables, get_connection
from src.pipeline.box_filter import filter_anomalous_boxes, filter_contained_boxes
from src.pipeline.box_merge import merge_adjacent_fragments
from src.pipeline.gap_detection import detect_gaps
from src.pipeline.roi_crop import RoiCropResult
from src.pipeline.scan import ROW_CLUSTER_TOLERANCE_RATIO, Y_GAP_TOLERANCE_RATIO, adaptive_tolerances, persist_scan, run_scan

FAKE_IMAGE = Image.new("RGB", (200, 200))


FAKE_USAGE = SimpleNamespace(input_tokens=100, output_tokens=20)


class FakeMessages:
    def __init__(self, answer):
        self.answer = answer
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        text = json.dumps({"answer": self.answer})
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)], usage=FAKE_USAGE)


class FakeLLMClient:
    def __init__(self, answer):
        self.messages = FakeMessages(answer)


class DelayedFakeMessages:
    def __init__(self, answer, delay):
        self.answer = answer
        self.delay = delay

    def create(self, **kwargs):
        time.sleep(self.delay)
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=json.dumps({"answer": self.answer}))], usage=FAKE_USAGE
        )


class DelayedFakeLLMClient:
    def __init__(self, answer, delay):
        self.messages = DelayedFakeMessages(answer, delay)


def fake_detect_fn(image):
    # 2 boxes on the "shelf"
    return [(0, 0, 10, 10), (10, 0, 20, 10)]


def fake_detect_fn_with_fragments(image):
    return [
        (0, 0, 10, 10),  # normal box
        (20, 0, 30, 10),  # normal box
        (50, 0, 60, 3),  # split-box fragment (top)
        (50, 3, 60, 6),  # split-box fragment (bottom) -> should merge with the one above
        (100, 0, 100.9, 10),  # anomalously narrow junk box -> should be filtered out
    ]


def fake_embed_fn(crop_image):
    # crop_image is unused by the fake; return a fixed vector so classify_crop
    # always matches "choco_pie_orion" (see catalog_embeddings below)
    return np.array([1.0, 0.0])


def test_adaptive_tolerances_scales_with_median_box_height():
    # heights: 100, 200, 300 -> median 200
    boxes = [(0, 0, 100, 100), (200, 0, 300, 200), (400, 0, 500, 300)]
    row_cluster_tolerance, y_gap_tolerance = adaptive_tolerances(boxes)
    assert row_cluster_tolerance == ROW_CLUSTER_TOLERANCE_RATIO * 200
    assert y_gap_tolerance == Y_GAP_TOLERANCE_RATIO * 200


def test_adaptive_tolerances_falls_back_with_fewer_than_2_boxes():
    assert adaptive_tolerances([]) == (20.0, 5.0)
    assert adaptive_tolerances([(0, 0, 100, 100)]) == (20.0, 5.0)


def test_adaptive_tolerances_stay_below_test3_danger_thresholds():
    # Pins the actual real-world invariants Task 4's verification discovered on
    # test3.HEIC (median detected-box height ~450.9px), independent of the
    # exact ROW_CLUSTER_TOLERANCE_RATIO / Y_GAP_TOLERANCE_RATIO literals -
    # unlike test_adaptive_tolerances_scales_with_median_box_height above,
    # which imports those same constants and would stay green even if they
    # were changed to values that reintroduce this exact regression.
    #
    # row_cluster_tolerance: at test3's scale, cluster_rows' row grouping was
    # empirically found to flip between 21.0px (still safe) and 21.5px,
    # producing a phantom gap spanning almost the entire Yakult shelf row.
    # y_gap_tolerance: at test3's scale, a value of 5.78px crosses the real
    # ~5.1px gap between two separate, correctly-classified stacked Yakult
    # 5-packs and wrongly merges them into one unclassifiable box.
    #
    # Boxes below are synthetic, chosen only so their median height (b[3]-b[1])
    # is ~450.9px to match test3's real detected scale.
    boxes = [
        (0, 0, 100, 449.0),
        (0, 0, 100, 450.9),
        (0, 0, 100, 452.0),
    ]
    row_cluster_tolerance, y_gap_tolerance = adaptive_tolerances(boxes)
    assert row_cluster_tolerance < 21.0
    assert y_gap_tolerance < 5.1


def test_run_scan_produces_quantities_value_and_flags():
    catalog_items = [
        {"sku_id": "choco_pie_orion", "name": "Chocopie", "price": 45000, "shelf_full_qty": 10},
    ]
    catalog_embeddings = [("choco_pie_orion", np.array([1.0, 0.0]))]

    result = run_scan(
        image=FAKE_IMAGE,
        catalog_items=catalog_items,
        catalog_embeddings=catalog_embeddings,
        detect_fn=fake_detect_fn,
        embed_fn=fake_embed_fn,
        llm_client=FakeLLMClient(answer="choco_pie_orion"),
    )

    assert result["quantities"] == {"choco_pie_orion": 2}
    assert result["value"] == 2 * 45000
    assert result["flags"] == {"choco_pie_orion": "low"}
    assert result["low_confidence"] is False
    assert len(result["detections"]) == 2


def test_run_scan_includes_boxes_aligned_with_detections():
    catalog_items = [
        {"sku_id": "choco_pie_orion", "name": "Chocopie", "price": 45000, "shelf_full_qty": 10},
    ]
    catalog_embeddings = [("choco_pie_orion", np.array([1.0, 0.0]))]

    result = run_scan(
        image=FAKE_IMAGE,
        catalog_items=catalog_items,
        catalog_embeddings=catalog_embeddings,
        detect_fn=fake_detect_fn,
        embed_fn=fake_embed_fn,
        llm_client=FakeLLMClient(answer="choco_pie_orion"),
    )

    assert result["boxes"] == [(0, 0, 10, 10), (10, 0, 20, 10)]
    assert len(result["boxes"]) == len(result["detections"])


def test_run_scan_applies_depth_multiplier_by_box_index():
    catalog_items = [{"sku_id": "choco_pie_orion", "name": "Chocopie", "price": 45000, "shelf_full_qty": 10}]
    catalog_embeddings = [("choco_pie_orion", np.array([1.0, 0.0]))]

    result = run_scan(
        image=FAKE_IMAGE,
        catalog_items=catalog_items,
        catalog_embeddings=catalog_embeddings,
        detect_fn=fake_detect_fn,
        embed_fn=fake_embed_fn,
        llm_client=FakeLLMClient(answer="choco_pie_orion"),
        depth_by_index={0: 3, 1: 1},
    )

    assert result["quantities"] == {"choco_pie_orion": 4}


def test_run_scan_merges_and_filters_boxes_before_classify_and_gaps():
    catalog_items = [
        {"sku_id": "choco_pie_orion", "name": "Chocopie", "price": 45000, "shelf_full_qty": 10},
    ]
    catalog_embeddings = [("choco_pie_orion", np.array([1.0, 0.0]))]

    result = run_scan(
        image=FAKE_IMAGE,
        catalog_items=catalog_items,
        catalog_embeddings=catalog_embeddings,
        detect_fn=fake_detect_fn_with_fragments,
        embed_fn=fake_embed_fn,
        llm_client=FakeLLMClient(answer="choco_pie_orion"),
    )

    raw_boxes = fake_detect_fn_with_fragments(None)
    row_cluster_tolerance, y_gap_tolerance = adaptive_tolerances(raw_boxes)
    cleaned_boxes = filter_anomalous_boxes(
        merge_adjacent_fragments(raw_boxes, y_gap_tolerance=y_gap_tolerance),
        row_cluster_tolerance=row_cluster_tolerance,
    )
    cleaned_boxes, _flagged = filter_contained_boxes(cleaned_boxes)
    assert len(cleaned_boxes) == 3
    assert len(result["detections"]) == 3
    assert result["gaps"] == detect_gaps(cleaned_boxes, row_cluster_tolerance=row_cluster_tolerance)


def test_run_scan_drops_redundant_containing_box_and_reports_flagged_regions():
    # Real Haohao crop_45 coords (see tests/pipeline/test_box_filter.py for the
    # crop cross-check): box45 swallows box41 entirely and also dips into
    # box48's region at leftover-coverage level (~0.6, below the 0.8 primary
    # containment threshold so box48 isn't itself a second "child") - both
    # regions box45 covers already have their own independent box, so box45
    # is genuinely redundant.
    box41_top_cup = (1109.0, 2840.4, 1326.8, 3116.4)
    box45_both_cups = (1116.5, 2843.7, 1326.5, 3254.9)
    box48_bottom_cup = (1125.5, 3098.8, 1318.6, 3359.2)

    def detect_fn_containment(image):
        return [box41_top_cup, box45_both_cups, box48_bottom_cup]

    catalog_items = [{"sku_id": "choco_pie_orion", "name": "Chocopie", "price": 45000, "shelf_full_qty": 10}]
    catalog_embeddings = [("choco_pie_orion", np.array([1.0, 0.0]))]

    result = run_scan(
        image=FAKE_IMAGE,
        catalog_items=catalog_items,
        catalog_embeddings=catalog_embeddings,
        detect_fn=detect_fn_containment,
        embed_fn=fake_embed_fn,
        llm_client=FakeLLMClient(answer="choco_pie_orion"),
    )

    assert len(result["detections"]) == 2  # box45 dropped, box41 + box48 kept
    assert result["flagged_regions"] == []


def test_run_scan_flags_redundant_looking_box_when_leftover_uncovered():
    # Real Binggrae crop_38 coords (see tests/pipeline/test_box_filter.py for
    # the crop cross-check): box38 swallows box37 (Melon) but also covers a
    # Strawberry-side region no other box touches at all -> must be kept, not
    # silently dropped, and surfaced via flagged_regions.
    box37_melon_only = (702.7, 2476.3, 819.0, 2772.5)
    box38_melon_and_strawberry = (610.1, 2478.3, 820.7, 2808.7)

    def detect_fn_containment(image):
        return [box37_melon_only, box38_melon_and_strawberry]

    catalog_items = [{"sku_id": "choco_pie_orion", "name": "Chocopie", "price": 45000, "shelf_full_qty": 10}]
    catalog_embeddings = [("choco_pie_orion", np.array([1.0, 0.0]))]

    result = run_scan(
        image=FAKE_IMAGE,
        catalog_items=catalog_items,
        catalog_embeddings=catalog_embeddings,
        detect_fn=detect_fn_containment,
        embed_fn=fake_embed_fn,
        llm_client=FakeLLMClient(answer="choco_pie_orion"),
    )

    assert len(result["detections"]) == 2  # box37 + box38 both kept
    assert result["flagged_regions"] == [box38_melon_and_strawberry]





def test_run_scan_includes_gaps_from_detected_boxes():
    catalog_items = [
        {"sku_id": "choco_pie_orion", "name": "Chocopie", "price": 45000, "shelf_full_qty": 10},
    ]
    catalog_embeddings = [("choco_pie_orion", np.array([1.0, 0.0]))]

    result = run_scan(
        image=FAKE_IMAGE,
        catalog_items=catalog_items,
        catalog_embeddings=catalog_embeddings,
        detect_fn=fake_detect_fn,
        embed_fn=fake_embed_fn,
        llm_client=FakeLLMClient(answer="choco_pie_orion"),
    )

    raw_boxes = fake_detect_fn(None)
    row_cluster_tolerance, _y_gap_tolerance = adaptive_tolerances(raw_boxes)
    assert result["gaps"] == detect_gaps(raw_boxes, row_cluster_tolerance=row_cluster_tolerance)


def test_run_scan_flags_undetected_catalog_sku_as_out():
    catalog_items = [
        {"sku_id": "choco_pie_orion", "name": "Chocopie", "price": 45000, "shelf_full_qty": 10},
        {"sku_id": "coke_330", "name": "Coke", "price": 12000, "shelf_full_qty": 20},
    ]
    catalog_embeddings = [("choco_pie_orion", np.array([1.0, 0.0]))]

    result = run_scan(
        image=FAKE_IMAGE,
        catalog_items=catalog_items,
        catalog_embeddings=catalog_embeddings,
        detect_fn=fake_detect_fn,
        embed_fn=fake_embed_fn,
        llm_client=FakeLLMClient(answer="choco_pie_orion"),
    )

    assert result["flags"]["coke_330"] == "out"


def test_run_scan_flags_low_confidence_when_no_catalog_match():
    result = run_scan(
        image=FAKE_IMAGE,
        catalog_items=[],
        catalog_embeddings=[],
        detect_fn=fake_detect_fn,
        embed_fn=fake_embed_fn,
        llm_client=FakeLLMClient(answer="choco_pie_orion"),
    )
    assert result["low_confidence"] is True
    assert result["quantities"] == {}


def test_run_scan_skips_embed_and_classify_for_degenerate_crop():
    # Box fully outside the 200x200 FAKE_IMAGE bounds -> crop_box returns None.
    def detect_fn_out_of_bounds(image):
        return [(300, 300, 310, 310)]

    embed_calls = []

    def tracking_embed_fn(crop_image):
        embed_calls.append(crop_image)
        return np.array([1.0, 0.0])

    llm_client = FakeLLMClient(answer="choco_pie_orion")

    result = run_scan(
        image=FAKE_IMAGE,
        catalog_items=[{"sku_id": "choco_pie_orion", "name": "Chocopie", "price": 45000, "shelf_full_qty": 10}],
        catalog_embeddings=[("choco_pie_orion", np.array([1.0, 0.0]))],
        detect_fn=detect_fn_out_of_bounds,
        embed_fn=tracking_embed_fn,
        llm_client=llm_client,
    )

    assert result["detections"] == [{"sku_id": None, "confidence": 0.0, "depth": 1}]
    assert embed_calls == []
    assert llm_client.messages.calls == []


def test_run_scan_verifies_boxes_with_llm_in_parallel_not_sequentially():
    def detect_fn_five_separate_boxes(image):
        # Well-separated (y-gap > row_cluster_tolerance) so merge/filter/gap
        # logic doesn't interact with them - this test is only about phase 2
        # (LLM verification) actually running concurrently across boxes.
        return [(0, 0, 10, 10), (0, 30, 10, 40), (0, 60, 10, 70), (0, 90, 10, 100), (0, 120, 10, 130)]

    catalog_items = [{"sku_id": "choco_pie_orion", "name": "Chocopie", "price": 45000, "shelf_full_qty": 10}]
    catalog_embeddings = [("choco_pie_orion", np.array([1.0, 0.0]))]
    delay = 0.2
    llm_client = DelayedFakeLLMClient(answer="choco_pie_orion", delay=delay)

    start = time.monotonic()
    result = run_scan(
        image=FAKE_IMAGE,
        catalog_items=catalog_items,
        catalog_embeddings=catalog_embeddings,
        detect_fn=detect_fn_five_separate_boxes,
        embed_fn=fake_embed_fn,
        llm_client=llm_client,
        max_workers=5,
    )
    elapsed = time.monotonic() - start

    assert len(result["detections"]) == 5
    assert result["quantities"] == {"choco_pie_orion": 5}
    # sequential would take 5 * delay (1.0s); parallel should be well under half that.
    assert elapsed < delay * 5 / 2


def test_run_scan_applies_roi_crop_before_detect_when_background_present():
    # Simulates the "has clear background, needs crop" case: roi_crop_fn hands
    # back a smaller, different image object than FAKE_IMAGE (standing in for a
    # neighboring-shelf crop actually being removed) and detect_fn must receive
    # THAT image, not the original -- proving the crop runs before detect_fn.
    cropped_image = Image.new("RGB", (150, 150))
    seen_images = []

    def tracking_detect_fn(image):
        seen_images.append(image)
        return fake_detect_fn(image)

    def roi_crop_fn(image):
        assert image is FAKE_IMAGE  # roi crop must see the *original* upload
        return RoiCropResult(image=cropped_image, applied=True, reason="ok", bbox=(25, 25, 175, 175))

    catalog_items = [{"sku_id": "choco_pie_orion", "name": "Chocopie", "price": 45000, "shelf_full_qty": 10}]
    catalog_embeddings = [("choco_pie_orion", np.array([1.0, 0.0]))]

    result = run_scan(
        image=FAKE_IMAGE,
        catalog_items=catalog_items,
        catalog_embeddings=catalog_embeddings,
        detect_fn=tracking_detect_fn,
        embed_fn=fake_embed_fn,
        llm_client=FakeLLMClient(answer="choco_pie_orion"),
        roi_crop_fn=roi_crop_fn,
    )

    assert seen_images == [cropped_image]
    assert result["roi_crop"] == {"applied": True, "reason": "ok", "bbox": (25, 25, 175, 175)}
    assert result["quantities"] == {"choco_pie_orion": 2}  # scan still completes normally


def test_run_scan_falls_back_to_original_image_when_roi_mask_unreliable():
    # Simulates CLIPSeg producing an empty/too-small mask (e.g. a shelf photo
    # CLIPSeg can't confidently segment): roi_crop_fn reports applied=False and
    # hands back the ORIGINAL image untouched -- the scan must still complete
    # normally on the original image, never crash or block.
    def roi_crop_fn(image):
        return RoiCropResult(image=image, applied=False, reason="mask_empty_or_too_small", bbox=None)

    catalog_items = [{"sku_id": "choco_pie_orion", "name": "Chocopie", "price": 45000, "shelf_full_qty": 10}]
    catalog_embeddings = [("choco_pie_orion", np.array([1.0, 0.0]))]

    result = run_scan(
        image=FAKE_IMAGE,
        catalog_items=catalog_items,
        catalog_embeddings=catalog_embeddings,
        detect_fn=fake_detect_fn,
        embed_fn=fake_embed_fn,
        llm_client=FakeLLMClient(answer="choco_pie_orion"),
        roi_crop_fn=roi_crop_fn,
    )

    assert result["roi_crop"] == {"applied": False, "reason": "mask_empty_or_too_small", "bbox": None}
    assert result["quantities"] == {"choco_pie_orion": 2}  # scan not blocked by the fallback


def test_run_scan_skips_roi_crop_entirely_when_no_roi_crop_fn_given():
    # Default (roi_crop_fn=None) must behave exactly like before 2026-07-28 --
    # no crop attempted, no crash, "disabled" reported for observability.
    catalog_items = [{"sku_id": "choco_pie_orion", "name": "Chocopie", "price": 45000, "shelf_full_qty": 10}]
    catalog_embeddings = [("choco_pie_orion", np.array([1.0, 0.0]))]

    result = run_scan(
        image=FAKE_IMAGE,
        catalog_items=catalog_items,
        catalog_embeddings=catalog_embeddings,
        detect_fn=fake_detect_fn,
        embed_fn=fake_embed_fn,
        llm_client=FakeLLMClient(answer="choco_pie_orion"),
    )

    assert result["roi_crop"] == {"applied": False, "reason": "disabled", "bbox": None}


def test_persist_scan_writes_scan_history_and_inventory_rows(tmp_path):
    db_path = tmp_path / "shelfsense.db"
    conn = get_connection(str(db_path))
    create_tables(conn)

    scan_result = {
        "detections": [{"sku_id": "choco_pie_orion", "confidence": 1.0}],
        "low_confidence": False,
        "quantities": {"choco_pie_orion": 2},
        "value": 90000,
        "flags": {"choco_pie_orion": "low"},
    }

    persist_scan(
        conn,
        image_path="data/scans/1.jpg",
        scan_result=scan_result,
        catalog_items=[{"sku_id": "choco_pie_orion", "price": 45000}],
    )

    scan_rows = conn.execute("SELECT image_path, raw_result FROM scan_history").fetchall()
    assert len(scan_rows) == 1
    assert scan_rows[0][0] == "data/scans/1.jpg"
    assert json.loads(scan_rows[0][1])["quantities"] == {"choco_pie_orion": 2}

    inventory_rows = conn.execute("SELECT sku_id, quantity, value, status FROM inventory").fetchall()
    assert inventory_rows == [("choco_pie_orion", 2, 90000, "low")]
