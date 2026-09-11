from __future__ import annotations

from typing import Any

import numpy as np

from src.registry.errors import OperationExecutionError
from src.schemas import ColorSpace, ImageData


MAX_OUTPUT_PIXELS = 64_000_000


def ensure_pixel_budget(
    *,
    pixels: int,
    operation: str,
    max_pixels: int,
    resource: str = "input",
) -> None:
    if pixels > max_pixels:
        raise OperationExecutionError(
            code="resource_limit_exceeded",
            message=f"{operation} exceeds its {resource} pixel budget",
            details={
                "resource": resource,
                "pixels": pixels,
                "max_pixels": max_pixels,
            },
        )


def ensure_output_size(
    *,
    width: int,
    height: int,
    operation: str,
) -> None:
    if width < 1 or height < 1:
        raise OperationExecutionError(
            code="invalid_output_size",
            message=f"{operation} output dimensions must be positive",
            details={"width": width, "height": height},
        )

    pixels = width * height
    if pixels > MAX_OUTPUT_PIXELS:
        raise OperationExecutionError(
            code="resource_limit_exceeded",
            message=f"{operation} output exceeds the pixel limit",
            details={
                "width": width,
                "height": height,
                "pixels": pixels,
                "max_pixels": MAX_OUTPUT_PIXELS,
            },
        )


def as_image(
    data: np.ndarray,
    *,
    source: ImageData,
    color_space: ColorSpace | None = None,
    name: str | None = None,
) -> ImageData:
    return ImageData(
        data=np.ascontiguousarray(data),
        color_space=color_space or source.color_space,
        name=source.name if name is None else name,
    )


def to_bgr(image: ImageData) -> np.ndarray:
    import cv2

    conversions: dict[ColorSpace, int] = {
        ColorSpace.GRAY: cv2.COLOR_GRAY2BGR,
        ColorSpace.BINARY: cv2.COLOR_GRAY2BGR,
        ColorSpace.RGB: cv2.COLOR_RGB2BGR,
        ColorSpace.HSV: cv2.COLOR_HSV2BGR,
        ColorSpace.LAB: cv2.COLOR_LAB2BGR,
        ColorSpace.BGRA: cv2.COLOR_BGRA2BGR,
        ColorSpace.RGBA: cv2.COLOR_RGBA2BGR,
    }

    if image.color_space == ColorSpace.BGR:
        return image.data.copy()

    conversion = conversions.get(image.color_space)
    if conversion is None:
        raise OperationExecutionError(
            code="unsupported_color_space",
            message="image cannot be converted to BGR",
            details={"color_space": image.color_space.value},
        )
    return cv2.cvtColor(image.data, conversion)


def points_array(
    value: Any,
    *,
    expected_count: int,
    input_name: str,
) -> np.ndarray:
    try:
        points = np.asarray(value, dtype=np.float32)
    except (TypeError, ValueError) as exc:
        raise OperationExecutionError(
            code="invalid_points",
            message=f"{input_name} must contain numeric coordinates",
        ) from exc

    if points.shape != (expected_count, 2):
        raise OperationExecutionError(
            code="invalid_points",
            message=(
                f"{input_name} must have shape "
                f"({expected_count}, 2)"
            ),
            details={"shape": list(points.shape)},
        )
    if not np.isfinite(points).all():
        raise OperationExecutionError(
            code="invalid_points",
            message=f"{input_name} coordinates must be finite",
        )
    return points
