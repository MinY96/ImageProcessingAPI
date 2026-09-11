import json

import cv2
import numpy as np
from fastapi.testclient import TestClient

from src.api import ApiSettings, create_app
from src.pipeline import pipeline_input, step_output
from src.schemas import InputKind, InputSlotSpec, PipelineSpec, PipelineStepSpec


def make_custom_recipe(name: str = "custom_edge", kernel_size: int = 3) -> PipelineSpec:
    return PipelineSpec(
        name=name,
        display_name="Custom Edge",
        description="custom recipe for API tests",
        inputs=[InputSlotSpec(name="image", kind=InputKind.IMAGE)],
        steps=[
            PipelineStepSpec(
                id="gray",
                operation="convert_color",
                inputs={"image": pipeline_input("image")},
                params={"target_color_space": "gray"},
            ),
            PipelineStepSpec(
                id="blur",
                operation="gaussian_blur",
                inputs={"image": step_output("gray")},
                params={"kernel_size": kernel_size},
            ),
            PipelineStepSpec(
                id="edges",
                operation="canny",
                inputs={"image": step_output("blur")},
                params={"threshold_low": 50, "threshold_high": 150},
            ),
        ],
        outputs={"edges": step_output("edges")},
    )


def make_settings(tmp_path) -> ApiSettings:
    return ApiSettings(
        recipe_store_dir=tmp_path / "recipes",
        label_store_dir=tmp_path / "labels",
    )


def image_upload_payload() -> tuple[str, list[tuple[str, tuple[str, bytes, str]]]]:
    image = np.zeros((20, 24, 3), dtype=np.uint8)
    image[5:15, 7:17] = 255
    ok, encoded = cv2.imencode(".png", image)
    assert ok
    payload = json.dumps(
        {
            "image_inputs": [{"input_name": "image", "file_index": 0}],
            "retain_intermediates": True,
        }
    )
    files = [("files", ("input.png", encoded.tobytes(), "image/png"))]
    return payload, files


def test_recipe_api_lists_builtin_recipes(tmp_path):
    with TestClient(create_app(settings=make_settings(tmp_path))) as client:
        response = client.get("/api/v1/recipes")
        detail = client.get("/api/v1/recipes/sem_profile_edges")

    assert response.status_code == 200
    names = [item["name"] for item in response.json()]
    assert "sem_profile_edges" in names
    assert detail.status_code == 200
    assert detail.json()["source"] == "builtin"
    assert detail.json()["readonly"] is True


def test_recipe_crud_revision_and_pipeline_catalog_sync(tmp_path):
    settings = make_settings(tmp_path)
    pipeline = make_custom_recipe()

    with TestClient(create_app(settings=settings)) as client:
        created = client.post(
            "/api/v1/recipes",
            json={"pipeline": pipeline.model_dump(mode="json"), "tags": ["sem", "edge", "sem"]},
        )
        assert created.status_code == 201
        assert created.json()["revision"] == 1
        assert created.json()["tags"] == ["edge", "sem"]

        pipeline_listing = client.get("/api/v1/pipelines")
        assert "custom_edge" in [item["name"] for item in pipeline_listing.json()]

        updated_pipeline = make_custom_recipe(kernel_size=5)
        updated = client.put(
            "/api/v1/recipes/custom_edge",
            json={
                "pipeline": updated_pipeline.model_dump(mode="json"),
                "tags": ["updated"],
                "expected_revision": 1,
            },
        )
        assert updated.status_code == 200
        assert updated.json()["revision"] == 2
        assert updated.json()["pipeline"]["steps"][1]["params"]["kernel_size"] == 5

        conflict = client.put(
            "/api/v1/recipes/custom_edge",
            json={
                "pipeline": updated_pipeline.model_dump(mode="json"),
                "tags": [],
                "expected_revision": 1,
            },
        )
        assert conflict.status_code == 409
        assert conflict.json()["error"]["code"] == "recipe_revision_conflict"

        deleted = client.delete(
            "/api/v1/recipes/custom_edge",
            params={"expected_revision": 2},
        )
        assert deleted.status_code == 204
        assert client.get("/api/v1/recipes/custom_edge").status_code == 404
        assert client.get("/api/v1/pipelines/custom_edge").status_code == 404


