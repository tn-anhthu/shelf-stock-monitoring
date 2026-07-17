"""CLIP image embedding wrapper, for zero-shot catalog retrieval (no fine-tuning).

Model confirmed to exist on Hugging Face 2026-07-17: openai/clip-vit-base-patch32.
"""
from typing import Tuple

import numpy as np
import torch
from PIL import Image
from transformers import CLIPModel, CLIPProcessor

MODEL_ID = "openai/clip-vit-base-patch32"


def load_model_clip() -> Tuple[CLIPModel, CLIPProcessor]:
    model = CLIPModel.from_pretrained(MODEL_ID).to("mps")
    processor = CLIPProcessor.from_pretrained(MODEL_ID)
    return model, processor


def embed_image_clip(model: CLIPModel, processor: CLIPProcessor, image: Image.Image) -> np.ndarray:
    inputs = processor(images=image, return_tensors="pt").to("mps")
    with torch.no_grad():
        output = model.get_image_features(**inputs)
    return output.pooler_output[0].cpu().numpy()
