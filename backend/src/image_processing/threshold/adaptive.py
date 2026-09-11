from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from src.schemas import (
    CategoryChoice,
    CategoryParameterSpec,
    ColorSpace,
    ContinuousParameterSpec,
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


ADAPTIVE_THRESHOLD_SPEC = OperationSpec(
    name="adaptive_threshold",
    display_name="Adaptive Threshold",
    category=OperationCategory.THRESHOLD,
    description="주변 영역의 통계로 각 픽셀의 임계값을 계산합니다.",
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
        "max_value": DiscreteParameterSpec(
            title="Maximum Value", min_value=1, max_value=255, default=255
        ),
        "method": CategoryParameterSpec(
            title="Adaptive Method",
            choices=[
                CategoryChoice(value="mean", label="Mean"),
                CategoryChoice(value="gaussian", label="Gaussian"),
            ],
            default="gaussian",
        ),
        "mode": CategoryParameterSpec(
            title="Threshold Mode",
            choices=[
                CategoryChoice(value="binary", label="Binary"),
                CategoryChoice(value="binary_inv", label="Binary Inverse"),
            ],
            default="binary",
        ),
        "block_size": DiscreteParameterSpec(
            title="Block Size",
            min_value=3,
            max_value=99,
            step=2,
            default=11,
        ),
        "c": ContinuousParameterSpec(
            title="Constant C",
            min_value=-100.0,
            max_value=100.0,
            default=2.0,
        ),
    },
    outputs=[OutputSlotSpec(name="image", kind=OutputKind.MASK)],
)


def adaptive_threshold_handler(
    *, inputs: Mapping[str, Any], params: Mapping[str, Any]
) -> OperationOutput:
    import cv2

    image: ImageData = inputs["image"]
    methods = {
        "mean": cv2.ADAPTIVE_THRESH_MEAN_C,
        "gaussian": cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
    }
    modes = {
        "binary": cv2.THRESH_BINARY,
        "binary_inv": cv2.THRESH_BINARY_INV,
    }
    result = cv2.adaptiveThreshold(
        image.data,
        params["max_value"],
        methods[params["method"]],
        modes[params["mode"]],
        params["block_size"],
        params["c"],
    )
    return OperationOutput(
        images={
            "image": as_image(
                result,
                source=image,
                color_space=ColorSpace.BINARY,
            )
        }
    )
