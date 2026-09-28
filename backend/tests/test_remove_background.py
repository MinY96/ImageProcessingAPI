import base64
import json

import numpy as np
import pytest
from fastapi.testclient import TestClient

cv2 = pytest.importorskip("cv2")

from src.registry import create_default_registry
from src.schemas import ColorSpace, ImageData
from src.api import create_app


def test_remove_background_returns_transparent_bgra_and_binary_mask():
    image = np.full((96, 128, 3), 18, dtype=np.uint8)
    cv2.rectangle(image, (38, 22), (90, 76), (30, 120, 230), thickness=-1)
    source = ImageData(data=image, color_space=ColorSpace.BGR, name="shape")

    result = create_default_registry().execute(
        operation="remove_background",
        inputs={"image": source},
        params={"x": 28, "y": 12, "width": 74, "height": 74, "iterations": 2},
    )

    assert result.success, result.error
    foreground = result.output.images["image"]
    mask = result.output.images["mask"]
    assert foreground.color_space == ColorSpace.BGRA
    assert foreground.data.shape == (96, 128, 4)
    assert np.any(foreground.data[:, :, 3] == 0)
    assert np.any(foreground.data[:, :, 3] == 255)
    assert mask.color_space == ColorSpace.BINARY
    assert result.output.data["foreground_ratio"] > 0


def test_remove_background_rejects_full_image_rectangle():
    image = ImageData(
        data=np.zeros((32, 40, 3), dtype=np.uint8),
        color_space=ColorSpace.BGR,
    )
    result = create_default_registry().execute(
        operation="remove_background",
        inputs={"image": image},
        params={"x": 0, "y": 0, "width": 40, "height": 32},
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.code == "invalid_foreground_rectangle"


def test_remove_background_api_encodes_alpha_channel_as_png():
    image = np.full((96, 128, 3), 18, dtype=np.uint8)
    cv2.rectangle(image, (38, 22), (90, 76), (30, 120, 230), thickness=-1)
    success, encoded = cv2.imencode(".png", image)
    assert success

    with TestClient(create_app()) as client:
        response = client.post(
            "/api/v1/operations/remove_background/execute",
            data={"payload": json.dumps({
                "params": {"x": 28, "y": 12, "width": 74, "height": 74, "iterations": 2},
                "image_inputs": [{"input_name": "image", "file_index": 0}],
            })},
            files=[("files", ("sample.png", encoded.tobytes(), "image/png"))],
        )

    assert response.status_code == 200, response.text
    image_result = response.json()["output"]["images"]["image"]
    assert image_result["media_type"] == "image/png"
    decoded = cv2.imdecode(
        np.frombuffer(base64.b64decode(image_result["data"]), dtype=np.uint8),
        cv2.IMREAD_UNCHANGED,
    )
    assert decoded.shape == (96, 128, 4)
    assert np.any(decoded[:, :, 3] == 0)
    assert np.any(decoded[:, :, 3] == 255)
