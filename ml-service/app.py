"""FastAPI wrapper exposing POST /predict, backed by the real CV pipeline.

Schema: docs/adr/0002-analyze-endpoint-schema.md

Models are loaded once at startup (module level) — NOT per request, since
loading YOLO + SigLIP2 takes real time and doing it per-request would make
every /analyze call from the frontend unusably slow.
"""
import io
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, UploadFile
from google import genai
from PIL import Image
import pillow_heif

pillow_heif.register_heif_opener()

from mapping import map_scan_result_to_response
from src.catalog.db import get_connection, list_catalog
from src.classification.benchmark.embed_siglip2 import embed_image_siglip2, load_model_siglip2
from src.detection.train.run_trained_1a import detect_1a, load_model_1a
from src.pipeline.classify import load_catalog_embeddings
from src.pipeline.gap_verify import build_client as build_gap_verify_client
from src.pipeline.scan import run_scan

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parent.parent
WEIGHTS_PATH = REPO_ROOT / "sku110k_yolo26n_results/weights/best.pt"
DB_PATH = REPO_ROOT / "data/shelfsense.db"
IMAGES_DIR = REPO_ROOT / "data/catalog/images"

# The catalog DB stores embedding_path as a plain relative string
# (e.g. "data/catalog/embeddings/choco_pie_org.npy"), resolved relative to
# cwd by src/pipeline/classify.py::load_catalog_embeddings. chdir here so
# that resolves correctly regardless of which directory this process is
# launched from (ml-service/ per the usual `cd ml-service && uvicorn ...`).
os.chdir(REPO_ROOT)

app = FastAPI(title="shelf-stock-monitoring ml-service")

# --- Loaded once at import time (module load = FastAPI process startup) ---
_yolo_model = load_model_1a(WEIGHTS_PATH)
_siglip_model, _siglip_processor = load_model_siglip2()

_conn = get_connection(str(DB_PATH))
_catalog_items = list_catalog(_conn)
_catalog_embeddings = load_catalog_embeddings(_catalog_items)

if os.environ.get("LLM_PROVIDER", "anthropic") != "gemini":
    raise RuntimeError(
        "ml-service currently only supports LLM_PROVIDER=gemini (see .env) — "
        "add an anthropic branch here if that changes."
    )
if not os.environ.get("GEMINI_API_KEY"):
    raise RuntimeError("GEMINI_API_KEY not set in .env")
_llm_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

# Fail-open (spec S4): gap_verify is a precision layer on top of
# detect_gaps(), not required for the service to run. No OPENROUTER_API_KEY
# means detect_gaps() candidates pass through unverified (see
# src/pipeline/scan.py::run_scan's gap_verify_client=None branch) instead of
# crashing startup the way a missing GEMINI_API_KEY does above -- classify is
# core to the product, gap_verify is not.
_gap_verify_client = build_gap_verify_client()
if _gap_verify_client is None:
    print("OPENROUTER_API_KEY not set - gap_verify disabled, detect_gaps() candidates will pass through unverified.")


def _detect_fn(image):
    return detect_1a(_yolo_model, image)


def _embed_fn(cropped_image):
    return embed_image_siglip2(_siglip_model, _siglip_processor, cropped_image)


@app.post("/predict")
async def predict(image: UploadFile = File(...)):
    contents = await image.read()
    with Image.open(io.BytesIO(contents)) as img:
        img.load()
        width, height = img.size

        scan_result = run_scan(
            image=img,
            catalog_items=_catalog_items,
            catalog_embeddings=_catalog_embeddings,
            detect_fn=_detect_fn,
            embed_fn=_embed_fn,
            llm_client=_llm_client,
            gap_verify_client=_gap_verify_client,
            images_dir=str(IMAGES_DIR),
        )

    return map_scan_result_to_response(
        scan_result,
        catalog_items=_catalog_items,
        image_width=width,
        image_height=height,
    )
