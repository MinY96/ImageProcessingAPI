from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np

from src.schemas import (
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
from .common import color_and_alpha, integer_scale, restore_alpha


ADJUST_TONE_SPEC = OperationSpec(
    name="adjust_tone",
    display_name="Adjust Tone",
    category=OperationCategory.ADJUSTMENT,
    description="노출, 대비, 밝기와 gamma를 한 번의 float32 pass에서 조정합니다.",
    inputs=[
        InputSlotSpec(
            name="image",
            kind=InputKind.IMAGE,
            image_constraint=ImageConstraint(
                allowed_dtypes=[ImageDType.UINT8, ImageDType.UINT16]
            ),
        )
    ],
    parameters={
        "exposure": ContinuousParameterSpec(
            title="Exposure EV", min_value=-8.0, max_value=8.0, default=0.0
        ),
        "contrast": ContinuousParameterSpec(
            title="Contrast", min_value=0.0, max_value=4.0, default=1.0
        ),
        "brightness": ContinuousParameterSpec(
            title="Brightness", min_value=-1.0, max_value=1.0, default=0.0
        ),
        "gamma": ContinuousParameterSpec(
            title="Gamma", min_value=0.05, max_value=8.0, default=1.0
        ),
    },
    outputs=[OutputSlotSpec(name="image", kind=OutputKind.IMAGE)],
)


def adjust_tone_handler(
    *, inputs: Mapping[str, Any], params: Mapping[str, Any]
) -> OperationOutput:
    image: ImageData = inputs["image"]
    ensure_pixel_budget(
        pixels=image.width * image.height,
        operation="adjust_tone",
        max_pixels=64_000_000,
    )
    scale = integer_scale(image, "adjust_tone")
    color, alpha = color_and_alpha(image)
    values = color.astype(np.float32) / scale
    values *= np.float32(2.0 ** params["exposure"])
    values = (values - 0.5) * params["contrast"] + 0.5
    values += params["brightness"]
    values = np.power(np.clip(values, 0.0, 1.0), 1.0 / params["gamma"])
    adjusted = np.rint(values * scale).astype(image.data.dtype)
    output = restore_alpha(adjusted, alpha)
    return OperationOutput(images={"image": as_image(output, source=image)})
