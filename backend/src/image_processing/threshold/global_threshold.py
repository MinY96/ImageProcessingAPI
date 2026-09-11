from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from src.registry.errors import OperationExecutionError
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
    OperationCategory,
    OperationOutput,
    OperationSpec,
    OutputKind,
    OutputSlotSpec,
)

from ..common import as_image


GLOBAL_THRESHOLD_SPEC = OperationSpec(
    name="global_threshold",
    display_name="Global Threshold",
    category=OperationCategory.THRESHOLD,
    description="고정 임계값 또는 Otsu 방식으로 단일 채널 영상을 분할합니다.",
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
        "threshold": DiscreteParameterSpec(
            title="Threshold", min_value=0, max_value=255, default=127
        ),
        "max_value": DiscreteParameterSpec(
            title="Maximum Value", min_value=1, max_value=255, default=255
        ),
        "mode": CategoryParameterSpec(
            title="Threshold Mode",
            choices=[
                CategoryChoice(value="binary", label="Binary"),
                CategoryChoice(value="binary_inv", label="Binary Inverse"),
                CategoryChoice(value="trunc", label="Truncate"),
                CategoryChoice(value="tozero", label="To Zero"),
                CategoryChoice(value="tozero_inv", label="To Zero Inverse"),
            ],
            default="binary",
        ),
        "use_otsu": CategoryParameterSpec(
            title="Use Otsu",
            choices=[
                CategoryChoice(value=False, label="Disabled"),
                CategoryChoice(value=True, label="Enabled"),
            ],
            default=False,
        ),
    },
    outputs=[
        OutputSlotSpec(name="image", kind=OutputKind.MASK),
        OutputSlotSpec(name="threshold", kind=OutputKind.SCALAR),
    ],
)


def global_threshold_handler(
    *, inputs: Mapping[str, Any], params: Mapping[str, Any]
) -> OperationOutput:
    import cv2

    image: ImageData = inputs["image"]
    modes = {
        "binary": cv2.THRESH_BINARY,
        "binary_inv": cv2.THRESH_BINARY_INV,
        "trunc": cv2.THRESH_TRUNC,
        "tozero": cv2.THRESH_TOZERO,
        "tozero_inv": cv2.THRESH_TOZERO_INV,
    }
    mode = params["mode"]
    flag = modes[mode]

    if params["use_otsu"]:
        if mode not in {"binary", "binary_inv"}:
            raise OperationExecutionError(
                code="invalid_parameter_combination",
                message="Otsu is only valid for binary threshold modes",
                details={"mode": mode},
            )
        flag |= cv2.THRESH_OTSU

    used_threshold, thresholded = cv2.threshold(
        image.data,
        params["threshold"],
        params["max_value"],
        flag,
    )
    color_space = (
        ColorSpace.BINARY
        if mode in {"binary", "binary_inv"}
        else ColorSpace.GRAY
    )
    return OperationOutput(
        images={
            "image": as_image(
                thresholded,
                source=image,
                color_space=color_space,
            )
        },
        data={"threshold": float(used_threshold)},
    )
