"""Thin FastAPI wrapper exposing POST /predict.

Schema: docs/adr/0002-analyze-endpoint-schema.md

Currently returns fixed mock boxes regardless of image content — the CV
pipeline (src/pipeline/scan.py) is not wired in yet (see ADR-001). Image
width/height are read from the real upload since that's not "mock" logic,
just image inspection.
"""

import io

from fastapi import FastAPI, File, UploadFile
from PIL import Image

app = FastAPI(title="shelf-stock-monitoring ml-service")

# NOTE: these mock bbox pixel coordinates are NOT scaled to the real uploaded
# image's width/height (returned separately via img.size below), so on real
# (non-mock-sized) photos the boxes will visually misalign / cluster in a
# corner. This is expected and will self-resolve once real CV integration
# replaces this mock and returns boxes already scaled to the actual image.
_MOCK_BOXES = [
    {
        "box_id": "b1",
        "bbox": [40, 40, 220, 420],
        "type": "product",
        "sku_id": "choco_pie_org",
        "sku_name": "Bánh chocopie Orion hộp 217.8g (6 cái)",
        "confidence": 0.94,
        "is_unknown": False,
    },
    {
        "box_id": "b2",
        "bbox": [230, 40, 410, 420],
        "type": "product",
        "sku_id": "choco_pie_org",
        "sku_name": "Bánh chocopie Orion hộp 217.8g (6 cái)",
        "confidence": 0.91,
        "is_unknown": False,
    },
    {
        "box_id": "b3",
        "bbox": [420, 40, 600, 420],
        "type": "product",
        "sku_id": "karo_org",
        "sku_name": "Bánh trứng tươi chà bông Karo Richy túi 156g",
        "confidence": 0.89,
        "is_unknown": False,
    },
    {
        "box_id": "b4",
        "bbox": [610, 40, 790, 420],
        "type": "product",
        "sku_id": None,
        "sku_name": None,
        "confidence": 0.52,
        "is_unknown": True,
    },
    {
        "box_id": "b5",
        "bbox": [800, 40, 980, 420],
        "type": "gap",
        "sku_id": None,
        "sku_name": None,
        "confidence": 0.0,
        "is_unknown": False,
    },
]

_MOCK_WARNINGS = {
    "low_confidence_regions": ["b4"],
    "edge_crop_regions": [],
    "blur_detected": False,
}


@app.post("/predict")
async def predict(image: UploadFile = File(...)):
    contents = await image.read()
    with Image.open(io.BytesIO(contents)) as img:
        width, height = img.size

    return {
        "image": {"width": width, "height": height},
        "boxes": _MOCK_BOXES,
        "warnings": _MOCK_WARNINGS,
    }
