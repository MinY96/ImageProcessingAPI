from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np

from src.schemas import (
    CategoryChoice,
    CategoryParameterSpec,
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
from .common import dtype_scale, mask_values, validate_pair


_INTEGER_IMAGES = ImageConstraint(
    allowed_dtypes=[ImageDType.UINT8, ImageDType.UINT16]
)


BLEND_IMAGES_SPEC = OperationSpec(
    name="blend_images",
    display_name="Blend Images",
    category=OperationCategory.COMPOSITING,
    description="두 동일 규격 이미지를 대표적인 layer blend mode로 합성합니다.",
    inputs=[
        InputSlotSpec(name="base", kind=InputKind.IMAGE, image_constraint=_INTEGER_IMAGES),
        InputSlotSpec(name="layer", kind=InputKind.IMAGE, image_constraint=_INTEGER_IMAGES),
    ],
    parameters={
        "mode": CategoryParameterSpec(
            title="Blend Mode",
            choices=[
                CategoryChoice(value=value, label=value.replace("_", " ").title())
                for value in [
                    "normal",
                    "multiply",
                    "screen",
                    "overlay",
                    "soft_light",
                    "hard_light",
                    "difference",
                    "add",
                    "subtract",
                ]
            ],
            default="normal",
        ),
        "opacity": ContinuousParameterSpec(
            title="Opacity", min_value=0.0, max_value=1.0, default=1.0
        ),
    },
    outputs=[OutputSlotSpec(name="image", kind=OutputKind.IMAGE)],
)


APPLY_MASK_SPEC = OperationSpec(
    name="apply_mask",
    display_name="Apply Mask",
    category=OperationCategory.COMPOSITING,
    description="mask 밝기에 따라 base와 effect 이미지를 합성합니다.",
    inputs=[
        InputSlotSpec(name="base", kind=InputKind.IMAGE, image_constraint=_INTEGER_IMAGES),
        InputSlotSpec(name="effect", kind=InputKind.IMAGE, image_constraint=_INTEGER_IMAGES),
        InputSlotSpec(name="mask", kind=InputKind.MASK, image_constraint=_INTEGER_IMAGES),
    ],
    parameters={
        "opacity": ContinuousParameterSpec(
            title="Opacity", min_value=0.0, max_value=1.0, default=1.0
        ),
        "invert_mask": CategoryParameterSpec(
            title="Invert Mask",
            choices=[
                CategoryChoice(value=False, label="Disabled"),
                CategoryChoice(value=True, label="Enabled"),
            ],
            default=False,
        ),
    },
    outputs=[OutputSlotSpec(name="image", kind=OutputKind.IMAGE)],
)


def _blend_mode(base: np.ndarray, layer: np.ndarray, mode: str) -> np.ndarray:
    if mode == "normal":
        return layer
    if mode == "multiply":
        return base * layer
    if mode == "screen":
        return 1.0 - (1.0 - base) * (1.0 - layer)
    if mode == "overlay":
        return np.where(
            base <= 0.5,
            2.0 * base * layer,
            1.0 - 2.0 * (1.0 - base) * (1.0 - layer),
        )
    if mode == "hard_light":
        return np.where(
            layer <= 0.5,
            2.0 * base * layer,
            1.0 - 2.0 * (1.0 - base) * (1.0 - layer),
        )
    if mode == "soft_light":
        return (1.0 - 2.0 * layer) * base * base + 2.0 * layer * base
    if mode == "difference":
        return np.abs(base - layer)
    if mode == "add":
        return np.minimum(base + layer, 1.0)
    return np.maximum(base - layer, 0.0)


def blend_images_handler(
    *, inputs: Mapping[str, Any], params: Mapping[str, Any]
) -> OperationOutput:
    base: ImageData = inputs["base"]
    layer: ImageData = inputs["layer"]
    validate_pair(base, layer, "blend_images")
    ensure_pixel_budget(
        pixels=base.width * base.height,
        operation="blend_images",
        max_pixels=32_000_000,
    )
    scale = dtype_scale(base, "blend_images")
    first = base.data.astype(np.float32) / scale
    second = layer.data.astype(np.float32) / scale
    effect = _blend_mode(first, second, params["mode"])
    output = first * (1.0 - params["opacity"]) + effect * params["opacity"]
    result = np.rint(np.clip(output, 0.0, 1.0) * scale).astype(base.data.dtype)
    return OperationOutput(images={"image": as_image(result, source=base)})


def apply_mask_handler(
    *, inputs: Mapping[str, Any], params: Mapping[str, Any]
) -> OperationOutput:
    base: ImageData = inputs["base"]
    effect: ImageData = inputs["effect"]
    mask: ImageData = inputs["mask"]
    validate_pair(base, effect, "apply_mask")
    ensure_pixel_budget(
        pixels=base.width * base.height,
        operation="apply_mask",
        max_pixels=32_000_000,
    )
    scale = dtype_scale(base, "apply_mask")
    weight = mask_values(mask, base.shape, "apply_mask")
    if params["invert_mask"]:
        weight = 1.0 - weight
    weight *= params["opacity"]
    output = base.data.astype(np.float32) * (1.0 - weight)
    output += effect.data.astype(np.float32) * weight
    result = np.rint(np.clip(output, 0.0, scale)).astype(base.data.dtype)
    return OperationOutput(images={"image": as_image(result, source=base)})
