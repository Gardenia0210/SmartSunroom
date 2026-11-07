from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
from PIL import Image
from transformers import AutoImageProcessor, AutoModelForSemanticSegmentation

from src.config import DEFAULT_MODEL, IMAGE_ROTATE_CW90


def rotate_clockwise_90(image_pil: Image.Image) -> Image.Image:
    """顺时针 90°（PIL ROTATE_270 = 逆时针 270°）。"""
    return image_pil.transpose(Image.ROTATE_270)


def run_segmentation(
    image_path: Path,
    model_name: str = DEFAULT_MODEL,
    device: str | None = None,
) -> tuple[np.ndarray, Image.Image]:
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"

    processor = AutoImageProcessor.from_pretrained(model_name)
    model = AutoModelForSemanticSegmentation.from_pretrained(model_name).to(device)
    model.eval()

    image_pil = Image.open(image_path).convert("RGB")
    if IMAGE_ROTATE_CW90:
        image_pil = rotate_clockwise_90(image_pil)
    inputs = processor(images=image_pil, return_tensors="pt").to(device)
    with torch.no_grad():
        outputs = model(**inputs)
    pred = outputs.logits.argmax(dim=1)[0].cpu().numpy().astype(np.uint8)
    pred_resized = np.array(
        Image.fromarray(pred).resize(
            (image_pil.width, image_pil.height), resample=Image.Resampling.NEAREST
        )
    )
    return pred_resized, image_pil
