import json
import time
from types import SimpleNamespace

import numpy as np
from PIL import Image

from src.catalog.db import create_tables, get_connection
from src.pipeline.box_filter import filter_anomalous_boxes, filter_contained_boxes
from src.pipeline.box_merge import merge_adjacent_fragments
from src.pipeline.gap_detection import detect_gaps
from src.pipeline.scan import ROW_CLUSTER_TOLERANCE_RATIO, Y_GAP_TOLERANCE_RATIO, adaptive_tolerances, persist_scan, run_scan

FAKE_IMAGE = Image.new("RGB", (200, 200))


FAKE_USAGE = SimpleNamespace(input_tokens=100, output_tokens=20)


class FakeMessages:
    def __init__(self, answer):
        # answer: string (hành vi cũ, cùng 1 câu trả lời mọi lần gọi) hoặc
        # list[string] (mới -- trả lần lượt theo thứ tự gọi, dùng để mô
        # phỏng parent/child khớp 2 SKU khác nhau -- xem test ở Bước 3).
        self.answer = answer
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        current = self.answer[len(self.calls) - 1] if isinstance(self.answer, list) else self.answer
        text = json.dumps({"answer": current})
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
    # Pins the actual real-world invariants discovered on test3.HEIC (median
    # detected-box height ~566.9px against the production YOLO26n checkpoint -
    # see src/pipeline/scan.py's ROW_CLUSTER_TOLERANCE_RATIO/
    # Y_GAP_TOLERANCE_RATIO comments), independent of the exact ratio
    # literals - unlike test_adaptive_tolerances_scales_with_median_box_height
    # above, which imports those same constants and would stay green even if
    # they were changed to values that reintroduce this exact regression.
    #
    # This test has now been re-pinned twice, because its thresholds are a
    # function of one specific checkpoint's box *positions* and do not survive
    # a checkpoint swap:
    #   `full`   -> scale ~450.9px, thresholds 21.0px / 5.1px
    #   n_2000   -> scale ~519.9px, thresholds 74.5px / 38.3px
    #   YOLO26n  -> scale ~566.9px, thresholds below (current)
    # Re-measured directly against real cluster_rows() /
    # merge_adjacent_fragments() output on YOLO26n's test3 detections (see
    # scan.py comments for the full sweep methodology):
    #
    # y_gap_tolerance: real danger (wrongly merging two separate,
    # correctly-classified boxes into one) starts at 26.8px on test3 with
    # YOLO26n - down from n_2000's 38.3px, so this bound genuinely tightened
    # and the old 38.0px assert would no longer have caught it.
    #
    # row_cluster_tolerance: under YOLO26n *no* severe row collapse (max row
    # size jumping 3+ boxes in one step) occurs above the calibrated operating
    # point on test3 anywhere up to the 120px sweep limit - the only severe
    # jump found sits at 11.5px, below the ~24.4px operating point, and is
    # already passed through in normal operation. There is therefore no
    # YOLO26n-measured danger point to pin here. Deliberate judgment call:
    # retain n_2000's measured 74.5px collapse point as the bound rather than
    # loosening the guard to the 120px sweep limit. Absence of a measured jump
    # up to 120px is not positive evidence that 120px is safe, and at the new
    # 566.9px scale this same 74.0px absolute is *stricter* in ratio terms than
    # it was before (74.0/566.9 = 0.1305 vs 74.0/519.9 = 0.1423).
    #
    # Boxes below are synthetic, chosen only so their median height (b[3]-b[1])
    # is ~566.9px to match test3's real YOLO26n-detected scale.
    boxes = [
        (0, 0, 100, 565.0),
        (0, 0, 100, 566.9),
        (0, 0, 100, 568.0),
    ]
    row_cluster_tolerance, y_gap_tolerance = adaptive_tolerances(boxes)
    assert row_cluster_tolerance < 74.0
    assert y_gap_tolerance < 26.5


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
    cleaned_boxes, _flagged, _pairs = filter_contained_boxes(cleaned_boxes)
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


