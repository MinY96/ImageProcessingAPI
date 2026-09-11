from __future__ import annotations

import numpy as np

from src.registry.errors import OperationExecutionError
from src.schemas import ColorSpace, ImageData


def integer_scale(image: ImageData, operation: str) -> float:
    if image.data.dtype == np.uint8:
        return 255.0
    if image.data.dtype == np.uint16:
        return 65535.0
    raise OperationExecutionError(
        code="invalid_image_dtype",
        message=f"{operation} requires uint8 or uint16 image data",
        details={"dtype": image.dtype},
    )


def color_and_alpha(image: ImageData) -> tuple[np.ndarray, np.ndarray | None]:
    channels = image.channels
    if channels == 4:
        return image.data[..., :3], image.data[..., 3:4].copy()
    return image.data, None


def restore_alpha(color: np.ndarray, alpha: np.ndarray | None) -> np.ndarray:
    if alpha is None:
        return np.ascontiguousarray(color)
    return np.ascontiguousarray(np.concatenate([color, alpha], axis=2))


def to_rgb_and_alpha(image: ImageData) -> tuple[np.ndarray, np.ndarray | None]:
    import cv2

    conversions = {
        ColorSpace.BGR: cv2.COLOR_BGR2RGB,
        ColorSpace.BGRA: cv2.COLOR_BGRA2RGBA,
    }
    data = image.data
    conversion = conversions.get(image.color_space)
    if conversion is not None:
        data = cv2.cvtColor(data, conversion)
    if image.color_space not in {
        ColorSpace.BGR,
        ColorSpace.RGB,
        ColorSpace.BGRA,
        ColorSpace.RGBA,
    }:
        raise OperationExecutionError(
            code="invalid_color_space",
            message="operation requires a BGR/RGB/BGRA/RGBA image",
            details={"color_space": image.color_space.value},
        )
    return color_and_alpha(
        ImageData(data=data, color_space=(ColorSpace.RGBA if data.shape[2] == 4 else ColorSpace.RGB))
    )


def restore_from_rgb(
    rgb: np.ndarray,
    alpha: np.ndarray | None,
    color_space: ColorSpace,
) -> np.ndarray:
    import cv2

    combined = restore_alpha(rgb, alpha)
    if color_space == ColorSpace.BGR:
        return cv2.cvtColor(combined, cv2.COLOR_RGB2BGR)
    if color_space == ColorSpace.BGRA:
        return cv2.cvtColor(combined, cv2.COLOR_RGBA2BGRA)
    return combined
