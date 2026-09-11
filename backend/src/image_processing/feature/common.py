from __future__ import annotations

from typing import Any

import numpy as np

from src.registry.errors import OperationExecutionError
from src.schemas import ColorSpace, ImageData

from ..common import to_bgr


def to_gray_u8(image: ImageData) -> np.ndarray:
    import cv2

    if image.data.dtype != np.uint8:
        raise OperationExecutionError(
            code="invalid_image_dtype",
            message="feature operations require uint8 images",
            details={"dtype": image.dtype},
        )
    if image.color_space in {ColorSpace.GRAY, ColorSpace.BINARY}:
        return image.data.copy()
    bgr = to_bgr(image)
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)


def serialize_keypoints(keypoints: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "x": float(point.pt[0]),
            "y": float(point.pt[1]),
            "size": float(point.size),
            "angle": float(point.angle),
            "response": float(point.response),
            "octave": int(point.octave),
            "class_id": int(point.class_id),
        }
        for point in keypoints
    ]


def empty_descriptors(columns: int, dtype=np.float32) -> np.ndarray:
    return np.empty((0, columns), dtype=dtype)


def draw_keypoints(image: ImageData, keypoints: list[Any], *, rich: bool = False):
    import cv2

    flags = (
        cv2.DRAW_MATCHES_FLAGS_DRAW_RICH_KEYPOINTS
        if rich
        else cv2.DRAW_MATCHES_FLAGS_DEFAULT
    )
    return cv2.drawKeypoints(
        to_bgr(image), keypoints, None, color=(0, 255, 0), flags=flags
    )
