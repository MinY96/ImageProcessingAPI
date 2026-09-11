from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from src.schemas import (
    CategoryChoice,
    CategoryParameterSpec,
    ColorSpace,
    DiscreteParameterSpec,
    ImageConstraint,
    ImageDType,
    ImageData,
    InputKind,
    InputSlotSpec,
    LessThanConstraint,
    OperationCategory,
    OperationOutput,
    OperationSpec,
    OutputKind,
    OutputSlotSpec,
)


CANNY_SPEC = OperationSpec(
    name="canny",
    display_name="Canny Edge",
    category=OperationCategory.GRADIENT,
    description="단일 채널 uint8 이미지에서 Canny edge를 검출합니다.",
    inputs=[
        InputSlotSpec(
            name="image",
            kind=InputKind.IMAGE,
            image_constraint=ImageConstraint(
                allowed_color_spaces=[ColorSpace.GRAY],
                allowed_dtypes=[ImageDType.UINT8],
            ),
        )
    ],
    parameters={
        "threshold_low": DiscreteParameterSpec(
            title="Low Threshold",
            min_value=0,
            max_value=255,
            default=100,
            order=0,
        ),
        "threshold_high": DiscreteParameterSpec(
            title="High Threshold",
            min_value=0,
            max_value=255,
            default=200,
            order=1,
        ),
        "aperture_size": DiscreteParameterSpec(
            title="Aperture Size",
            values=[3, 5, 7],
            default=3,
            order=2,
        ),
        "l2_gradient": CategoryParameterSpec(
            title="L2 Gradient",
            choices=[
                CategoryChoice(value=False, label="Disabled"),
                CategoryChoice(value=True, label="Enabled"),
            ],
            default=False,
            order=3,
        ),
    },
    constraints=[
        LessThanConstraint(
            left="threshold_low",
            right="threshold_high",
            message="Low threshold must be smaller than high threshold.",
        )
    ],
    outputs=[
        OutputSlotSpec(name="image", kind=OutputKind.MASK)
    ],
)


def canny_handler(
    *,
    inputs: Mapping[str, Any],
    params: Mapping[str, Any],
) -> OperationOutput:
    import cv2

    image: ImageData = inputs["image"]
    edges = cv2.Canny(
        image=image.data,
        threshold1=params["threshold_low"],
        threshold2=params["threshold_high"],
        apertureSize=params["aperture_size"],
        L2gradient=params["l2_gradient"],
    )

    return OperationOutput(
        images={
            "image": ImageData(
                data=edges,
                color_space=ColorSpace.BINARY,
                name=image.name,
            )
        }
    )
