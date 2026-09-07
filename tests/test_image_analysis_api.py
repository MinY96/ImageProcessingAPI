import json

import cv2
import numpy as np
from fastapi.testclient import TestClient

from src.analysis import AnalysisOptions, ImageAnalyzer
from src.api import create_app
from src.schemas import ColorSpace, ImageData


def _encode_png(image: np.ndarray) -> bytes:
    ok, encoded = cv2.imencode(".png", image)
    assert ok
    return encoded.tobytes()


def _pipeline_payload(*, analysis=None, retain_intermediates=False, analyze_intermediates=False):
    body = {
        "image_inputs": [{"input_name": "image", "file_index": 0}],
        "retain_intermediates": retain_intermediates,
        "analyze_intermediates": analyze_intermediates,
    }
    if analysis is not None:
        body["analysis"] = analysis
    return json.dumps(body)


def test_analyze_grayscale_image_endpoint():
    image = np.tile(np.arange(64, dtype=np.uint8), (32, 1))
    encoded = _encode_png(image)

    with TestClient(create_app()) as client:
        response = client.post(
            "/api/v1/analysis/image",
            data={"payload": "{}"},
            files={"file": ("gray.png", encoded, "image/png")},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["metadata"]["width"] == 64
    assert body["metadata"]["height"] == 32
    assert body["metadata"]["channels"] == 1
    assert body["metadata"]["bit_depth_per_channel"] == 8
    assert body["metadata"]["pixel_count"] == 64 * 32
    assert body["metadata"]["source_size_bytes"] == len(encoded)
    assert body["histograms"]["gray"]["bins"] == 256
    assert body["histograms"]["rgb"] == {}
    assert body["histograms"]["hsv"] == {}
    assert len(body["profiles"]["x"]["sum_profile"]) == 64
    assert len(body["profiles"]["y"]["derivative_profile"]) == 32
    assert body["features"]["edge_density"] >= 0.0


def test_analyze_color_image_returns_rgb_and_hsv_histograms():
    image = np.zeros((24, 30, 3), dtype=np.uint8)
    image[:, :10] = (255, 0, 0)
    image[:, 10:20] = (0, 255, 0)
    image[:, 20:] = (0, 0, 255)

    with TestClient(create_app()) as client:
        response = client.post(
            "/api/v1/analysis/image",
            data={"payload": "{}"},
            files={"file": ("color.png", _encode_png(image), "image/png")},
        )

    body = response.json()
    assert response.status_code == 200
    assert set(body["histograms"]["rgb"]) == {"r", "g", "b"}
    assert set(body["histograms"]["hsv"]) == {"h", "s", "v"}
    assert set(body["channel_statistics"]) == {"r", "g", "b"}
    assert body["features"]["mean_saturation"] is not None
    assert body["features"]["colorfulness"] is not None


def test_operation_result_can_include_analysis():
    image = np.zeros((32, 32), dtype=np.uint8)
    image[8:24, 8:24] = 255
    payload = {
        "image_inputs": [{"input_name": "image", "file_index": 0}],
        "params": {"kernel_size": 3},
        "analysis": {
            "include_hsv_histogram": False,
            "include_profiles": False,
        },
    }

    with TestClient(create_app()) as client:
        response = client.post(
            "/api/v1/operations/gaussian_blur/execute",
            data={"payload": json.dumps(payload)},
            files=[("files", ("input.png", _encode_png(image), "image/png"))],
        )

    assert response.status_code == 200
    analysis = response.json()["output"]["images"]["image"]["analysis"]
    assert analysis["metadata"]["width"] == 32
    assert analysis["histograms"]["gray"] is not None
    assert analysis["profiles"]["x"] is None


def test_recipe_result_analysis_does_not_analyze_intermediates_by_default():
    image = np.zeros((48, 64, 3), dtype=np.uint8)
    image[12:36, 16:48] = (200, 200, 200)

    with TestClient(create_app()) as client:
        response = client.post(
            "/api/v1/recipes/edge_thumbnail/execute",
            data={
                "payload": _pipeline_payload(
                    analysis={"include_profiles": False},
                    retain_intermediates=True,
                )
            },
            files=[("files", ("input.png", _encode_png(image), "image/png"))],
        )

    body = response.json()
    assert response.status_code == 200
    assert "analysis" in next(iter(body["output"]["images"].values()))
    first_step = next(iter(body["intermediates"].values()))
    first_image = next(iter(first_step["images"].values()))
    assert "analysis" not in first_image


def test_recipe_result_can_analyze_intermediates_on_demand():
    image = np.zeros((48, 64, 3), dtype=np.uint8)
    image[12:36, 16:48] = (200, 200, 200)

    with TestClient(create_app()) as client:
        response = client.post(
            "/api/v1/recipes/edge_thumbnail/execute",
            data={
                "payload": _pipeline_payload(
                    analysis={"include_profiles": False},
                    retain_intermediates=True,
                    analyze_intermediates=True,
                )
            },
            files=[("files", ("input.png", _encode_png(image), "image/png"))],
        )

    body = response.json()
    assert response.status_code == 200
    analyzed_steps = [
        image_meta
        for step in body["intermediates"].values()
        for image_meta in step["images"].values()
        if "analysis" in image_meta
    ]
    assert analyzed_steps


def test_uint16_analysis_reports_bit_depth_and_histogram_range():
    image = np.linspace(0, 65535, 256, dtype=np.uint16).reshape(16, 16)
    result = ImageAnalyzer().analyze(
        ImageData(data=image, color_space=ColorSpace.GRAY),
        options=AnalysisOptions(include_profiles=False),
    )

    assert result.metadata.bit_depth_per_channel == 16
    assert result.metadata.bits_per_pixel == 16
    assert result.histograms.gray is not None
    assert result.histograms.gray.range_min == 0.0
    assert result.histograms.gray.range_max == 65536.0


def test_profile_is_downsampled_for_wide_image():
    image = np.tile(np.arange(1000, dtype=np.uint16), (8, 1))
    result = ImageAnalyzer().analyze(
        ImageData(data=image, color_space=ColorSpace.GRAY),
        options=AnalysisOptions(
            include_features=False,
            include_gray_histogram=False,
            profile_max_points=128,
        ),
    )

    assert result.profiles.x is not None
    assert result.profiles.x.original_length == 1000
    assert result.profiles.x.sampled_length == 128
    assert result.profiles.x.downsampled is True
