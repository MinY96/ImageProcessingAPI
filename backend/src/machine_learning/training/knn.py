from __future__ import annotations

from typing import Any

from ..schemas import ModelData, ModelSpec
from .common import training_arrays


def train_knn(
    features: Any,
    labels: Any,
    *,
    model_id: str,
    version: str,
    feature_schema: str,
    default_k: int = 5,
    label_names: dict[int, str] | None = None,
) -> ModelData:
    import cv2

    if default_k < 1:
        raise ValueError("default_k must be >= 1")
    x, y = training_arrays(features, labels)
    model = cv2.ml.KNearest_create()
    if not model.train(x, cv2.ml.ROW_SAMPLE, y):
        raise RuntimeError("OpenCV failed to train KNearest")
    return ModelData(
        spec=ModelSpec(
            model_id=model_id,
            version=version,
            algorithm="knn",
            feature_schema=feature_schema,
            labels=label_names or {},
            metadata={"default_k": default_k, "feature_count": x.shape[1]},
        ),
        model=model,
    )
