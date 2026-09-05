from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from src.schemas import (
    CategoryChoice,
    CategoryParameterSpec,
    DiscreteParameterSpec,
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

from ..common import as_image, ensure_output_size


PYRAMID_SPEC = OperationSpec(
    name="image_pyramid",
    display_name="Image Pyramid",
    category=OperationCategory.TRANSFORM,
    description="Gaussian pyramid를 단계별로 확대 또는 축소합니다.",
    inputs=[
        InputSlotSpec(
            name="image",
            kind=InputKind.IMAGE,
            image_constraint=ImageConstraint(
                allowed_dtypes=[
                    ImageDType.UINT8,
                    ImageDType.UINT16,
                    ImageDType.INT16,
                    ImageDType.FLOAT32,
                    ImageDType.FLOAT64,
                ]
            ),
        )
    ],
    parameters={
        "direction": CategoryParameterSpec(
            title="Direction",
            choices=[
                CategoryChoice(value="down", label="PyrDown"),
                CategoryChoice(value="up", label="PyrUp"),
            ],
            default="down",
        ),
        "levels": DiscreteParameterSpec(
            title="Levels", min_value=1, max_value=4, default=1
        ),
    },
    outputs=[OutputSlotSpec(name="image", kind=OutputKind.IMAGE)],
)


def pyramid_handler(
    *, inputs: Mapping[str, Any], params: Mapping[str, Any]
) -> OperationOutput:
    import cv2

    image: ImageData = inputs["image"]
    levels = params["levels"]
    if params["direction"] == "up":
        target_width = image.width * (2**levels)
        target_height = image.height * (2**levels)
    else:
        divisor = 2**levels
        target_width = max(1, image.width // divisor)
        target_height = max(1, image.height // divisor)

    ensure_output_size(
        width=target_width,
        height=target_height,
        operation="image_pyramid",
    )
    result = image.data
    for _ in range(levels):
        result = (
            cv2.pyrUp(result)
            if params["direction"] == "up"
            else cv2.pyrDown(result)
        )

    return OperationOutput(images={"image": as_image(result, source=image)})
