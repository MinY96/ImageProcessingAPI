from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np

from src.schemas import (
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

from ..common import as_image
from .common import color_and_alpha, integer_scale, restore_alpha


INVERT_SPEC = OperationSpec(
    name="invert",
    display_name="Invert",
    category=OperationCategory.ADJUSTMENT,
    description="색상 채널을 반전하고 alpha 채널은 보존합니다.",
    inputs=[
        InputSlotSpec(
            name="image",
            kind=InputKind.IMAGE,
            image_constraint=ImageConstraint(
                allowed_dtypes=[ImageDType.UINT8, ImageDType.UINT16]
            ),
        )
    ],
    outputs=[OutputSlotSpec(name="image", kind=OutputKind.IMAGE)],
)


def invert_handler(
    *, inputs: Mapping[str, Any], params: Mapping[str, Any]
) -> OperationOutput:
    image: ImageData = inputs["image"]
    maximum = integer_scale(image, "invert")
    color, alpha = color_and_alpha(image)
    inverted = (maximum - color).astype(image.data.dtype)
    return OperationOutput(
        images={"image": as_image(restore_alpha(inverted, alpha), source=image)}
    )
