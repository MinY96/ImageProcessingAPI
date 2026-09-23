"""OpenVINO SD 1.5 Inpainting Synthetic NG API example.

Before running:
    pip install -r requirements.txt
    pip install -r requirements-openvino-diffusion.txt

Prepare the local model once (internet/model access required for first export):
    python scripts/prepare_openvino_sd15_inpaint.py --device CPU --compile-test

Run API:
    uvicorn src.main:app --reload
"""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import cv2
import httpx
import numpy as np


BASE_URL = "http://127.0.0.1:8000/api/v1"
ROI_IMAGE_PATH = Path("hose_roi_512.png")
OUTPUT_DIR = Path("openvino_synthetic_output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

payload = {
    "method": "diffusion_inpaint",
    "defect_type": "tear_with_seepage",
    "count": 1,
    "seed": 100,
    "mask": {
        "type": "ellipse",
        "center_x": 0.52,
        "center_y": 0.50,
        "width_ratio": 0.14,
        "height_ratio": 0.10,
        "rotation_deg": 15,
        "feather_px": 5,
    },
    "parameters": {
        "model": "sd15_openvino_inpaint",
        "prompt_preset": "tear_with_seepage",
        "device": "AUTO",
        "input_size": 512,
        "steps": 20,
        "guidance_scale": 7.0,
        "strength": 0.85,
    },
}

with ROI_IMAGE_PATH.open("rb") as stream:
    response = httpx.post(
        f"{BASE_URL}/synthetic/generate",
        params={"response_format": "zip"},
        data={"payload": json.dumps(payload)},
        files={"source_image": (ROI_IMAGE_PATH.name, stream, "image/png")},
        timeout=600,
    )

response.raise_for_status()

with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
    archive.extractall(OUTPUT_DIR)
    generated = cv2.imdecode(
        np.frombuffer(archive.read("candidates/00/image.png"), dtype=np.uint8),
        cv2.IMREAD_COLOR,
    )
    cv2.imwrite(str(OUTPUT_DIR / "generated_preview.png"), generated)

print(f"saved: {OUTPUT_DIR.resolve()}")
