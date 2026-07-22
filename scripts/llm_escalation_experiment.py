"""LLM escalation experiment: when SigLIP2's top-1/top-2 candidates are too
close (see the earlier text-embedding experiment, which failed for this
exact reason), ask Claude Haiku 4.5 to pick the right sku_id from a short
shortlist using the crop image directly, or say "khong_chac" when it can't
tell / the product isn't in the shortlist at all.

Tests against the 2 confusion groups already diagnosed in this conversation:
  (a) cross-brand, similar can shape (Pepsi vs 7up vs Mountain Dew — the last
      one isn't a catalog SKU at all, so it's also a "khong_chac" test)
  (b) same-brand, different flavor (Vinamilk co-duong vs khong-duong vs a
      different brand's "it duong" milk)

Ground truth for (a) is real shelf crops from data/scan_viz/coke_fridge/,
confirmed by eye. Ground truth for (b) uses the catalog reference photos
themselves (same images used for the earlier SigLIP2 text-embedding test),
since real shelf crops are too small/low-res to read "co duong" vs "khong
duong" text reliably by eye.

Uses structured outputs (output_config.format) to force the model to answer
with exactly one of the given sku_ids or "khong_chac" — never a made-up SKU.

API key is read from the ANTHROPIC_API_KEY environment variable — either
export it yourself before running, or put it in a .env file (ANTHROPIC_API_KEY=...,
gitignored) and it's auto-loaded via python-dotenv if that package is
installed. Never hardcode the key into this or any other file.

Usage:
    ANTHROPIC_API_KEY=... .venv-e2e/bin/python3 scripts/llm_escalation_experiment.py
    # or: pip install python-dotenv, put ANTHROPIC_API_KEY=... in .env, then just run the script
"""
import base64
import io
import json
import os
from typing import List, Tuple

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import anthropic
from PIL import Image

MODEL_ID = "claude-haiku-4-5"


def _encode_image(image: Image.Image) -> str:
    buf = io.BytesIO()
    image.convert("RGB").save(buf, format="JPEG")
    return base64.standard_b64encode(buf.getvalue()).decode("utf-8")


def escalate_to_llm(
    client: anthropic.Anthropic,
    image: Image.Image,
    candidates: List[Tuple[str, str]],
) -> str:
    sku_ids = [sku_id for sku_id, _ in candidates]
    candidate_lines = "\n".join(f"- {sku_id}: {name}" for sku_id, name in candidates)

    response = client.messages.create(
        model=MODEL_ID,
        max_tokens=256,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": _encode_image(image),
                    },
                },
                {
                    "type": "text",
                    "text": (
                        "Đây là ảnh crop 1 sản phẩm trên kệ hàng. Chọn đúng 1 sku_id "
                        "khớp với sản phẩm trong ảnh từ danh sách dưới đây, hoặc trả "
                        "lời \"khong_chac\" nếu sản phẩm trong ảnh không khớp SKU nào "
                        "hoặc bạn không phân biệt được:\n\n"
                        f"{candidate_lines}"
                    ),
                },
            ],
        }],
        output_config={
            "format": {
                "type": "json_schema",
                "schema": {
                    "type": "object",
                    "properties": {
                        "answer": {"type": "string", "enum": sku_ids + ["khong_chac"]},
                    },
                    "required": ["answer"],
                    "additionalProperties": False,
                },
            }
        },
    )
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)["answer"]


def run_group(client, label: str, candidates, cases):
    print(f"=== {label} ===")
    correct = 0
    for path, true_label in cases:
        img = Image.open(path)
        answer = escalate_to_llm(client, img, candidates)
        ok = answer == true_label
        correct += ok
        print(f"  {path}: true={true_label:<20} llm={answer:<20} [{'OK' if ok else 'WRONG'}]")
    print(f"  -> {correct}/{len(cases)} correct\n")


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
        ("data/scan_viz/coke_fridge/crop_38_ok.jpg", "khong_chac"),  # actually Mountain Dew, not a catalog SKU
        ("data/scan_viz/coke_fridge/crop_47_ok.jpg", "khong_chac"),  # actually Mountain Dew, not a catalog SKU
    ]
    run_group(client, "GROUP A: cross-brand, similar can shape", group_a_candidates, group_a_cases)

    group_b_candidates = [
        ("vnm_org_sugar_180", "Sữa tươi tiệt trùng ít đường Vinamilk 100% Sữa tươi 180ml"),
        ("vnm_org_no_180", "Sữa tươi tiệt trùng không đường Vinamilk 100% Sữa tươi 180ml"),
        ("th_org_180", "Sữa Tươi Tiệt Trùng Có Đường TH true MILK 180 ml"),
        ("dalatmilk_less_180", "Sữa tươi tiệt trùng ít đường Dalat Milk 180ml"),
    ]
    group_b_cases = [
        ("data/catalog/images/vnm_org_sugar_180/1.jpg", "vnm_org_sugar_180"),
        ("data/catalog/images/vnm_org_no_180/1.jpg", "vnm_org_no_180"),
        ("data/catalog/images/th_org_180/1.jpg", "th_org_180"),
        ("data/catalog/images/dalatmilk_less_180/1.jpg", "dalatmilk_less_180"),
    ]
    run_group(client, "GROUP B: same-brand, different flavor", group_b_candidates, group_b_cases)


if __name__ == "__main__":
    main()
