"""Synthetic NG Generator API example.

Run the API first:
    uvicorn src.main:app --reload
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx


BASE_URL = "http://127.0.0.1:8000/api/v1"
IMAGE_PATH = Path("sample.png")
OUTPUT_PATH = Path("synthetic_result.zip")

payload = {
    "method": "procedural",
    "defect_type": "liquid_pool",
    "severity": 0.6,
    "count": 4,
    "seed": 100,
    "mask": {
        "type": "ellipse",
        "center_x": 0.55,
        "center_y": 0.45,
        "width_ratio": 0.18,
        "height_ratio": 0.12,
        "feather_px": 4,
    },
    "parameters": {
        "pattern": "pooling",
        "opacity": 0.5,
    },
}

with IMAGE_PATH.open("rb") as stream:
    response = httpx.post(
        f"{BASE_URL}/synthetic/generate",
        params={"response_format": "zip"},
        data={"payload": json.dumps(payload)},
        files={"source_image": (IMAGE_PATH.name, stream, "image/png")},
        timeout=120,
    )

response.raise_for_status()
OUTPUT_PATH.write_bytes(response.content)
print(f"saved: {OUTPUT_PATH.resolve()}")
