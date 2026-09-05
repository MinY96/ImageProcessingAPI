import base64
import io
import json
import zipfile

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from src.api import ApiSettings, create_app
from src.machine_learning import train_knn
from src.pipeline import pipeline_input, step_output
from src.schemas import (
    InputKind,
    InputSlotSpec,
    PipelineSpec,
    PipelineStepSpec,
)


def make_pipeline() -> PipelineSpec:
    return PipelineSpec(
        name="edge_thumbnail",
        display_name="Edge Thumbnail",
        inputs=[
            InputSlotSpec(name="image", kind=InputKind.IMAGE)
        ],
        steps=[
            PipelineStepSpec(
                id="blur",
                operation="gaussian_blur",
                inputs={"image": pipeline_input("image")},
                params={"kernel_size": 3},
            ),
            PipelineStepSpec(
                id="resize",
                operation="resize",
                inputs={"image": step_output("blur")},
                params={"width": 10, "height": 8},
            ),
            PipelineStepSpec(
                id="edges",
                operation="canny",
                inputs={"image": step_output("resize")},
                params={
                    "threshold_low": 50,
                    "threshold_high": 150,
                },
            ),
        ],
        outputs={"edges": step_output("edges")},
    )


@pytest.fixture
def image_bytes() -> bytes:
    image = np.zeros((16, 20), dtype=np.uint8)
    image[4:12, 6:14] = 255
    success, encoded = cv2.imencode(".png", image)
    assert success
    return encoded.tobytes()


@pytest.fixture
def client():
    app = create_app(pipelines=[make_pipeline()])
    with TestClient(app) as test_client:
        yield test_client


def image_form_payload(**extra):
    payload = {
        "image_inputs": [
            {"input_name": "image", "file_index": 0}
        ]
    }
    payload.update(extra)
    return json.dumps(payload)


def image_upload(image_bytes):
    return [
        ("files", ("input.png", image_bytes, "image/png"))
    ]


def test_health_and_openapi(client):
    assert client.get("/api/v1/health").json() == {"status": "ok"}
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert "/api/v1/operations" in response.json()["paths"]
    assert "/api/v1/models" in response.json()["paths"]


def test_default_app_registers_builtin_pipeline():
    with TestClient(create_app()) as test_client:
        response = test_client.get("/api/v1/pipelines")

    assert response.status_code == 200
    assert [item["name"] for item in response.json()] == [
        "binary_mask_cleanup",
        "cinematic_3d_lut",
        "circle_detection",
        "clean_portrait",
        "color_segmentation",
        "comic_style",
        "document_adaptive",
        "document_otsu",
        "dramatic_detail",
        "edge_thumbnail",
        "film_look",
        "general_edge_detection",
        "line_detection",
        "masked_local_enhancement",
        "natural_enhance",
        "pencil_sketch",
        "reference_difference",
        "seamless_composite",
        "sem_profile_edges",
        "vintage_1d_lut",
    ]


def test_default_pipeline_accepts_bgr_upload():
    image = np.zeros((32, 48, 3), dtype=np.uint8)
    image[8:24, 12:36] = (20, 180, 240)
    success, encoded = cv2.imencode(".png", image)
    assert success

    with TestClient(create_app()) as test_client:
        response = test_client.post(
            "/api/v1/pipelines/edge_thumbnail/execute",
            data={"payload": image_form_payload()},
            files=image_upload(encoded.tobytes()),
        )

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert [step["step_id"] for step in response.json()["steps"]] == [
        "gray",
        "blur",
        "resize",
        "edges",
    ]


def test_list_and_get_operations(client):
    response = client.get("/api/v1/operations")
    assert response.status_code == 200
    names = [item["name"] for item in response.json()]
    assert names == sorted(names)
    assert len(names) == 64
    assert {
        "adjust_tone",
        "apply_3d_lut",
        "blend_images",
        "canny",
        "draw_annotations",
        "feature_match",
        "gaussian_blur",
        "kmeans_segmentation",
        "model_predict",
        "seamless_clone",
        "resize",
    } <= set(names)

    detail = client.get("/api/v1/operations/canny")
    assert detail.status_code == 200
    assert detail.json()["constraints"][0]["type"] == "less_than"

    missing = client.get("/api/v1/operations/missing")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "operation_not_found"


