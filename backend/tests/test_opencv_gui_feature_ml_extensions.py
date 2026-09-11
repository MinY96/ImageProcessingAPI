import cv2
import numpy as np
import pytest

from src.machine_learning import ModelRegistry, train_knn, train_svm
from src.media_io import read_image, write_image
from src.pipeline import PipelineExecutor, pipeline_input, step_output
from src.registry import create_default_registry
from src.schemas import (
    ColorSpace,
    ImageData,
    InputKind,
    InputSlotSpec,
    PipelineSpec,
    PipelineStepSpec,
)


@pytest.fixture
def registry():
    return create_default_registry()


@pytest.fixture
def feature_image():
    rng = np.random.default_rng(7)
    data = rng.integers(0, 70, (192, 256), dtype=np.uint8)
    cv2.rectangle(data, (20, 25), (105, 150), 235, 4)
    cv2.circle(data, (175, 88), 42, 180, 5)
    cv2.line(data, (125, 165), (235, 130), 255, 4)
    cv2.putText(data, "CV", (125, 55), cv2.FONT_HERSHEY_SIMPLEX, 1.2, 250, 3)
    return ImageData(data=data, color_space=ColorSpace.GRAY, name="features")


def assert_success(result):
    assert result.success is True, result.error


def test_draw_annotations(registry, feature_image):
    result = registry.execute(
        operation="draw_annotations",
        inputs={
            "image": feature_image,
            "annotations": [
                {
                    "type": "rectangle",
                    "top_left": [10, 10],
                    "bottom_right": [80, 60],
                    "color": [0, 255, 0],
                },
                {
                    "type": "text",
                    "text": "result",
                    "origin": [15, 100],
                },
            ],
        },
    )
    assert_success(result)
    assert result.output.images["image"].color_space == ColorSpace.BGR
    assert np.any(result.output.images["image"].data != 0)


@pytest.mark.parametrize(
    "operation",
    [
        "harris_corners",
        "shi_tomasi_corners",
        "fast_keypoints",
        "sift_features",
        "orb_features",
    ],
)
def test_feature_detectors_and_descriptors(registry, feature_image, operation):
    result = registry.execute(operation=operation, inputs={"image": feature_image})
    assert_success(result)
    assert result.output.images["image"].color_space == ColorSpace.BGR
    assert len(result.output.data["keypoints"]) > 0
    if operation in {"sift_features", "orb_features"}:
        assert result.output.data["descriptors"].ndim == 2


@pytest.mark.parametrize("operation", ["surf_features", "brief_descriptors"])
def test_optional_contrib_features_fail_cleanly_when_unavailable(
    registry, feature_image, operation
):
    result = registry.execute(operation=operation, inputs={"image": feature_image})
    if result.success:
        assert result.output.data["descriptors"].ndim == 2
    else:
        assert result.error.code == "optional_dependency_unavailable"


def test_hog_descriptor(registry, feature_image):
    result = registry.execute(
        operation="hog_descriptor",
        inputs={"image": feature_image},
        params={"width": 64, "height": 128},
    )
    assert_success(result)
    assert result.output.data["descriptor"].shape == (1, 3780)


def test_feature_matching(registry, feature_image):
    matrix = cv2.getRotationMatrix2D((128, 96), 3.0, 1.0)
    shifted = cv2.warpAffine(feature_image.data, matrix, (256, 192))
    second = ImageData(data=shifted, color_space=ColorSpace.GRAY)
    result = registry.execute(
        operation="feature_match",
        inputs={"image1": feature_image, "image2": second},
        params={"algorithm": "sift", "matcher": "bf"},
    )
    assert_success(result)
    assert result.output.data["matches"]["count"] >= 4


def test_homography_estimation_and_pipeline_array_binding(registry):
    source = [[0, 0], [100, 0], [100, 80], [0, 80], [50, 40]]
    destination = [[10, 5], [120, 8], [115, 95], [8, 90], [62, 50]]
    direct = registry.execute(
        operation="estimate_homography",
        inputs={"source_points": source, "destination_points": destination},
        params={"method": "direct"},
    )
    assert_success(direct)
    assert direct.output.data["homography"].shape == (3, 3)

    pipeline = PipelineSpec(
        name="homography_then_warp",
        display_name="Homography Then Warp",
        inputs=[
            InputSlotSpec(name="image", kind=InputKind.IMAGE),
            InputSlotSpec(name="source", kind=InputKind.POINTS),
            InputSlotSpec(name="destination", kind=InputKind.POINTS),
        ],
        steps=[
            PipelineStepSpec(
                id="homography",
                operation="estimate_homography",
                inputs={
                    "source_points": pipeline_input("source"),
                    "destination_points": pipeline_input("destination"),
                },
                params={"method": "direct"},
            )
        ],
        outputs={"matrix": step_output("homography", "homography")},
    )
    compiled = PipelineExecutor(registry).compile(pipeline)
    assert compiled.output_bindings["matrix"].output_name == "homography"


