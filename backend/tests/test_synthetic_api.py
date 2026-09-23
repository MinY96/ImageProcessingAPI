import base64
import io
import json
import zipfile
from pathlib import Path

import cv2
import numpy as np
from fastapi.testclient import TestClient

from src.api import ApiSettings, create_app


def _png_bytes(image: np.ndarray) -> bytes:
    ok, encoded = cv2.imencode(".png", image)
    assert ok
    return encoded.tobytes()


def _client(tmp_path: Path) -> TestClient:
    settings = ApiSettings(
        recipe_store_dir=tmp_path / "store" / "recipes",
        label_store_dir=tmp_path / "store" / "labels",
        test_dataset_store_dir=tmp_path / "store" / "test_datasets",
        evaluation_store_dir=tmp_path / "store" / "evaluations",
        synthetic_asset_store_dir=tmp_path / "store" / "synthetic" / "assets",
        synthetic_diffusion_cache_dir=tmp_path / "store" / "models" / "diffusion",
        synthetic_diffusion_local_files_only=True,
        synthetic_diffusion_device="cpu",
    )
    return TestClient(create_app(settings=settings))


def test_synthetic_methods_and_diffusion_status(tmp_path: Path):
    with _client(tmp_path) as client:
        methods = client.get("/api/v1/synthetic/methods")
        assert methods.status_code == 200
        values = {item["method"] for item in methods.json()}
        assert {
            "procedural",
            "cut_paste",
            "alpha_blend",
            "seamless_clone",
            "asset_composite",
            "diffusion_inpaint",
        } <= values

        models = client.get("/api/v1/synthetic/diffusion/models")
        assert models.status_code == 200
        keys = {item["model"] for item in models.json()}
        assert {"sdxl_inpaint", "flux_fill", "sd15_openvino_inpaint"} <= keys

        openvino = next(
            item for item in models.json() if item["model"] == "sd15_openvino_inpaint"
        )
        assert openvino["device"] == "AUTO"
        assert "512x512" in openvino["notes"]

        presets = client.get("/api/v1/synthetic/diffusion/prompt-presets")
        assert presets.status_code == 200
        preset_keys = {item["key"] for item in presets.json()}
        assert {"small_pooling", "tear_with_seepage", "downward_drip"} <= preset_keys


def test_procedural_generation_preserves_outside_mask(tmp_path: Path):
    image = np.full((96, 128, 3), 170, dtype=np.uint8)
    payload = {
        "method": "procedural",
        "defect_type": "liquid_pool",
        "severity": 0.6,
        "count": 2,
        "seed": 100,
        "mask": {
            "type": "ellipse",
            "center_x": 0.5,
            "center_y": 0.5,
            "width_ratio": 0.25,
            "height_ratio": 0.2,
            "feather_px": 4,
        },
        "parameters": {
            "pattern": "pooling",
            "opacity": 0.55,
        },
    }
    with _client(tmp_path) as client:
        response = client.post(
            "/api/v1/synthetic/generate",
            data={"payload": json.dumps(payload)},
            files={"source_image": ("source.png", _png_bytes(image), "image/png")},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["success"] is True
        assert len(body["candidates"]) == 2
        assert body["candidates"][0]["seed"] == 100
        assert body["candidates"][1]["seed"] == 101
        quality = body["candidates"][0]["metadata"]["quality"]
        assert quality["outside_mask_mean_abs_diff"] == 0.0
        assert quality["outside_mask_max_abs_diff"] == 0.0
        assert quality["inside_mask_mean_abs_diff"] > 0.0
        encoded = body["candidates"][0]["images"]["image"]["data"]
        result = cv2.imdecode(np.frombuffer(base64.b64decode(encoded), dtype=np.uint8), cv2.IMREAD_COLOR)
        assert result.shape == image.shape
        assert np.any(result != image)


def test_synthetic_zip_contains_image_mask_difference_and_manifest(tmp_path: Path):
    image = np.full((64, 64, 3), 140, dtype=np.uint8)
    payload = {
        "method": "procedural",
        "defect_type": "crack",
        "count": 1,
        "seed": 7,
        "mask": {
            "type": "crack",
            "center_x": 0.5,
            "center_y": 0.5,
            "width_ratio": 0.6,
            "height_ratio": 0.08,
            "feather_px": 1,
        },
        "parameters": {"pattern": "crack", "opacity": 0.9},
    }
    with _client(tmp_path) as client:
        response = client.post(
            "/api/v1/synthetic/generate?response_format=zip",
            data={"payload": json.dumps(payload)},
            files={"source_image": ("source.png", _png_bytes(image), "image/png")},
        )
        assert response.status_code == 200, response.text
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            names = set(archive.namelist())
            assert "manifest.json" in names
            assert "candidates/00/image.png" in names
            assert "candidates/00/mask.png" in names
            assert "candidates/00/difference.png" in names


def test_asset_library_and_alpha_blend(tmp_path: Path):
    source = np.full((96, 128, 3), 120, dtype=np.uint8)
    asset = np.zeros((32, 32, 3), dtype=np.uint8)
    cv2.circle(asset, (16, 16), 10, (230, 230, 230), -1)
    mask = np.zeros((32, 32), dtype=np.uint8)
    cv2.circle(mask, (16, 16), 10, 255, -1)

    with _client(tmp_path) as client:
        create = client.post(
            "/api/v1/synthetic/assets",
            data={
                "payload": json.dumps(
                    {
                        "asset_id": "droplet_001",
                        "name": "Droplet 001",
                        "category": "droplet",
                        "tags": ["photo"],
                    }
                )
            },
            files={
                "image": ("asset.png", _png_bytes(asset), "image/png"),
                "mask": ("mask.png", _png_bytes(mask), "image/png"),
            },
        )
        assert create.status_code == 201, create.text
        assert create.json()["asset_id"] == "droplet_001"
        assert create.json()["has_mask"] is True

        listing = client.get("/api/v1/synthetic/assets", params={"category": "droplet"})
        assert listing.status_code == 200
        assert len(listing.json()) == 1

        payload = {
            "method": "alpha_blend",
            "defect_type": "droplet",
            "severity": 0.5,
            "seed": 11,
            "asset_id": "droplet_001",
            "mask": {
                "type": "ellipse",
                "center_x": 0.55,
                "center_y": 0.45,
                "width_ratio": 0.25,
                "height_ratio": 0.25,
            },
            "parameters": {"opacity": 0.8},
        }
        generated = client.post(
            "/api/v1/synthetic/generate",
            data={"payload": json.dumps(payload)},
            files={"source_image": ("source.png", _png_bytes(source), "image/png")},
        )
        assert generated.status_code == 200, generated.text
        quality = generated.json()["candidates"][0]["metadata"]["quality"]
        assert quality["inside_mask_mean_abs_diff"] > 0

        preview = client.get("/api/v1/synthetic/assets/droplet_001/image")
        assert preview.status_code == 200
        assert preview.headers["content-type"].startswith("image/png")

        deleted = client.delete("/api/v1/synthetic/assets/droplet_001")
        assert deleted.status_code == 204
        assert client.get("/api/v1/synthetic/assets/droplet_001").status_code == 404
