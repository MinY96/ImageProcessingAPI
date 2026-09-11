import base64
import json

import cv2
import numpy as np
from fastapi.testclient import TestClient

from src.api import ApiSettings, create_app
from src.workflow import (
    DecisionNodeSpec,
    FeatureNodeSpec,
    GraphRecipeSpec,
    OperationNodeSpec,
    ScalarOperatorNodeSpec,
    WorkflowDataKind,
    WorkflowPortSpec,
    graph_input,
    node_output,
)


def make_settings(tmp_path) -> ApiSettings:
    return ApiSettings(
        recipe_store_dir=tmp_path / "recipes",
        label_store_dir=tmp_path / "labels",
    )


def image_upload_payload(*, retain_intermediates: bool = False):
    image = np.zeros((96, 144, 3), dtype=np.uint8)
    cv2.rectangle(image, (12, 15), (54, 82), (180, 180, 180), -1)
    cv2.circle(image, (105, 48), 19, (255, 255, 255), -1)
    ok, encoded = cv2.imencode(".png", image)
    assert ok
    payload = json.dumps(
        {
            "image_inputs": [{"input_name": "image", "file_index": 0}],
            "retain_intermediates": retain_intermediates,
        }
    )
    files = [("files", ("input.png", encoded.tobytes(), "image/png"))]
    return image, payload, files


def make_user_graph(name: str = "custom_graph_rule") -> GraphRecipeSpec:
    return GraphRecipeSpec(
        name=name,
        display_name="Custom Graph Rule",
        description="graph recipe CRUD test",
        inputs=[WorkflowPortSpec(name="image", kind=WorkflowDataKind.IMAGE)],
        nodes=[
            OperationNodeSpec(
                id="gray",
                operation="convert_color",
                inputs={"image": graph_input("image")},
                params={"target_color_space": "gray"},
            ),
            FeatureNodeSpec(
                id="mean",
                feature="pixel_statistic",
                inputs={"image": node_output("gray")},
                params={"statistic": "mean"},
            ),
            ScalarOperatorNodeSpec(
                id="normalized",
                operator="normalize_range",
                inputs={"value": node_output("mean", "value")},
                params={"lower": 0.0, "upper": 255.0, "clip": True},
            ),
            DecisionNodeSpec(
                id="decision",
                inputs={"value": node_output("normalized", "value")},
                params={"operator": "lte", "threshold": 0.9},
            ),
        ],
        outputs={
            "image": node_output("gray"),
            "score": node_output("normalized", "value"),
            "passed": node_output("decision", "passed"),
            "result": node_output("decision", "label"),
        },
    )


def test_default_app_registers_graph_recipe_examples(tmp_path):
    with TestClient(create_app(settings=make_settings(tmp_path))) as client:
        response = client.get("/api/v1/recipes", params={"kind": "graph"})

    assert response.status_code == 200
    recipes = {item["name"]: item for item in response.json()}
    assert set(recipes) == {
        "rule_branch_binary_score",
        "rule_multi_roi_fusion",
        "rule_multi_roi_recompose",
        "rule_nested_graph_score",
        "rule_nested_sem_profile",
    }
    assert all(item["source"] == "builtin" for item in recipes.values())
    assert all(item["readonly"] is True for item in recipes.values())


def test_workflow_metadata_endpoints(tmp_path):
    with TestClient(create_app(settings=make_settings(tmp_path))) as client:
        features = client.get("/api/v1/workflow/features")
        operators = client.get("/api/v1/workflow/operators")

    assert features.status_code == 200
    assert {
        "pixel_statistic",
        "profile_feature",
        "contour_feature",
        "image_similarity",
        "mask_similarity",
    } <= {item["name"] for item in features.json()}
    assert operators.status_code == 200
    assert {
        "add",
        "subtract",
        "multiply",
        "divide",
        "abs_diff",
        "weighted_sum",
        "weighted_mean",
        "normalize_range",
    } <= {item["name"] for item in operators.json()}


def test_branch_binary_recipe_executes_and_fuses_three_features(tmp_path):
    _, payload, files = image_upload_payload(retain_intermediates=True)
    with TestClient(create_app(settings=make_settings(tmp_path))) as client:
        response = client.post(
            "/api/v1/recipes/rule_branch_binary_score/execute",
            data={"payload": payload},
            files=files,
        )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert set(body["output"]["data"]) == {
        "foreground_ratio",
        "boundary_ratio",
        "largest_area_ratio",
        "score",
        "passed",
        "result",
    }
    assert 0.0 <= body["output"]["data"]["score"] <= 1.0
    assert {"binary", "open_branch", "gradient_branch", "close_branch"} <= set(body["intermediates"])


def test_multi_roi_feature_fusion_executes_different_branches(tmp_path):
    _, payload, files = image_upload_payload(retain_intermediates=True)
    with TestClient(create_app(settings=make_settings(tmp_path))) as client:
        response = client.post(
            "/api/v1/recipes/rule_multi_roi_fusion/execute",
            data={"payload": payload},
            files=files,
        )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert set(body["output"]["images"]) == {
        "left_processed",
        "center_processed",
        "right_processed",
    }
    assert {"score", "passed", "result"} <= set(body["output"]["data"])
    assert {"left_blur", "center_clahe", "right_edges"} <= set(body["intermediates"])


