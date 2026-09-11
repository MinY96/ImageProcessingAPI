from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np

from src.machine_learning import ModelData, PredictionData
from src.registry.errors import OperationExecutionError
from src.schemas import (
    DiscreteParameterSpec,
    InputKind,
    InputSlotSpec,
    OperationCategory,
    OperationOutput,
    OperationSpec,
    OutputKind,
    OutputSlotSpec,
)


MODEL_PREDICT_SPEC = OperationSpec(
    name="model_predict",
    display_name="Classical ML Model Predict",
    category=OperationCategory.CLASSIFICATION,
    description=(
        "ModelRegistry에서 얻은 OpenCV kNN/SVM ModelData와 feature matrix로 추론합니다."
    ),
    inputs=[
        InputSlotSpec(name="model", kind=InputKind.MODEL),
        InputSlotSpec(name="features", kind=InputKind.ARRAY),
    ],
    parameters={
        "knn_k": DiscreteParameterSpec(
            title="KNN Neighbours", min_value=1, max_value=1000, default=5
        )
    },
    outputs=[
        OutputSlotSpec(name="predictions", kind=OutputKind.ARRAY),
        OutputSlotSpec(name="prediction_info", kind=OutputKind.METRICS),
    ],
)


def _features(value: Any, expected: int | None) -> np.ndarray:
    try:
        features = np.asarray(value, dtype=np.float32)
    except (TypeError, ValueError) as exc:
        raise OperationExecutionError(
            code="invalid_features", message="features must be numeric"
        ) from exc
    if features.ndim == 1:
        features = features.reshape(1, -1)
    if features.ndim != 2 or not features.size:
        raise OperationExecutionError(
            code="invalid_features", message="features must be a non-empty 2D array"
        )
    if not np.isfinite(features).all():
        raise OperationExecutionError(
            code="invalid_features", message="features must contain finite values"
        )
    if expected is not None and features.shape[1] != expected:
        raise OperationExecutionError(
            code="feature_schema_mismatch",
            message="feature count does not match the registered model",
            details={"provided": features.shape[1], "expected": expected},
        )
    if features.size > 10_000_000:
        raise OperationExecutionError(
            code="resource_limit_exceeded",
            message="feature input exceeds the item limit",
            details={"items": int(features.size), "maximum": 10_000_000},
        )
    return np.ascontiguousarray(features)


def model_predict_handler(
    *, inputs: Mapping[str, Any], params: Mapping[str, Any]
) -> OperationOutput:
    model_data: ModelData = inputs["model"]
    spec = model_data.spec
    expected = spec.metadata.get("feature_count")
    features = _features(inputs["features"], int(expected) if expected else None)

    if spec.algorithm == "knn":
        k = params.get("knn_k") or int(spec.metadata.get("default_k", 5))
        _, predictions, neighbours, distances = model_data.model.findNearest(
            features, int(k)
        )
        details: dict[str, Any] = {
            "k": int(k),
            "neighbours": neighbours,
            "distances": distances,
        }
    elif spec.algorithm == "svm":
        _, predictions = model_data.model.predict(features)
        details = {}
    else:
        raise OperationExecutionError(
            code="unsupported_model_algorithm",
            message=f"unsupported model algorithm: {spec.algorithm}",
        )

    flattened = np.asarray(predictions).reshape(-1)
    normalized_labels = [float(value) for value in flattened]
    names = [spec.labels.get(int(value)) for value in flattened]
    prediction_info = PredictionData(
        labels=normalized_labels,
        label_names=names,
        model_id=spec.model_id,
        model_version=spec.version,
        algorithm=spec.algorithm,
        details=details,
    )
    return OperationOutput(
        data={
            "predictions": np.asarray(predictions, dtype=np.float32),
            "prediction_info": prediction_info,
        }
    )