def test_model_registry_query_and_prediction_api():
    model = train_knn(
        [[0.0, 0.0], [0.0, 1.0], [8.0, 8.0], [9.0, 8.0]],
        [0, 0, 1, 1],
        model_id="api_knn",
        version="1.0.0",
        feature_schema="xy-v1",
        default_k=1,
        label_names={0: "low", 1: "high"},
    )
    with TestClient(create_app(models=[model])) as model_client:
        listing = model_client.get("/api/v1/models")
        detail = model_client.get("/api/v1/models/api_knn/1.0.0")
        prediction = model_client.post(
            "/api/v1/operations/model_predict/execute",
            data={
                "payload": json.dumps(
                    {
                        "inputs": {"features": [[0.2, 0.1], [8.4, 8.2]]},
                        "model_inputs": [
                            {
                                "input_name": "model",
                                "model_id": "api_knn",
                                "version": "1.0.0",
                            }
                        ],
                        "params": {"knn_k": 1},
                    }
                )
            },
        )

    assert listing.status_code == 200
    assert listing.json()[0]["model_id"] == "api_knn"
    assert detail.status_code == 200
    assert detail.json()["algorithm"] == "knn"
    assert prediction.status_code == 200
    assert prediction.json()["output"]["data"]["predictions"] == [[0.0], [1.0]]


def test_model_prediction_api_rejects_unknown_model():
    with TestClient(create_app()) as model_client:
        response = model_client.post(
            "/api/v1/operations/model_predict/execute",
            data={
                "payload": json.dumps(
                    {
                        "inputs": {"features": [[0.0, 0.0]]},
                        "model_inputs": [
                            {
                                "input_name": "model",
                                "model_id": "missing",
                                "version": "1.0.0",
                            }
                        ],
                    }
                )
            },
        )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "model_not_found"


