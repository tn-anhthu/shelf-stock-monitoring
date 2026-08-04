"""One-off experiment script — NOT part of the production pipeline. This is
what established that LLM verification helps and roughly how to prompt it;
see src/pipeline/classify.py (classify_crop) and src/pipeline/llm_escalation.py
(escalate_to_llm) for the production version that's actually wired into
src/pipeline/scan.py::run_scan. Kept as-is since it's the evidence behind that
design decision, not because it should be extended further.

LLM escalation experiment: when SigLIP2's top-1/top-2 candidates are too
close (see the earlier text-embedding experiment, which failed for this
exact reason), ask Claude Haiku 4.5 to pick the right sku_id from a short
shortlist using the crop image directly, or say "unknown" when it can't
tell / the product isn't in the shortlist at all.

Tests against the 2 confusion groups already diagnosed in this conversation:
  (a) cross-brand, similar can shape (Pepsi vs 7up vs Mountain Dew — the last
      one isn't a catalog SKU at all, so it's also an "unknown" test)
  (b) same-brand, different flavor (Vinamilk co-duong vs khong-duong vs a
      different brand's "it duong" milk)

Ground truth for (a) is real shelf crops from data/scan_viz/coke_fridge/,
confirmed by eye.

Ground truth for (b) STILL uses the catalog reference photos, not real shelf
crops — checked both real milk-shelf photos we have
(data/scan_viz/milk_shelf/0_original.jpg, data/scan_viz/input/vnm-lotte-2_*.jpg)
and in both the "CO DUONG"/"KHONG DUONG" print is cropped off by the shelf
price-tag strip or the frame edge at their native 640x480 resolution, so
there's no real crop yet where that text is legible by eye. Swap this group
to real crops once a higher-res shelf photo exists where the print is
readable — don't treat a low-res real crop as ground truth just because it's
real; an unverifiable label is worse than an obviously-synthetic one.

Each group runs twice: once with only the sku_id/name text listed (the
original approach), once with each candidate's first catalog reference image
shown inline before the crop to classify — to measure how much a reference
image actually helps over a bare text shortlist.

Uses structured outputs (output_config.format) to force the model to answer
with exactly one of the given sku_ids or "unknown" — never a made-up SKU.

API key is read from the ANTHROPIC_API_KEY environment variable — either
export it yourself before running, or put it in a .env file (ANTHROPIC_API_KEY=...,
gitignored) and it's auto-loaded via python-dotenv if that package is
installed. Never hardcode the key into this or any other file.

Usage:
    ANTHROPIC_API_KEY=... .venv-e2e/bin/python3 scripts/llm_escalation_experiment.py
    # or: pip install python-dotenv, put ANTHROPIC_API_KEY=... in .env, then just run the script
"""
import base64
import glob
import io
import json
import os
from typing import Dict, List, Optional, Tuple

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import anthropic
from PIL import Image
import pillow_heif
pillow_heif.register_heif_opener()

MODEL_ID = "claude-haiku-4-5"


def _encode_image(image: Image.Image) -> str:
    buf = io.BytesIO()
    image.convert("RGB").save(buf, format="JPEG")
    return base64.standard_b64encode(buf.getvalue()).decode("utf-8")


def _image_block(image: Image.Image) -> Dict:
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": "image/jpeg",
            "data": _encode_image(image),
        },
    }


def load_reference_images(
    sku_ids: List[str], images_root: str = "data/catalog/images"
) -> Dict[str, List[Image.Image]]:
    images = {}
    for sku_id in sku_ids:
        paths = sorted(glob.glob(os.path.join(images_root, sku_id, "*.jpg")))
        images[sku_id] = [Image.open(p) for p in paths]
    return images


def escalate_to_llm(
    client: anthropic.Anthropic,
    image: Image.Image,
    candidates: List[Tuple[str, str]],
    reference_images: Optional[Dict[str, List[Image.Image]]] = None,
) -> str:
    sku_ids = [sku_id for sku_id, _ in candidates]
    candidate_lines = "\n".join(f"- {sku_id}: {name}" for sku_id, name in candidates)

    content: List[Dict] = []
    if reference_images:
        for sku_id, _ in candidates:
            refs = reference_images.get(sku_id) or []
            if not refs:
                continue
            content.append({"type": "text", "text": f"Đây là {sku_id}:"})
            content.append(_image_block(refs[0]))
        content.append({"type": "text", "text": "Đây là ảnh cần phân loại:"})
        content.append(_image_block(image))
        content.append({
            "type": "text",
            "text": (
                "Sản phẩm trong ảnh cần phân loại ở trên khớp với sku_id nào trong "
                "danh sách sau, hoặc trả lời \"unknown\" nếu không khớp SKU nào hoặc "
                "bạn không phân biệt được:\n\n"
                f"{candidate_lines}"
            ),
        })
    else:
        content.append(_image_block(image))
        content.append({
            "type": "text",
            "text": (
                "Đây là ảnh crop 1 sản phẩm trên kệ hàng. Chọn đúng 1 sku_id "
                "khớp với sản phẩm trong ảnh từ danh sách dưới đây, hoặc trả "
                "lời \"unknown\" nếu sản phẩm trong ảnh không khớp SKU nào "
                "hoặc bạn không phân biệt được:\n\n"
                f"{candidate_lines}"
            ),
        })

    response = client.messages.create(
        model=MODEL_ID,
        max_tokens=256,
        messages=[{"role": "user", "content": content}],
        output_config={
            "format": {
                "type": "json_schema",
                "schema": {
                    "type": "object",
                    "properties": {
                        "answer": {"type": "string", "enum": sku_ids + ["unknown"]},
                    },
                    "required": ["answer"],
                    "additionalProperties": False,
                },
            }
        },
    )
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)["answer"]


