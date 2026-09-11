from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from src.schemas import (
    CategoryChoice,
    CategoryParameterSpec,
    ColorSpace,
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

from ..common import as_image, to_bgr


_COLOR_CHOICES = [
    CategoryChoice(value=item.value, label=item.value.upper())
    for item in (
        ColorSpace.GRAY,
        ColorSpace.BGR,
        ColorSpace.RGB,
        ColorSpace.HSV,
        ColorSpace.LAB,
        ColorSpace.BGRA,
        ColorSpace.RGBA,
    )
]


CONVERT_COLOR_SPEC = OperationSpec(
    name="convert_color",
    display_name="Convert Color Space",
    category=OperationCategory.COLOR,
    description="uint8 이미지를 지정한 OpenCV 색공간으로 변환합니다.",
    inputs=[
        InputSlotSpec(
            name="image",
            kind=InputKind.IMAGE,
            image_constraint=ImageConstraint(
                allowed_color_spaces=[
                    ColorSpace.GRAY,
                    ColorSpace.BINARY,
                    ColorSpace.BGR,
                    ColorSpace.RGB,
                    ColorSpace.HSV,
                    ColorSpace.LAB,
                    ColorSpace.BGRA,
                    ColorSpace.RGBA,
                ],
                allowed_dtypes=[ImageDType.UINT8],
            ),
        )
    ],
    parameters={
        "target_color_space": CategoryParameterSpec(
            title="Target Color Space",
            choices=_COLOR_CHOICES,
            default="gray",
        )
    },
    outputs=[OutputSlotSpec(name="image", kind=OutputKind.IMAGE)],
)


def convert_color_handler(
    *,
    inputs: Mapping[str, Any],
    params: Mapping[str, Any],
) -> OperationOutput:
    import cv2

    image: ImageData = inputs["image"]
    target = ColorSpace(params["target_color_space"])

    if image.color_space == target:
        converted = image.data.copy()
    elif target == ColorSpace.GRAY:
        converted = cv2.cvtColor(to_bgr(image), cv2.COLOR_BGR2GRAY)
    else:
        bgr = to_bgr(image)
        conversions = {
            ColorSpace.BGR: None,
            ColorSpace.RGB: cv2.COLOR_BGR2RGB,
            ColorSpace.HSV: cv2.COLOR_BGR2HSV,
            ColorSpace.LAB: cv2.COLOR_BGR2LAB,
            ColorSpace.BGRA: cv2.COLOR_BGR2BGRA,
            ColorSpace.RGBA: cv2.COLOR_BGR2RGBA,
        }
        code = conversions[target]
        converted = bgr if code is None else cv2.cvtColor(bgr, code)

    return OperationOutput(
        images={
            "image": as_image(
                converted,
                source=image,
                color_space=target,
            )
        }
    )