def test_run_scan_excludes_lower_confidence_box_of_a_flagged_pair_from_count():
    # fake_embed_fn returns a FIXED vector regardless of crop, so every box in
    # the other tests always ties on confidence - not enough to exercise the
    # new confidence-comparison logic (see docs/superpowers/specs/
    # 2026-08-05-same-item-dedup-design.md section 9). This test needs an
    # embed_fn that actually varies per crop (keyed off crop pixel area, since
    # child/parent crop to different sizes) so parent and child get two real,
    # different confidence scores.
    child_melon = (20.0, 20.0, 70.0, 150.0)  # smaller box, fully inside parent
    parent_both = (10.0, 20.0, 90.0, 160.0)  # larger box, swallows child

    def detect_fn_twin(image):
        return [child_melon, parent_both]

    def embed_by_crop_size(crop_image):
        # Child's crop area is 50*130=6500px; parent's is 80*140=11200px.
        # Deliberately gives the SMALLER (child) crop the closer-matching
        # vector, so the parent - despite being geometrically bigger - ends
        # up with lower confidence and gets excluded. Proves the decision is
        # confidence-based, not "always keep the bigger box".
        width, height = crop_image.size
        if width * height < 8000:
            return np.array([1.0, 0.0])
        return np.array([0.6, 0.4])

    catalog_items = [{"sku_id": "choco_pie_orion", "name": "Chocopie", "price": 45000, "shelf_full_qty": 10}]
    catalog_embeddings = [("choco_pie_orion", np.array([1.0, 0.0]))]

    result = run_scan(
        image=FAKE_IMAGE,
        catalog_items=catalog_items,
        catalog_embeddings=catalog_embeddings,
        detect_fn=detect_fn_twin,
        embed_fn=embed_by_crop_size,
        llm_client=FakeLLMClient(answer="choco_pie_orion"),
    )

    assert result["boxes"] == [child_melon, parent_both]
    child_detection, parent_detection = result["detections"]
    assert child_detection["confidence"] == 1.0
    assert parent_detection["confidence"] < 1.0
    assert child_detection["excluded_from_count"] is False
    assert parent_detection["excluded_from_count"] is True
    # Only the higher-confidence (child) box counts toward quantity - the
    # excluded parent isn't silently double-counting the same physical item.
    assert result["quantities"] == {"choco_pie_orion": 1}
    # Cả 2 box cùng khớp 1 SKU (choco_pie_orion) -- case an toàn, không cần
    # con người review dù box vẫn bị loại khỏi count.
    assert child_detection["needs_review"] is False
    assert parent_detection["needs_review"] is False


def test_run_scan_flags_needs_review_when_pair_matches_different_skus():
    # Cùng hình học với test_run_scan_excludes_lower_confidence_box_of_a_
    # flagged_pair_from_count ở trên, nhưng lần này parent và child khớp 2 SKU
    # KHÁC NHAU -- case thật sự nguy hiểm cần con người kiểm tra (xem
    # docs/superpowers/specs/2026-08-10-hide-same-sku-purple-box-design.md
    # mục 1, ví dụ thật: OTOKI Kimchi Cay vs Koreno Volcano).
    child_melon = (20.0, 20.0, 70.0, 150.0)
    parent_both = (10.0, 20.0, 90.0, 160.0)

    def detect_fn_twin(image):
        return [child_melon, parent_both]

    def embed_by_crop_size(crop_image):
        width, height = crop_image.size
        if width * height < 8000:
            return np.array([1.0, 0.0])
        return np.array([0.6, 0.4])

    catalog_items = [
        {"sku_id": "choco_pie_orion", "name": "Chocopie", "price": 45000, "shelf_full_qty": 10},
        {"sku_id": "karo_org", "name": "Karo", "price": 30000, "shelf_full_qty": 10},
    ]
    # karo_org's embedding is deliberately NOT parallel to parent's crop
    # vector [0.6, 0.4] (it's [0.5, 0.5], a different direction) so parent's
    # best-match score comes out < 1.0 and strictly less than child's -- a
    # real inequality to drive the loser selection, not a tie. Verified by
    # hand: cosine(child, choco)=1.0, cosine(parent, karo)=0.9806.
    catalog_embeddings = [
        ("choco_pie_orion", np.array([1.0, 0.0])),
        ("karo_org", np.array([0.5, 0.5])),
    ]

    result = run_scan(
        image=FAKE_IMAGE,
        catalog_items=catalog_items,
        catalog_embeddings=catalog_embeddings,
        detect_fn=detect_fn_twin,
        embed_fn=embed_by_crop_size,
        # 2 câu trả lời, tiêu thụ theo THỨ TỰ GỌI: child (crop nhỏ hơn, được
        # xử lý trước trong `pending`) nhận "choco_pie_orion", parent nhận
        # "karo_org". max_workers=1 bên dưới bắt buộc thứ tự gọi LLM đúng
        # thứ tự submit (xem comment ở tham số đó) -- nếu không, 2 luồng có
        # thể gọi song song và đảo thứ tự tiêu thụ list này.
        llm_client=FakeLLMClient(answer=["choco_pie_orion", "karo_org"]),
        max_workers=1,
    )

    assert result["boxes"] == [child_melon, parent_both]
    child_detection, parent_detection = result["detections"]
    assert child_detection["sku_id"] == "choco_pie_orion"
    assert parent_detection["sku_id"] == "karo_org"
    assert child_detection["confidence"] == 1.0
    assert parent_detection["confidence"] < 1.0
    # parent thua (confidence thấp hơn) -- bị loại khỏi count, VÀ vì SKU khác
    # child nên cần con người review.
    assert parent_detection["excluded_from_count"] is True
    assert parent_detection["needs_review"] is True
    assert child_detection["excluded_from_count"] is False
    assert child_detection["needs_review"] is False


