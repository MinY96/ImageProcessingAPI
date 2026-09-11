from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np

from src.registry.errors import OperationExecutionError
from src.schemas import (
    CategoryChoice,
    CategoryParameterSpec,
    ColorSpace,
    ContinuousParameterSpec,
    ImageConstraint,
    ImageDType,
    ImageData,
    InputKind,
    InputSlotSpec,
    OperationCategory,
    OperationOutput,
    OperationSpec,
    OutputKind,
    OutputSlotSpec,
)

from ..common import as_image, ensure_pixel_budget
from .common import color_and_alpha, restore_alpha, restore_from_rgb, to_rgb_and_alpha


APPLY_LUT_SPEC = OperationSpec(
    name="apply_lut",
    display_name="Apply 1D LUT",
    category=OperationCategory.ADJUSTMENT,
    description="uint8 이미지에 256-entry 단일/채널별 LUT를 적용합니다.",
    inputs=[
        InputSlotSpec(
            name="image",
            kind=InputKind.IMAGE,
            image_constraint=ImageConstraint(allowed_dtypes=[ImageDType.UINT8]),
        ),
        InputSlotSpec(name="lut", kind=InputKind.ARRAY),
    ],
    parameters={
        "intensity": ContinuousParameterSpec(
            title="Intensity", min_value=0.0, max_value=1.0, default=1.0
        )
    },
    outputs=[OutputSlotSpec(name="image", kind=OutputKind.IMAGE)],
)


APPLY_3D_LUT_SPEC = OperationSpec(
    name="apply_3d_lut",
    display_name="Apply 3D LUT",
    category=OperationCategory.ADJUSTMENT,
    description="RGB 축 순서의 NxNxNx3 color cube를 chunk 단위로 보간합니다.",
    inputs=[
        InputSlotSpec(
            name="image",
            kind=InputKind.IMAGE,
            image_constraint=ImageConstraint(
                allowed_color_spaces=[
                    ColorSpace.BGR,
                    ColorSpace.RGB,
                    ColorSpace.BGRA,
                    ColorSpace.RGBA,
                ],
                allowed_dtypes=[ImageDType.UINT8],
            ),
        ),
        InputSlotSpec(name="lut", kind=InputKind.ARRAY),
    ],
    parameters={
        "interpolation": CategoryParameterSpec(
            title="Interpolation",
            choices=[
                CategoryChoice(value="trilinear", label="Trilinear"),
                CategoryChoice(value="nearest", label="Nearest"),
            ],
            default="trilinear",
        ),
        "intensity": ContinuousParameterSpec(
            title="Intensity", min_value=0.0, max_value=1.0, default=1.0
        ),
    },
    outputs=[OutputSlotSpec(name="image", kind=OutputKind.IMAGE)],
)


def _array(value: Any, operation: str) -> np.ndarray:
    try:
        result = np.asarray(value, dtype=np.float32)
    except (TypeError, ValueError) as exc:
        raise OperationExecutionError(
            code="invalid_lut", message=f"{operation} LUT must be numeric"
        ) from exc
    if not np.isfinite(result).all():
        raise OperationExecutionError(
            code="invalid_lut", message="LUT values must be finite"
        )
    return result


def apply_lut_handler(
    *, inputs: Mapping[str, Any], params: Mapping[str, Any]
) -> OperationOutput:
    image: ImageData = inputs["image"]
    lut = _array(inputs["lut"], "apply_lut")
    if lut.shape in {(1, 256), (256, 1)}:
        lut = lut.reshape(256)
    color, alpha = color_and_alpha(image)
    channels = 1 if color.ndim == 2 else color.shape[2]
    if lut.shape == (256,):
        transformed = lut[color]
    elif lut.shape == (256, channels):
        if channels == 1:
            transformed = lut[color, 0]
        else:
            transformed = np.empty_like(color, dtype=np.float32)
            for channel in range(channels):
                transformed[..., channel] = lut[color[..., channel], channel]
    else:
        raise OperationExecutionError(
            code="invalid_lut",
            message="1D LUT must have shape (256,) or (256, image_channels)",
            details={"shape": list(lut.shape), "image_channels": channels},
        )
    transformed = np.clip(transformed, 0.0, 255.0)
    intensity = params["intensity"]
    blended = np.rint(color * (1.0 - intensity) + transformed * intensity).astype(
        np.uint8
    )
    return OperationOutput(
        images={"image": as_image(restore_alpha(blended, alpha), source=image)}
    )