def run_group(client, label: str, candidates, cases, reference_images=None) -> Tuple[int, int]:
    print(f"=== {label} ===")
    correct = 0
    for path, true_label in cases:
        img = Image.open(path)
        answer = escalate_to_llm(client, img, candidates, reference_images=reference_images)
        ok = answer == true_label
        correct += ok
        print(f"  {path}: true={true_label:<20} llm={answer:<20} [{'OK' if ok else 'WRONG'}]")
    print(f"  -> {correct}/{len(cases)} correct\n")
    return correct, len(cases)


def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("ANTHROPIC_API_KEY not set — export it before running this script.")

    client = anthropic.Anthropic()

    group_a_candidates = [
        ("pepsi_org_lon_320", "Nước ngọt Pepsi Cola lon 320ml"),
        ("7up_org_lon_320", "Nước ngọt 7 Up vị chanh lon 320ml"),
        ("pepsi_zero_lon_320", "Nước ngọt Pepsi Không Calo lon 320ml"),
    ]
    group_a_cases = [
        ("data/scan_viz/coke_fridge/crop_00_ok.jpg", "pepsi_org_lon_320"),
        ("data/scan_viz/coke_fridge/crop_13_ok.jpg", "pepsi_org_lon_320"),
        ("data/scan_viz/coke_fridge/crop_04_ok.jpg", "7up_org_lon_320"),
        ("data/scan_viz/coke_fridge/crop_38_ok.jpg", "unknown"),  # actually Mountain Dew, not a catalog SKU
        ("data/scan_viz/coke_fridge/crop_47_ok.jpg", "unknown"),  # actually Mountain Dew, not a catalog SKU
    ]

    group_b_candidates = [
        ("vnm_org_sugar_180", "Sữa tươi tiệt trùng ít đường Vinamilk 100% Sữa tươi 180ml"),
        ("vnm_org_no_180", "Sữa tươi tiệt trùng không đường Vinamilk 100% Sữa tươi 180ml"),
        ("th_org_180", "Sữa Tươi Tiệt Trùng Có Đường TH true MILK 180 ml"),
        ("dalatmilk_less_180", "Sữa tươi tiệt trùng ít đường Dalat Milk 180ml"),
    ]
    # NOTE: still catalog reference photos, not real shelf crops — see module
    # docstring. Swap once a real crop with legible "co duong/khong duong"
    # print exists. Until then, the "+ reference images" run for this group
    # is close to a trivial test (the crop-to-classify IS each SKU's own
    # reference image, so the correct answer is a near-exact pixel match) —
    # don't read a high score here as evidence reference images help; only
    # the group A comparison is meaningful right now.
    group_b_cases = [
        ("data/catalog/images/vnm_org_sugar_180/1.jpg", "vnm_org_sugar_180"),
        ("data/catalog/images/vnm_org_no_180/1.jpg", "vnm_org_no_180"),
        ("data/catalog/images/th_org_180/1.jpg", "th_org_180"),
        ("data/catalog/images/dalatmilk_less_180/1.jpg", "dalatmilk_less_180"),
    ]

    groups = [
        ("GROUP A: cross-brand, similar can shape", group_a_candidates, group_a_cases),
        ("GROUP B: same-brand, different flavor", group_b_candidates, group_b_cases),
    ]

    results = {}
    for label, candidates, cases in groups:
        sku_ids = [sku_id for sku_id, _ in candidates]
        reference_images = load_reference_images(sku_ids)

        text_only = run_group(client, f"{label} [text-only]", candidates, cases)
        with_refs = run_group(
            client, f"{label} [+ reference images]", candidates, cases, reference_images=reference_images
        )
        results[label] = (text_only, with_refs)

    print("=== SUMMARY: text-only vs + reference images ===")
    for label, (text_only, with_refs) in results.items():
        t_correct, t_total = text_only
        r_correct, r_total = with_refs
        print(f"  {label}")
        print(f"    text-only:          {t_correct}/{t_total}")
        print(f"    + reference images: {r_correct}/{r_total}")


if __name__ == "__main__":
    main()
