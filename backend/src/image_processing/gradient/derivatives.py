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
    OperationCategory,
    OperationOutput,
    OperationSpec,
    OutputKind,
    OutputSlotSpec,
)

from ..common import as_image


_GRAY_UINT8_INPUT = InputSlotSpec(
    name="image",
    kind=InputKind.IMAGE,
    image_constraint=ImageConstraint(
        allowed_color_spaces=[ColorSpace.GRAY],
        allowed_dtypes=[ImageDType.UINT8],
    ),
)


SOBEL_SPEC = OperationSpec(
    name="sobel",
    display_name="Sobel Gradient",
    category=OperationCategory.GRADIENT,
    description="Sobel 미분 결과를 절댓값 uint8 영상으로 반환합니다.",
    inputs=[_GRAY_UINT8_INPUT],
    parameters={
        "direction": CategoryParameterSpec(
            title="Direction",
            choices=[
                CategoryChoice(value="x", label="X"),
                CategoryChoice(value="y", label="Y"),
                CategoryChoice(value="xy", label="X + Y"),
            ],
            default="xy",
        ),
        "kernel_size": DiscreteParameterSpec(
            title="Kernel Size", values=[1, 3, 5, 7], default=3
        ),
    },
    outputs=[OutputSlotSpec(name="image", kind=OutputKind.IMAGE)],
)


SCHARR_SPEC = OperationSpec(
    name="scharr",
    display_name="Scharr Gradient",
    category=OperationCategory.GRADIENT,
    description="3x3 Scharr operator로 x 또는 y 방향 미분을 계산합니다.",
    inputs=[_GRAY_UINT8_INPUT],
    parameters={
        "direction": CategoryParameterSpec(
            title="Direction",
            choices=[
                CategoryChoice(value="x", label="X"),
                CategoryChoice(value="y", label="Y"),
                CategoryChoice(value="xy", label="X + Y"),
            ],
            default="xy",
        )
    },
    outputs=[OutputSlotSpec(name="image", kind=OutputKind.IMAGE)],
)


LAPLACIAN_SPEC = OperationSpec(
    name="laplacian",
    display_name="Laplacian",
    category=OperationCategory.GRADIENT,
    description="Laplacian 2차 미분의 절댓값을 반환합니다.",
    inputs=[_GRAY_UINT8_INPUT],
    parameters={
        "kernel_size": DiscreteParameterSpec(
            title="Kernel Size",
            min_value=1,
            max_value=31,
            step=2,
            default=3,
        )
    },
    outputs=[OutputSlotSpec(name="image", kind=OutputKind.IMAGE)],
)


def _combine_derivatives(x_image, y_image):
    import cv2

    x_abs = cv2.convertScaleAbs(x_image)
    y_abs = cv2.convertScaleAbs(y_image)
    return cv2.addWeighted(x_abs, 0.5, y_abs, 0.5, 0)


def sobel_handler(
    *, inputs: Mapping[str, Any], params: Mapping[str, Any]
) -> OperationOutput:
    import cv2

    image: ImageData = inputs["image"]
    direction = params["direction"]
    ksize = params["kernel_size"]
    if direction == "x":
        result = cv2.convertScaleAbs(
            cv2.Sobel(image.data, cv2.CV_64F, 1, 0, ksize=ksize)
        )
    elif direction == "y":
        result = cv2.convertScaleAbs(
            cv2.Sobel(image.data, cv2.CV_64F, 0, 1, ksize=ksize)
        )
    else:
        result = _combine_derivatives(
            cv2.Sobel(image.data, cv2.CV_64F, 1, 0, ksize=ksize),
            cv2.Sobel(image.data, cv2.CV_64F, 0, 1, ksize=ksize),
        )
    return OperationOutput(
        images={
            "image": as_image(
                result, source=image, color_space=ColorSpace.GRAY
            )
        }
    )


def scharr_handler(
    *, inputs: Mapping[str, Any], params: Mapping[str, Any]
) -> OperationOutput:
    import cv2

    image: ImageData = inputs["image"]
    direction = params["direction"]
    if direction == "x":
        result = cv2.convertScaleAbs(
            cv2.Scharr(image.data, cv2.CV_64F, 1, 0)
        )
    elif direction == "y":
        result = cv2.convertScaleAbs(
            cv2.Scharr(image.data, cv2.CV_64F, 0, 1)
        )
    else:
        result = _combine_derivatives(
            cv2.Scharr(image.data, cv2.CV_64F, 1, 0),
            cv2.Scharr(image.data, cv2.CV_64F, 0, 1),
        )
    return OperationOutput(
        images={
            "image": as_image(
                result, source=image, color_space=ColorSpace.GRAY
            )
        }
    )


def laplacian_handler(
    *, inputs: Mapping[str, Any], params: Mapping[str, Any]
) -> OperationOutput:
    import cv2

    image: ImageData = inputs["image"]
    derivative = cv2.Laplacian(
        image.data,
        cv2.CV_64F,
        ksize=params["kernel_size"],
    )
    result = cv2.convertScaleAbs(derivative)
    return OperationOutput(
        images={
            "image": as_image(
                result, source=image, color_space=ColorSpace.GRAY
            )
        }
    )
