from __future__ import annotations

from typing import Any

import numpy as np

from ..schemas import ModelData, ModelSpec
from .common import training_arrays


def train_svm(
    features: Any,
    labels: Any,
    *,
    model_id: str,
    version: str,
    feature_schema: str,
    kernel: str = "rbf",
    c: float = 1.0,
    gamma: float = 0.01,
    label_names: dict[int, str] | None = None,
) -> ModelData:
    import cv2

    kernels = {
        "linear": cv2.ml.SVM_LINEAR,
        "rbf": cv2.ml.SVM_RBF,
        "poly": cv2.ml.SVM_POLY,
        "sigmoid": cv2.ml.SVM_SIGMOID,
    }
    if kernel not in kernels:
        raise ValueError(f"unsupported SVM kernel: {kernel}")
    if c <= 0 or gamma <= 0:
        raise ValueError("c and gamma must be positive")
    x, y = training_arrays(features, labels)
    if not np.equal(y, np.rint(y)).all():
        raise ValueError("SVM classification labels must be integers")
    categorical = np.ascontiguousarray(y.astype(np.int32))
    model = cv2.ml.SVM_create()
    model.setType(cv2.ml.SVM_C_SVC)
    model.setKernel(kernels[kernel])
    model.setC(float(c))
    model.setGamma(float(gamma))
    if not model.train(x, cv2.ml.ROW_SAMPLE, categorical):
        raise RuntimeError("OpenCV failed to train SVM")
    return ModelData(
        spec=ModelSpec(
            model_id=model_id,
            version=version,
            algorithm="svm",
            feature_schema=feature_schema,
            labels=label_names or {},
            metadata={
                "kernel": kernel,
                "c": float(c),
                "gamma": float(gamma),
                "feature_count": x.shape[1],
            },
        ),
        model=model,
    )