def test_execute_operation_json(client, image_bytes):
    response = client.post(
        "/api/v1/operations/gaussian_blur/execute",
        data={
            "payload": image_form_payload(
                params={"kernel_size": 3}
            )
        },
        files=image_upload(image_bytes),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    encoded = base64.b64decode(
        body["output"]["images"]["image"]["data"]
    )
    decoded = cv2.imdecode(
        np.frombuffer(encoded, dtype=np.uint8),
        cv2.IMREAD_UNCHANGED,
    )
    assert decoded.shape == (16, 20)


def test_execute_operation_zip(client, image_bytes):
    response = client.post(
        (
            "/api/v1/operations/gaussian_blur/execute"
            "?response_format=zip"
        ),
        data={
            "payload": image_form_payload(
                params={"kernel_size": 3}
            )
        },
        files=image_upload(image_bytes),
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"

    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert set(archive.namelist()) == {
            "manifest.json",
            "output/image.png",
        }
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["success"] is True


def test_execute_color_conversion_through_api(client):
    image = np.zeros((12, 16, 3), dtype=np.uint8)
    image[:, :8] = (255, 0, 0)
    success, encoded = cv2.imencode(".png", image)
    assert success

    response = client.post(
        "/api/v1/operations/convert_color/execute",
        data={
            "payload": image_form_payload(
                params={"target_color_space": "gray"}
            )
        },
        files=image_upload(encoded.tobytes()),
    )

    assert response.status_code == 200
    image_info = response.json()["output"]["images"]["image"]
    assert image_info["color_space"] == "gray"
    assert image_info["shape"] == [12, 16]


def test_execute_draw_annotations_through_api(client, image_bytes):
    response = client.post(
        "/api/v1/operations/draw_annotations/execute",
        data={
            "payload": image_form_payload(
                inputs={
                    "annotations": [
                        {
                            "type": "circle",
                            "center": [10, 8],
                            "radius": 4,
                            "color": [0, 0, 255],
                        }
                    ]
                }
            )
        },
        files=image_upload(image_bytes),
    )

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["output"]["images"]["image"]["color_space"] == "bgr"


def test_execute_template_matching_with_two_uploads(client):
    image = np.zeros((40, 50), dtype=np.uint8)
    image[12:24, 18:32] = 220
    image[15:18, 20:30] = 80
    template = image[10:26, 16:34].copy()
    image_ok, image_encoded = cv2.imencode(".png", image)
    template_ok, template_encoded = cv2.imencode(".png", template)
    assert image_ok and template_ok

    payload = {
        "params": {"method": "sqdiff_normed"},
        "image_inputs": [
            {"input_name": "image", "file_index": 0},
            {"input_name": "template", "file_index": 1},
        ],
    }
    response = client.post(
        "/api/v1/operations/template_match/execute",
        data={"payload": json.dumps(payload)},
        files=[
            (
                "files",
                ("image.png", image_encoded.tobytes(), "image/png"),
            ),
            (
                "files",
                (
                    "template.png",
                    template_encoded.tobytes(),
                    "image/png",
                ),
            ),
        ],
    )

    assert response.status_code == 200
    best_match = response.json()["output"]["data"]["best_match"]
    assert best_match["top_left"] == [16, 10]


def test_execute_affine_with_json_point_inputs(client, image_bytes):
    payload = {
        "inputs": {
            "source_points": [[0, 0], [19, 0], [0, 15]],
            "destination_points": [[1, 1], [18, 0], [0, 14]],
        },
        "params": {"width": 20, "height": 16},
        "image_inputs": [
            {"input_name": "image", "file_index": 0}
        ],
    }
    response = client.post(
        "/api/v1/operations/warp_affine/execute",
        data={"payload": json.dumps(payload)},
        files=image_upload(image_bytes),
    )

    assert response.status_code == 200
    assert response.json()["output"]["images"]["image"]["shape"] == [
        16,
        20,
    ]


def test_execute_custom_filter_with_json_kernel(client, image_bytes):
    payload = {
        "inputs": {
            "kernel": [
                [0.0, -1.0, 0.0],
                [-1.0, 5.0, -1.0],
                [0.0, -1.0, 0.0],
            ]
        },
        "image_inputs": [
            {"input_name": "image", "file_index": 0}
        ],
    }
    response = client.post(
        "/api/v1/operations/filter_2d/execute",
        data={"payload": json.dumps(payload)},
        files=image_upload(image_bytes),
    )

    assert response.status_code == 200
    assert response.json()["success"] is True


def test_operation_validation_error_is_422(client, image_bytes):
    response = client.post(
        "/api/v1/operations/gaussian_blur/execute",
        data={
            "payload": image_form_payload(
                params={"kernel_size": 4}
            )
        },
        files=image_upload(image_bytes),
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == (
        "parameter_validation_error"
    )


def test_invalid_multipart_payload_is_422(client):
    response = client.post(
        "/api/v1/operations/gaussian_blur/execute",
        data={"payload": "not-json"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_payload"


def test_missing_form_payload_uses_api_error_shape(client):
    response = client.post(
        "/api/v1/operations/gaussian_blur/execute"
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == (
        "request_validation_error"
    )


def test_invalid_upload_media_type_is_415(client):
    response = client.post(
        "/api/v1/operations/gaussian_blur/execute",
        data={"payload": image_form_payload()},
        files=[("files", ("input.txt", b"hello", "text/plain"))],
    )

    assert response.status_code == 415
    assert response.json()["error"]["code"] == (
        "unsupported_media_type"
    )


def test_list_get_and_validate_pipeline(client):
    listed = client.get("/api/v1/pipelines")
    assert listed.status_code == 200
    assert [item["name"] for item in listed.json()] == [
        "edge_thumbnail"
    ]

    detail = client.get("/api/v1/pipelines/edge_thumbnail")
    assert detail.status_code == 200
    assert len(detail.json()["steps"]) == 3

    valid = client.post(
        "/api/v1/pipelines/validate",
        json=make_pipeline().model_dump(mode="json"),
    )
    assert valid.status_code == 200
    assert valid.json()["valid"] is True
    assert valid.json()["output_names"] == ["edges"]


def test_execute_registered_pipeline(client, image_bytes):
    response = client.post(
        "/api/v1/pipelines/edge_thumbnail/execute",
        data={"payload": image_form_payload()},
        files=image_upload(image_bytes),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert [item["step_id"] for item in body["steps"]] == [
        "blur",
        "resize",
        "edges",
    ]
    assert body["output"]["images"]["edges"]["shape"] == [8, 10]


def test_execute_ad_hoc_pipeline(client, image_bytes):
    payload = json.loads(image_form_payload())
    payload["pipeline"] = make_pipeline().model_dump(mode="json")

    response = client.post(
        "/api/v1/pipelines/execute",
        data={"payload": json.dumps(payload)},
        files=image_upload(image_bytes),
    )

    assert response.status_code == 200
    assert response.json()["pipeline"] == "edge_thumbnail"


def test_missing_pipeline_is_404(client):
    response = client.get("/api/v1/pipelines/missing")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "pipeline_not_found"


def test_upload_size_limit_is_413(image_bytes):
    app = create_app(
        settings=ApiSettings(max_upload_bytes_per_file=1024)
    )
    with TestClient(app) as test_client:
        response = test_client.post(
            "/api/v1/operations/gaussian_blur/execute",
            data={"payload": image_form_payload()},
            files=image_upload(image_bytes * 100),
        )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "upload_too_large"