def test_recipe_api_rejects_builtin_changes_and_duplicate_names(tmp_path):
    settings = make_settings(tmp_path)
    pipeline = make_custom_recipe(name="sem_profile_edges")

    with TestClient(create_app(settings=settings)) as client:
        duplicate = client.post(
            "/api/v1/recipes",
            json={"pipeline": pipeline.model_dump(mode="json")},
        )
        assert duplicate.status_code == 409

        builtin = client.get("/api/v1/recipes/sem_profile_edges").json()
        update = client.put(
            "/api/v1/recipes/sem_profile_edges",
            json={"pipeline": builtin["pipeline"], "tags": []},
        )
        delete = client.delete("/api/v1/recipes/sem_profile_edges")

    assert update.status_code == 403
    assert delete.status_code == 403



def test_clone_builtin_recipe_to_user_recipe(tmp_path):
    settings = make_settings(tmp_path)
    with TestClient(create_app(settings=settings)) as client:
        cloned = client.post(
            "/api/v1/recipes/sem_profile_edges/clone",
            json={
                "name": "sem_profile_edges_custom",
                "display_name": "SEM Profile Edges Custom",
                "tags": ["sem", "custom"],
            },
        )
        assert cloned.status_code == 201
        body = cloned.json()
        assert body["source"] == "user"
        assert body["readonly"] is False
        assert body["pipeline"]["name"] == "sem_profile_edges_custom"
        assert body["pipeline"]["display_name"] == "SEM Profile Edges Custom"

        updated_pipeline = body["pipeline"]
        updated_pipeline["description"] = "edited after cloning"
        updated = client.put(
            "/api/v1/recipes/sem_profile_edges_custom",
            json={
                "pipeline": updated_pipeline,
                "tags": body["tags"],
                "expected_revision": 1,
            },
        )
        assert updated.status_code == 200
        assert updated.json()["pipeline"]["description"] == "edited after cloning"

def test_recipe_persists_across_app_restart(tmp_path):
    settings = make_settings(tmp_path)
    pipeline = make_custom_recipe()

    with TestClient(create_app(settings=settings)) as client:
        assert client.post(
            "/api/v1/recipes",
            json={"pipeline": pipeline.model_dump(mode="json"), "tags": ["persisted"]},
        ).status_code == 201

    with TestClient(create_app(settings=settings)) as client:
        detail = client.get("/api/v1/recipes/custom_edge")
        pipeline_detail = client.get("/api/v1/pipelines/custom_edge")

    assert detail.status_code == 200
    assert detail.json()["tags"] == ["persisted"]
    assert pipeline_detail.status_code == 200


def test_execute_user_recipe(tmp_path):
    settings = make_settings(tmp_path)
    pipeline = make_custom_recipe()
    payload, files = image_upload_payload()

    with TestClient(create_app(settings=settings)) as client:
        assert client.post(
            "/api/v1/recipes",
            json={"pipeline": pipeline.model_dump(mode="json")},
        ).status_code == 201
        response = client.post(
            "/api/v1/recipes/custom_edge/execute",
            data={"payload": payload},
            files=files,
        )

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert list(response.json()["intermediates"]) == ["gray", "blur", "edges"]


def base_label_request(image_id: str = "sem_0001") -> dict:
    return {
        "image_id": image_id,
        "image_name": "SEM_0001.png",
        "source_uri": "dataset/SEM_0001.png",
        "width": 640,
        "height": 480,
        "tags": ["sem", "training"],
        "metadata": {"equipment": "SEM01"},
        "annotations": [
            {
                "type": "bbox",
                "label": "bridge",
                "x": 10,
                "y": 20,
                "width": 100,
                "height": 80,
            },
            {
                "type": "polygon",
                "label": "residue",
                "points": [
                    {"x": 200, "y": 200},
                    {"x": 250, "y": 210},
                    {"x": 230, "y": 260},
                ],
            },
        ],
    }


def test_label_document_crud_and_persistence(tmp_path):
    settings = make_settings(tmp_path)
    with TestClient(create_app(settings=settings)) as client:
        created = client.post("/api/v1/labels", json=base_label_request())
        assert created.status_code == 201
        body = created.json()
        assert body["revision"] == 1
        assert len(body["annotations"]) == 2
        assert all(item["annotation_id"] for item in body["annotations"])

        detail = client.get("/api/v1/labels/sem_0001")
        listing = client.get("/api/v1/labels", params={"label": "bridge"})
        assert detail.status_code == 200
        assert listing.json()["total"] == 1
        assert listing.json()["items"][0]["labels"] == ["bridge", "residue"]

    with TestClient(create_app(settings=settings)) as client:
        persisted = client.get("/api/v1/labels/sem_0001")
    assert persisted.status_code == 200
    assert persisted.json()["metadata"]["equipment"] == "SEM01"