def test_run_scan_keeps_needs_review_true_when_a_later_pair_agrees_on_sku():
    # Regression test for a bug found in final whole-branch review: a single
    # oversized parent box can swallow TWO children (filter_contained_boxes
    # emits one flagged_pair per child - see its docstring), so the
    # flagged_pairs loop in run_scan touches the SAME parent detection twice.
    # If needs_review is a plain overwrite (not OR-accumulated), a parent that
    # genuinely disagrees with child1's SKU (pair 1 -> needs_review=True) but
    # happens to agree with child2's SKU (pair 2, processed after) would have
    # its True silently reset to False by pair 2 - erasing a real conflict the
    # frontend now depends on (excluded_from_count=True + needs_review=False
    # is hidden entirely, not shown with a neutral border). See
    # docs/superpowers/specs/2026-08-10-hide-same-sku-purple-box-design.md.
    #
    # Geometry: parent fully swallows two non-overlapping children of
    # different sizes (so filter_anomalous_boxes/merge_adjacent_fragments
    # leave all 3 untouched and filter_contained_boxes flags parent against
    # BOTH, in this order - confirmed directly against filter_contained_boxes
    # before wiring this test):
    #   flagged_pairs == [(parent, child1), (parent, child2)]
    #   boxes (post-filter, row-sorted by y-center) == [child1, parent, child2]
    child1 = (20.0, 20.0, 70.0, 70.0)  # 50x50, y-center 45 -> sorted first
    parent = (10.0, 10.0, 190.0, 190.0)  # 180x180, y-center 100 -> sorted second
    child2 = (100.0, 100.0, 160.0, 160.0)  # 60x60, y-center 130 -> sorted third

    def detect_fn_triplet(image):
        return [child1, child2, parent]

    def embed_by_crop_size(crop_image):
        # child1's crop is 50*50=2500px, child2's is 60*60=3600px, parent's is
        # 180*180=32400px - three distinct buckets, each pointing at a
        # different direction so each box gets a real, distinct embedding.
        width, height = crop_image.size
        area = width * height
        if area <= 2500:
            return np.array([1.0, 0.0])  # child1 -> points straight at sku_a
        if area <= 5000:
            return np.array([0.0, 1.0])  # child2 -> points straight at sku_b
        return np.array([0.6, 0.8])  # parent -> mixed, weaker match to both

    catalog_items = [
        {"sku_id": "sku_a", "name": "SKU A", "price": 10000, "shelf_full_qty": 10},
        {"sku_id": "sku_b", "name": "SKU B", "price": 10000, "shelf_full_qty": 10},
    ]
    catalog_embeddings = [
        ("sku_a", np.array([1.0, 0.0])),
        ("sku_b", np.array([0.0, 1.0])),
    ]

    result = run_scan(
        image=FAKE_IMAGE,
        catalog_items=catalog_items,
        catalog_embeddings=catalog_embeddings,
        detect_fn=detect_fn_triplet,
        embed_fn=embed_by_crop_size,
        # 3 answers, consumed in LLM call order. max_workers=1 forces that
        # order to match submission order (same reasoning as the test above).
        # Boxes reach classify in row-sorted order [child1, parent, child2]:
        #   child1 -> "sku_a" (cosine 1.0 against its own embedding)
        #   parent -> "sku_b" (cosine 0.8, its higher-scoring candidate)
        #   child2 -> "sku_b" (cosine 1.0 against its own embedding)
        llm_client=FakeLLMClient(answer=["sku_a", "sku_b", "sku_b"]),
        max_workers=1,
    )

    assert result["boxes"] == [child1, parent, child2]
    child1_detection, parent_detection, child2_detection = result["detections"]
    assert child1_detection["sku_id"] == "sku_a"
    assert parent_detection["sku_id"] == "sku_b"
    assert child2_detection["sku_id"] == "sku_b"
    # Parent's confidence (0.8, matched to sku_b) loses to BOTH children's
    # (1.0 each) - so parent is excluded by both pairs.
    assert child1_detection["confidence"] == 1.0
    assert child2_detection["confidence"] == 1.0
    assert parent_detection["confidence"] == 0.8
    assert parent_detection["excluded_from_count"] is True
    # Pair 1 (parent vs child1): different SKUs (sku_b vs sku_a) -> a real
    # conflict, needs_review must be True. Pair 2 (parent vs child2): same
    # SKU (sku_b vs sku_b) -> on its own would set needs_review False. The
    # fix accumulates with OR, so the True from pair 1 must survive pair 2.
    assert parent_detection["needs_review"] is True


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

    assert result["detections"] == [
        {"sku_id": None, "confidence": 0.0, "depth": 1, "excluded_from_count": False, "needs_review": False}
    ]
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
