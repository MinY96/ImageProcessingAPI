from __future__ import annotations

import numpy as np

from src.registry.errors import OperationExecutionError
from src.schemas import ImageData


def validate_pair(
    first: ImageData,
    second: ImageData,
    operation: str,
) -> None:
    if first.shape != second.shape:
        raise OperationExecutionError(
            code="incompatible_image_shape",
            message=f"{operation} inputs must have the same shape",
            details={"first": list(first.shape), "second": list(second.shape)},
        )
    if first.data.dtype != second.data.dtype:
        raise OperationExecutionError(
            code="incompatible_image_dtype",
            message=f"{operation} inputs must have the same dtype",
            details={"first": first.dtype, "second": second.dtype},
        )
    if first.color_space != second.color_space:
        raise OperationExecutionError(
            code="incompatible_color_space",
            message=f"{operation} inputs must have the same color space",
            details={
                "first": first.color_space.value,
                "second": second.color_space.value,
            },
        )


def dtype_scale(image: ImageData, operation: str) -> float:
    if image.data.dtype == np.uint8:
        return 255.0
    if image.data.dtype == np.uint16:
        return 65535.0
    raise OperationExecutionError(
        code="invalid_image_dtype",
        message=f"{operation} requires uint8 or uint16 images",
        details={"dtype": image.dtype},
    )


def mask_values(mask: ImageData, shape: tuple[int, ...], operation: str) -> np.ndarray:
    if mask.data.shape[:2] != shape[:2]:
        raise OperationExecutionError(
            code="incompatible_mask_shape",
            message=f"{operation} mask must match image width and height",
            details={"image": list(shape[:2]), "mask": list(mask.data.shape[:2])},
        )
    if mask.data.dtype not in {np.dtype(np.uint8), np.dtype(np.uint16)}:
        raise OperationExecutionError(
            code="invalid_mask_dtype",
            message="mask must use uint8 or uint16",
            details={"dtype": mask.dtype},
        )
    maximum = float(np.iinfo(mask.data.dtype).max)
    values = mask.data.astype(np.float32) / maximum
    if len(shape) == 3:
        values = values[..., None]
    return values