def _validate_cube(value: Any) -> np.ndarray:
    cube = _array(value, "apply_3d_lut")
    if (
        cube.ndim != 4
        or cube.shape[-1] != 3
        or cube.shape[0] != cube.shape[1]
        or cube.shape[1] != cube.shape[2]
        or not 2 <= cube.shape[0] <= 65
    ):
        raise OperationExecutionError(
            code="invalid_lut",
            message="3D LUT must have shape (N, N, N, 3), 2 <= N <= 65",
            details={"shape": list(cube.shape)},
        )
    maximum = float(cube.max(initial=0.0))
    minimum = float(cube.min(initial=0.0))
    if minimum < 0.0 or maximum > 255.0:
        raise OperationExecutionError(
            code="invalid_lut", message="3D LUT values must be in [0, 1] or [0, 255]"
        )
    if maximum > 1.0:
        cube = cube / 255.0
    return np.ascontiguousarray(cube, dtype=np.float32)


def _trilinear(cube: np.ndarray, values: np.ndarray) -> np.ndarray:
    size = cube.shape[0]
    coordinates = np.clip(values, 0.0, 1.0) * (size - 1)
    low = np.floor(coordinates).astype(np.int32)
    high = np.minimum(low + 1, size - 1)
    fraction = coordinates - low
    r0, g0, b0 = low.T
    r1, g1, b1 = high.T
    fr, fg, fb = fraction.T
    c000 = cube[r0, g0, b0]
    c001 = cube[r0, g0, b1]
    c010 = cube[r0, g1, b0]
    c011 = cube[r0, g1, b1]
    c100 = cube[r1, g0, b0]
    c101 = cube[r1, g0, b1]
    c110 = cube[r1, g1, b0]
    c111 = cube[r1, g1, b1]
    c00 = c000 * (1 - fb[:, None]) + c001 * fb[:, None]
    c01 = c010 * (1 - fb[:, None]) + c011 * fb[:, None]
    c10 = c100 * (1 - fb[:, None]) + c101 * fb[:, None]
    c11 = c110 * (1 - fb[:, None]) + c111 * fb[:, None]
    c0 = c00 * (1 - fg[:, None]) + c01 * fg[:, None]
    c1 = c10 * (1 - fg[:, None]) + c11 * fg[:, None]
    return c0 * (1 - fr[:, None]) + c1 * fr[:, None]


def apply_3d_lut_handler(
    *, inputs: Mapping[str, Any], params: Mapping[str, Any]
) -> OperationOutput:
    image: ImageData = inputs["image"]
    ensure_pixel_budget(
        pixels=image.width * image.height,
        operation="apply_3d_lut",
        max_pixels=32_000_000,
    )
    cube = _validate_cube(inputs["lut"])
    rgb, alpha = to_rgb_and_alpha(image)
    flat = rgb.reshape(-1, 3).astype(np.float32) / 255.0
    transformed = np.empty_like(flat)
    chunk_size = 100_000
    for start in range(0, len(flat), chunk_size):
        stop = min(start + chunk_size, len(flat))
        chunk = flat[start:stop]
        if params["interpolation"] == "nearest":
            indices = np.rint(chunk * (cube.shape[0] - 1)).astype(np.int32)
            transformed[start:stop] = cube[indices[:, 0], indices[:, 1], indices[:, 2]]
        else:
            transformed[start:stop] = _trilinear(cube, chunk)
    intensity = params["intensity"]
    output_rgb = np.rint(
        np.clip(flat * (1.0 - intensity) + transformed * intensity, 0.0, 1.0)
        * 255.0
    ).astype(np.uint8).reshape(rgb.shape)
    output = restore_from_rgb(output_rgb, alpha, image.color_space)
    return OperationOutput(images={"image": as_image(output, source=image)})