def test_multi_roi_recompose_restores_original_canvas_size(tmp_path):
    source, payload, files = image_upload_payload()
    with TestClient(create_app(settings=make_settings(tmp_path))) as client:
        response = client.post(
            "/api/v1/recipes/rule_multi_roi_recompose/execute",
            data={"payload": payload},
            files=files,
        )

    assert response.status_code == 200
    encoded = base64.b64decode(response.json()["output"]["images"]["image"]["data"])
    result = cv2.imdecode(np.frombuffer(encoded, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    assert result.shape[:2] == source.shape[:2]


def test_nested_linear_and_graph_recipes_execute(tmp_path):
    _, payload, files = image_upload_payload()
    with TestClient(create_app(settings=make_settings(tmp_path))) as client:
        linear_nested = client.post(
            "/api/v1/recipes/rule_nested_sem_profile/execute",
            data={"payload": payload},
            files=files,
        )
        graph_nested = client.post(
            "/api/v1/recipes/rule_nested_graph_score/execute",
            data={"payload": payload},
            files=files,
        )

    assert linear_nested.status_code == 200
    assert linear_nested.json()["success"] is True
    assert {"profile_mask", "gradient"} <= set(linear_nested.json()["output"]["images"])
    assert graph_nested.status_code == 200
    assert graph_nested.json()["success"] is True
    assert "score" in graph_nested.json()["output"]["data"]


def test_graph_recipe_crud_persistence_and_catalog_sync(tmp_path):
    settings = make_settings(tmp_path)
    graph = make_user_graph()

    with TestClient(create_app(settings=settings)) as client:
        created = client.post(
            "/api/v1/recipes",
            json={"kind": "graph", "graph": graph.model_dump(mode="json"), "tags": ["rule", "sem"]},
        )
        assert created.status_code == 201
        assert created.json()["kind"] == "graph"
        assert created.json()["revision"] == 1

        _, payload, files = image_upload_payload()
        executed = client.post(
            "/api/v1/recipes/custom_graph_rule/execute",
            data={"payload": payload},
            files=files,
        )
        assert executed.status_code == 200
        assert executed.json()["success"] is True

    with TestClient(create_app(settings=settings)) as client:
        detail = client.get("/api/v1/recipes/custom_graph_rule")
        assert detail.status_code == 200
        assert detail.json()["kind"] == "graph"
        assert detail.json()["tags"] == ["rule", "sem"]

        deleted = client.delete(
            "/api/v1/recipes/custom_graph_rule",
            params={"expected_revision": 1},
        )
        assert deleted.status_code == 204


def test_workflow_validation_rejects_graph_cycle(tmp_path):
    graph = GraphRecipeSpec(
        name="cyclic_graph",
        display_name="Cyclic Graph",
        inputs=[WorkflowPortSpec(name="image", kind=WorkflowDataKind.IMAGE)],
        nodes=[
            OperationNodeSpec(
                id="a",
                operation="gaussian_blur",
                inputs={"image": node_output("b")},
                params={"kernel_size": 3},
            ),
            OperationNodeSpec(
                id="b",
                operation="gaussian_blur",
                inputs={"image": node_output("a")},
                params={"kernel_size": 3},
            ),
        ],
        outputs={"image": node_output("b")},
    )

    with TestClient(create_app(settings=make_settings(tmp_path))) as client:
        response = client.post("/api/v1/workflow/validate", json=graph.model_dump(mode="json"))

    assert response.status_code == 422
    issues = response.json()["error"]["issues"]
    assert any(issue["code"] == "graph_cycle" for issue in issues)


def test_workflow_validation_rejects_incompatible_port_kind(tmp_path):
    graph = GraphRecipeSpec(
        name="bad_port_graph",
        display_name="Bad Port Graph",
        inputs=[WorkflowPortSpec(name="image", kind=WorkflowDataKind.IMAGE)],
        nodes=[
            FeatureNodeSpec(
                id="mean",
                feature="pixel_statistic",
                inputs={"image": graph_input("image")},
                params={"statistic": "mean"},
            ),
            OperationNodeSpec(
                id="blur",
                operation="gaussian_blur",
                inputs={"image": node_output("mean", "value")},
                params={"kernel_size": 3},
            ),
        ],
        outputs={"score": node_output("mean", "value")},
    )

    with TestClient(create_app(settings=make_settings(tmp_path))) as client:
        response = client.post("/api/v1/workflow/validate", json=graph.model_dump(mode="json"))

    assert response.status_code == 422
    issues = response.json()["error"]["issues"]
    assert any(issue["code"] == "incompatible_input_kind" for issue in issues)


def test_persisted_graph_subrecipe_load_order_is_dependency_safe(tmp_path):
    settings = make_settings(tmp_path)
    with TestClient(create_app(settings=settings)) as client:
        child = client.post(
            "/api/v1/recipes/rule_branch_binary_score/clone",
            json={"name": "z_child_rule"},
        )
        assert child.status_code == 201
        parent_graph = {
            "name": "a_parent_rule",
            "display_name": "Parent Rule",
            "inputs": [{"name": "image", "kind": "image"}],
            "nodes": [
                {
                    "id": "child",
                    "node_type": "subrecipe",
                    "recipe": "z_child_rule",
                    "recipe_kind": "graph",
                    "inputs": {
                        "image": {"type": "graph_input", "input_name": "image"}
                    },
                }
            ],
            "outputs": {
                "score": {
                    "type": "node_output",
                    "node_id": "child",
                    "output_name": "score",
                }
            },
        }
        parent = client.post(
            "/api/v1/recipes",
            json={"kind": "graph", "graph": parent_graph},
        )
        assert parent.status_code == 201

    # a_parent_rule.json sorts before z_child_rule.json; restart must still load both.
    with TestClient(create_app(settings=settings)) as client:
        detail = client.get("/api/v1/recipes/a_parent_rule")
        executed = client.post(
            "/api/v1/recipes/a_parent_rule/execute",
            data={"payload": image_upload_payload()[1]},
            files=image_upload_payload()[2],
        )
    assert detail.status_code == 200
    assert executed.status_code == 200
    assert executed.json()["success"] is True