def test_label_annotation_crud_and_classes(tmp_path):
    settings = make_settings(tmp_path)
    with TestClient(create_app(settings=settings)) as client:
        created = client.post("/api/v1/labels", json=base_label_request()).json()

        added = client.post(
            "/api/v1/labels/sem_0001/annotations",
            json={
                "expected_revision": 1,
                "annotation": {
                    "type": "point",
                    "label": "center",
                    "point": {"x": 320, "y": 240},
                },
            },
        )
        assert added.status_code == 200
        assert added.json()["revision"] == 2
        point = next(item for item in added.json()["annotations"] if item["type"] == "point")

        updated = client.put(
            f"/api/v1/labels/sem_0001/annotations/{point['annotation_id']}",
            json={
                "expected_revision": 2,
                "annotation": {
                    "type": "point",
                    "label": "center_updated",
                    "point": {"x": 300, "y": 220},
                },
            },
        )
        assert updated.status_code == 200
        assert updated.json()["revision"] == 3

        classes = client.get("/api/v1/labels/classes")
        assert classes.status_code == 200
        assert {item["label"] for item in classes.json()} == {
            "bridge",
            "center_updated",
            "residue",
        }

        deleted = client.delete(
            f"/api/v1/labels/sem_0001/annotations/{point['annotation_id']}",
            params={"expected_revision": 3},
        )
        assert deleted.status_code == 200
        assert deleted.json()["revision"] == 4
        assert all(item["annotation_id"] != point["annotation_id"] for item in deleted.json()["annotations"])


def test_label_rejects_out_of_bounds_and_revision_conflicts(tmp_path):
    settings = make_settings(tmp_path)
    with TestClient(create_app(settings=settings)) as client:
        request = base_label_request()
        request["annotations"] = [
            {
                "type": "bbox",
                "label": "bad",
                "x": 600,
                "y": 450,
                "width": 100,
                "height": 50,
            }
        ]
        invalid = client.post("/api/v1/labels", json=request)
        assert invalid.status_code == 422
        assert invalid.json()["error"]["code"] == "label_validation_error"

        assert client.post("/api/v1/labels", json=base_label_request()).status_code == 201
        conflict = client.post(
            "/api/v1/labels/sem_0001/annotations",
            json={
                "expected_revision": 99,
                "annotation": {
                    "type": "point",
                    "label": "center",
                    "point": {"x": 100, "y": 100},
                },
            },
        )
        assert conflict.status_code == 409
        assert conflict.json()["error"]["code"] == "label_revision_conflict"


def test_replace_and_delete_label_document(tmp_path):
    settings = make_settings(tmp_path)
    with TestClient(create_app(settings=settings)) as client:
        assert client.post("/api/v1/labels", json=base_label_request()).status_code == 201

        replacement = base_label_request()
        replacement.pop("image_id")
        replacement["image_name"] = "SEM_0001_REVIEWED.png"
        replacement["annotations"] = []
        replacement["expected_revision"] = 1
        updated = client.put("/api/v1/labels/sem_0001", json=replacement)
        assert updated.status_code == 200
        assert updated.json()["revision"] == 2
        assert updated.json()["annotations"] == []

        stale_delete = client.delete(
            "/api/v1/labels/sem_0001",
            params={"expected_revision": 1},
        )
        assert stale_delete.status_code == 409

        deleted = client.delete(
            "/api/v1/labels/sem_0001",
            params={"expected_revision": 2},
        )
        assert deleted.status_code == 204
        assert client.get("/api/v1/labels/sem_0001").status_code == 404


def test_openapi_contains_recipe_and_label_routes(tmp_path):
    with TestClient(create_app(settings=make_settings(tmp_path))) as client:
        paths = client.get("/openapi.json").json()["paths"]

    assert "/api/v1/recipes" in paths
    assert "/api/v1/recipes/{recipe_name}/execute" in paths
    assert "/api/v1/labels" in paths
    assert "/api/v1/labels/{image_id}/annotations/{annotation_id}" in paths