def test_localize_planar_object(registry, feature_image):
    query = ImageData(
        data=feature_image.data[15:175, 15:240].copy(),
        color_space=ColorSpace.GRAY,
    )
    homography = np.array(
        [[0.98, 0.03, 12.0], [-0.02, 1.01, 10.0], [0.0001, 0.0002, 1.0]],
        dtype=np.float32,
    )
    scene_data = cv2.warpPerspective(query.data, homography, (280, 220))
    scene = ImageData(data=scene_data, color_space=ColorSpace.GRAY)
    result = registry.execute(
        operation="localize_planar_object",
        inputs={"query_image": query, "scene_image": scene},
        params={
            "algorithm": "sift",
            "matcher": "bf",
            "min_matches": 4,
            "ratio_threshold": 0.9,
        },
    )
    assert_success(result)
    assert result.output.data["polygon"].shape == (4, 2)
    assert result.output.data["metrics"]["inliers"] >= 4


def test_kmeans_segmentation_and_color_quantization_are_reproducible(
    registry, feature_image
):
    bgr = cv2.cvtColor(feature_image.data, cv2.COLOR_GRAY2BGR)
    bgr[:, :80] = (20, 40, 220)
    image = ImageData(data=bgr, color_space=ColorSpace.BGR)
    params = {"random_seed": 17, "sample_size": 5000, "attempts": 1}

    first = registry.execute(
        operation="color_quantization", inputs={"image": image}, params=params
    )
    second = registry.execute(
        operation="color_quantization", inputs={"image": image}, params=params
    )
    assert_success(first)
    assert_success(second)
    np.testing.assert_array_equal(
        first.output.images["image"].data, second.output.images["image"].data
    )

    segmented = registry.execute(
        operation="kmeans_segmentation",
        inputs={"image": feature_image},
        params={"clusters": 3, **params},
    )
    assert_success(segmented)
    assert segmented.output.images["labels"].dtype == "int32"
    assert segmented.output.data["centers"].shape == (3, 1)


@pytest.mark.parametrize("algorithm", ["knn", "svm"])
def test_classical_ml_training_registry_and_prediction(registry, algorithm):
    features = np.array(
        [[0, 0], [0, 1], [1, 0], [8, 8], [8, 9], [9, 8]], dtype=np.float32
    )
    labels = np.array([0, 0, 0, 1, 1, 1])
    trainer = train_knn if algorithm == "knn" else train_svm
    keyword = {"default_k": 3} if algorithm == "knn" else {"kernel": "linear"}
    model = trainer(
        features,
        labels,
        model_id=f"demo_{algorithm}",
        version="1.0.0",
        feature_schema="xy-v1",
        label_names={0: "low", 1: "high"},
        **keyword,
    )
    models = ModelRegistry()
    models.register(model)
    assert models.get(model.spec.model_id, "1.0.0") is model
    assert models.list_specs()[0].algorithm == algorithm

    result = registry.execute(
        operation="model_predict",
        inputs={"model": model, "features": [[0.1, 0.2], [8.5, 8.2]]},
        params={"knn_k": 3},
    )
    assert_success(result)
    assert result.output.data["predictions"].reshape(-1).tolist() == [0.0, 1.0]
    assert result.output.data["prediction_info"].label_names == ["low", "high"]

    pipeline = PipelineSpec(
        name=f"{algorithm}_prediction_pipeline",
        display_name=f"{algorithm.upper()} Prediction Pipeline",
        inputs=[
            InputSlotSpec(name="model", kind=InputKind.MODEL),
            InputSlotSpec(name="features", kind=InputKind.ARRAY),
        ],
        steps=[
            PipelineStepSpec(
                id="predict",
                operation="model_predict",
                inputs={
                    "model": pipeline_input("model"),
                    "features": pipeline_input("features"),
                },
                params={"knn_k": 3},
            )
        ],
        outputs={"predictions": step_output("predict", "predictions")},
    )
    pipeline_result = PipelineExecutor(registry).execute(
        pipeline=pipeline,
        inputs={"model": model, "features": [[0.1, 0.2], [8.5, 8.2]]},
    )
    assert pipeline_result.success is True, pipeline_result.error
    assert pipeline_result.output.data["predictions"].shape == (2, 1)


def test_unicode_image_io_round_trip(tmp_path, feature_image):
    target = tmp_path / "테스트_영상.png"
    write_image(target, feature_image)
    loaded = read_image(target)
    assert loaded.name == target.name
    assert loaded.color_space == ColorSpace.GRAY
    np.testing.assert_array_equal(loaded.data, feature_image.data)
