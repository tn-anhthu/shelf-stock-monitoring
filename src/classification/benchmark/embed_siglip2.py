"""SigLIP2 image embedding wrapper, for zero-shot catalog retrieval (no fine-tuning).

Model confirmed to exist on Hugging Face 2026-07-17: google/siglip2-base-patch16-224.
"""
from typing import Tuple

import numpy as np
import torch
from PIL import Image
from transformers import AutoModel, AutoProcessor

MODEL_ID = "google/siglip2-base-patch16-224"


def load_model_siglip2() -> Tuple[AutoModel, AutoProcessor]:
    model = AutoModel.from_pretrained(MODEL_ID).to("mps")
    processor = AutoProcessor.from_pretrained(MODEL_ID)
    return model, processor


def embed_image_siglip2(model: AutoModel, processor: AutoProcessor, image: Image.Image) -> np.ndarray:
    inputs = processor(images=image, return_tensors="pt").to("mps")
    with torch.no_grad():
        output = model.get_image_features(**inputs)
    return output.pooler_output[0].cpu().numpy()
