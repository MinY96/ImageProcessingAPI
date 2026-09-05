from __future__ import annotations

import numpy as np


def training_arrays(features, labels) -> tuple[np.ndarray, np.ndarray]:
    x = np.asarray(features, dtype=np.float32)
    y = np.asarray(labels)
    if x.ndim != 2 or x.shape[0] == 0 or x.shape[1] == 0:
        raise ValueError("features must be a non-empty 2D array")
    y = y.reshape(-1, 1)
    if y.shape[0] != x.shape[0]:
        raise ValueError("features and labels must contain the same samples")
    if not np.isfinite(x).all():
        raise ValueError("features must be finite")
    return np.ascontiguousarray(x), np.ascontiguousarray(y.astype(np.float32))
