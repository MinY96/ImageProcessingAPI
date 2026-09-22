from pathlib import Path
import time

import cv2
import numpy as np
from fastapi.testclient import TestClient

from src.api import ApiSettings, create_app
from src.workflow import (
    DecisionNodeSpec,
    FeatureNodeSpec,
    GraphInputReference,
    GraphRecipeSpec,
    NodeOutputReference,
    WorkflowDataKind,
    WorkflowPortSpec,
)


def _write_gray(path: Path, value: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = np.full((24, 32), value, dtype=np.uint8)
    ok, encoded = cv2.imencode(path.suffix, image)
    assert ok
    path.write_bytes(encoded.tobytes())


def _evaluation_graph() -> GraphRecipeSpec:
    return GraphRecipeSpec(
        name="evaluation_mean_rule",
        display_name="Evaluation Mean Rule",
        inputs=[WorkflowPortSpec(name="image", kind=WorkflowDataKind.IMAGE)],
        nodes=[
            FeatureNodeSpec(
                id="mean_feature",
                feature="pixel_statistic",
                inputs={"image": GraphInputReference(input_name="image")},
                params={"statistic": "mean"},
            ),
            DecisionNodeSpec(
                id="decision",
                inputs={
                    "value": NodeOutputReference(
                        node_id="mean_feature", output_name="value"
                    )
                },
                params={
                    "operator": "lte",
                    "threshold": 127.0,
                    "pass_label": "OK",
                    "fail_label": "NG",
                },
            ),
        ],
        outputs={
            "score": NodeOutputReference(node_id="mean_feature", output_name="value"),
            "result": NodeOutputReference(node_id="decision", output_name="label"),
            "passed": NodeOutputReference(node_id="decision", output_name="passed"),
        },
    )


def _client(tmp_path: Path):
    settings = ApiSettings(
        recipe_store_dir=tmp_path / "store" / "recipes",
        label_store_dir=tmp_path / "store" / "labels",
        test_dataset_store_dir=tmp_path / "store" / "test_datasets",
        evaluation_store_dir=tmp_path / "store" / "evaluations",
    )
    return TestClient(create_app(settings=settings))




def _wait_for_evaluation(client: TestClient, evaluation_id: str, timeout: float = 5.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(f"/api/v1/evaluations/{evaluation_id}")
        assert response.status_code == 200, response.text
        run = response.json()
        if run["status"] in {"completed", "failed", "cancelled"}:
            return run
        time.sleep(0.01)
    raise AssertionError(f"evaluation did not reach terminal state: {evaluation_id}")

def _create_recipe(client: TestClient) -> None:
    graph = _evaluation_graph()
    response = client.post(
        "/api/v1/recipes",
        json={"kind": "graph", "graph": graph.model_dump(mode="json"), "tags": ["test"]},
    )
    assert response.status_code == 201, response.text


def test_dataset_folder_import_auto_labels_and_batch_update(tmp_path: Path):
    root = tmp_path / "images"
    _write_gray(root / "OK" / "ok_1.png", 0)
    _write_gray(root / "NG" / "ng_1.png", 255)
    _write_gray(root / "misc" / "unknown.png", 100)

    with _client(tmp_path) as client:
        create = client.post(
            "/api/v1/test-datasets",
            json={"dataset_id": "dataset_1", "name": "Dataset 1"},
        )
        assert create.status_code == 201

        imported = client.post(
            "/api/v1/test-datasets/dataset_1/import-folder",
            json={"folder_path": str(root), "recursive": True},
        )
        assert imported.status_code == 200, imported.text
        body = imported.json()
        assert body["discovered"] == 3
        assert body["added"] == 3
        page = client.get("/api/v1/test-datasets/dataset_1/images", params={"limit": 100}).json()
        labels = {item["relative_path"]: item["ground_truth"] for item in page["items"]}
        assert labels["OK/ok_1.png"] == "OK"
        assert labels["NG/ng_1.png"] == "NG"
        assert labels["misc/unknown.png"] is None

        unknown = next(
            item for item in page["items"] if item["relative_path"] == "misc/unknown.png"
        )
        revision = body["dataset"]["revision"]
        updated = client.put(
            "/api/v1/test-datasets/dataset_1/ground-truth",
            json={
                "image_ids": [unknown["image_id"]],
                "ground_truth": "OK",
                "expected_revision": revision,
            },
        )
        assert updated.status_code == 200, updated.text
        summary = client.get("/api/v1/test-datasets").json()[0]
        assert summary["image_count"] == 3
        assert summary["ok_count"] == 2
        assert summary["ng_count"] == 1
        assert summary["unlabeled_count"] == 0


def test_evaluation_confusion_metrics_result_filtering_and_persistence(tmp_path: Path):
    root = tmp_path / "eval_images"
    # Prediction rule: mean <= 127 => OK, otherwise NG.
    _write_gray(root / "ok_correct.png", 0)      # TN
    _write_gray(root / "ok_false_ng.png", 255)   # FP
    _write_gray(root / "ng_correct.png", 255)     # TP
    _write_gray(root / "ng_missed.png", 0)        # FN

    with _client(tmp_path) as client:
        _create_recipe(client)
        assert client.post(
            "/api/v1/test-datasets",
            json={"dataset_id": "eval_set", "name": "Evaluation Set"},
        ).status_code == 201

        added = client.post(
            "/api/v1/test-datasets/eval_set/images",
            json={
                "file_paths": [
                    str(root / "ok_correct.png"),
                    str(root / "ok_false_ng.png"),
                    str(root / "ng_correct.png"),
                    str(root / "ng_missed.png"),
                ]
            },
        )
        assert added.status_code == 200, added.text
        images_page = client.get("/api/v1/test-datasets/eval_set/images", params={"limit": 100}).json()
        images = {Path(item["file_path"]).name: item for item in images_page["items"]}
        rev = added.json()["revision"]

        ok_ids = [images["ok_correct.png"]["image_id"], images["ok_false_ng.png"]["image_id"]]
        labeled_ok = client.put(
            "/api/v1/test-datasets/eval_set/ground-truth",
            json={"image_ids": ok_ids, "ground_truth": "OK", "expected_revision": rev},
        )
        assert labeled_ok.status_code == 200, labeled_ok.text
        rev = labeled_ok.json()["revision"]
        ng_ids = [images["ng_correct.png"]["image_id"], images["ng_missed.png"]["image_id"]]
        labeled_ng = client.put(
            "/api/v1/test-datasets/eval_set/ground-truth",
            json={"image_ids": ng_ids, "ground_truth": "NG", "expected_revision": rev},
        )
        assert labeled_ng.status_code == 200, labeled_ng.text

        executed = client.post(
            "/api/v1/evaluations",
            json={
                "dataset_id": "eval_set",
                "recipe_name": "evaluation_mean_rule",
                "decision_output": "result",
                "score_output": "score",
                "capture_node_values": True,
            },
        )
        assert executed.status_code == 202, executed.text
        accepted = executed.json()
        assert accepted["status"] == "queued"
        assert accepted["progress"] == {"total": 4, "processed": 0, "percent": 0.0}
        run = _wait_for_evaluation(client, accepted["evaluation_id"])
        assert run["status"] == "completed", run
        assert run["progress"]["processed"] == 4
        assert run["progress"]["percent"] == 100.0
        matrix = run["summary"]["confusion_matrix"]
        assert matrix == {"tp": 1, "tn": 1, "fp": 1, "fn": 1}
        metrics = run["summary"]["metrics"]
        assert metrics["accuracy"] == 0.5
        assert metrics["precision"] == 0.5
        assert metrics["recall"] == 0.5
        assert metrics["specificity"] == 0.5
        assert metrics["f1"] == 0.5
        assert run["summary"]["error_images"] == 0
        assert run["summary"]["ok_scores"]["count"] == 2
        assert run["summary"]["ng_scores"]["count"] == 2
        assert all("mean_feature.value" in item["feature_values"] for item in run["results"])

        eval_id = run["evaluation_id"]
        false_ng = client.get(
            f"/api/v1/evaluations/{eval_id}/results",
            params={"ground_truth": "OK", "prediction": "NG"},
        )
        assert false_ng.status_code == 200
        assert false_ng.json()["total"] == 1
        assert Path(false_ng.json()["items"][0]["file_path"]).name == "ok_false_ng.png"

        missed_ng = client.get(
            f"/api/v1/evaluations/{eval_id}/results",
            params={"ground_truth": "NG", "prediction": "OK"},
        )
        assert missed_ng.status_code == 200
        assert missed_ng.json()["total"] == 1
        assert Path(missed_ng.json()["items"][0]["file_path"]).name == "ng_missed.png"

        listed = client.get("/api/v1/evaluations").json()
        assert len(listed) == 1
        assert listed[0]["evaluation_id"] == eval_id
        assert listed[0]["status"] == "completed"
        completed_only = client.get(
            "/api/v1/evaluations", params={"status": "completed"}
        ).json()
        assert len(completed_only) == 1
        running_only = client.get(
            "/api/v1/evaluations", params={"status": "running"}
        ).json()
        assert running_only == []
        fetched = client.get(f"/api/v1/evaluations/{eval_id}")
        assert fetched.status_code == 200
        assert fetched.json()["summary"]["confusion_matrix"] == matrix


def test_evaluation_marks_missing_file_as_error(tmp_path: Path):
    image_path = tmp_path / "present.png"
    missing_path = tmp_path / "missing.png"
    _write_gray(image_path, 0)

    with _client(tmp_path) as client:
        _create_recipe(client)
        client.post(
            "/api/v1/test-datasets",
            json={"dataset_id": "errors", "name": "Error Set"},
        )
        # Add the second path while it exists, then delete before evaluation.
        _write_gray(missing_path, 255)
        added = client.post(
            "/api/v1/test-datasets/errors/images",
            json={"file_paths": [str(image_path), str(missing_path)], "ground_truth": "OK"},
        )
        assert added.status_code == 200
        missing_path.unlink()

        executed = client.post(
            "/api/v1/evaluations",
            json={"dataset_id": "errors", "recipe_name": "evaluation_mean_rule"},
        )
        assert executed.status_code == 202, executed.text
        body = _wait_for_evaluation(client, executed.json()["evaluation_id"])
        assert body["status"] == "completed", body
        assert body["summary"]["error_images"] == 1
        assert body["summary"]["evaluated_images"] == 1
        assert body["summary"]["execution_success_rate"] == 0.5
        errors = [item for item in body["results"] if item["prediction"] == "ERROR"]
        assert len(errors) == 1
        assert errors[0]["correct"] is None
        assert errors[0]["error"] is not None


def test_evaluation_rejects_unlabeled_dataset_and_non_decision_graph(tmp_path: Path):
    root = tmp_path / "images"
    _write_gray(root / "x.png", 0)

    with _client(tmp_path) as client:
        _create_recipe(client)
        client.post(
            "/api/v1/test-datasets",
            json={"dataset_id": "unlabeled", "name": "Unlabeled"},
        )
        client.post(
            "/api/v1/test-datasets/unlabeled/images",
            json={"file_paths": [str(root / "x.png")]},
        )
        response = client.post(
            "/api/v1/evaluations",
            json={"dataset_id": "unlabeled", "recipe_name": "evaluation_mean_rule"},
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "evaluation_validation_error"
