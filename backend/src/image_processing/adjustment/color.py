from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np

from src.schemas import (
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
from .common import restore_from_rgb, to_rgb_and_alpha


ADJUST_COLOR_SPEC = OperationSpec(
    name="adjust_color",
    display_name="Adjust Color",
    category=OperationCategory.ADJUSTMENT,
    description="색조, 채도, vibrance, 색온도와 tint를 조정합니다.",
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
        )
    ],
    parameters={
        "hue_shift": ContinuousParameterSpec(
            title="Hue Shift", unit="degree", min_value=-180.0, max_value=180.0, default=0.0
        ),
        "saturation": ContinuousParameterSpec(
            title="Saturation", min_value=0.0, max_value=4.0, default=1.0
        ),
        "vibrance": ContinuousParameterSpec(
            title="Vibrance", min_value=-1.0, max_value=1.0, default=0.0
        ),
        "temperature": ContinuousParameterSpec(
            title="Temperature", min_value=-1.0, max_value=1.0, default=0.0
        ),
        "tint": ContinuousParameterSpec(
            title="Tint", min_value=-1.0, max_value=1.0, default=0.0
        ),
    },
    outputs=[OutputSlotSpec(name="image", kind=OutputKind.IMAGE)],
)


def adjust_color_handler(
    *, inputs: Mapping[str, Any], params: Mapping[str, Any]
) -> OperationOutput:
    import cv2

    image: ImageData = inputs["image"]
    ensure_pixel_budget(
        pixels=image.width * image.height,
        operation="adjust_color",
        max_pixels=32_000_000,
    )
    rgb, alpha = to_rgb_and_alpha(image)
    values = rgb.astype(np.float32) / 255.0

    temperature = params["temperature"] * 0.15
    values[..., 0] += temperature
    values[..., 2] -= temperature
    tint = params["tint"] * 0.10
    values[..., 1] += tint
    values[..., (0, 2)] -= tint * 0.5
    values = np.clip(values, 0.0, 1.0)

    hsv = cv2.cvtColor(values, cv2.COLOR_RGB2HSV)
    hsv[..., 0] = np.mod(hsv[..., 0] + params["hue_shift"], 360.0)
    saturation = np.clip(hsv[..., 1] * params["saturation"], 0.0, 1.0)
    vibrance = params["vibrance"]
    if vibrance >= 0:
        saturation += vibrance * (1.0 - saturation) * np.sqrt(saturation)
    else:
        saturation *= 1.0 + vibrance
    hsv[..., 1] = np.clip(saturation, 0.0, 1.0)
    adjusted_rgb = np.rint(
        np.clip(cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB), 0.0, 1.0) * 255.0
    ).astype(np.uint8)
    output = restore_from_rgb(adjusted_rgb, alpha, image.color_space)
    return OperationOutput(images={"image": as_image(output, source=image)})
