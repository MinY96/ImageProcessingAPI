from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from src.schemas import (
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

from ..common import as_image, ensure_pixel_budget


_SMOOTHING_DTYPES = [
    ImageDType.UINT8,
    ImageDType.UINT16,
    ImageDType.INT16,
    ImageDType.FLOAT32,
    ImageDType.FLOAT64,
]


BOX_BLUR_SPEC = OperationSpec(
    name="box_blur",
    display_name="Box Blur",
    category=OperationCategory.FILTERING,
    description="정규화된 box kernel로 이미지를 평활화합니다.",
    inputs=[
        InputSlotSpec(
            name="image",
            kind=InputKind.IMAGE,
            image_constraint=ImageConstraint(
                allowed_dtypes=_SMOOTHING_DTYPES
            ),
        )
    ],
    parameters={
        "kernel_size": DiscreteParameterSpec(
            title="Kernel Size",
            min_value=1,
            max_value=99,
            step=2,
            default=5,
        )
    },
    outputs=[OutputSlotSpec(name="image", kind=OutputKind.IMAGE)],
)


MEDIAN_BLUR_SPEC = OperationSpec(
    name="median_blur",
    display_name="Median Blur",
    category=OperationCategory.FILTERING,
    description="중앙값 필터로 salt-and-pepper 잡음을 완화합니다.",
    inputs=[
        InputSlotSpec(
            name="image",
            kind=InputKind.IMAGE,
            image_constraint=ImageConstraint(
                allowed_dtypes=[ImageDType.UINT8]
            ),
        )
    ],
    parameters={
        "kernel_size": DiscreteParameterSpec(
            title="Kernel Size",
            min_value=3,
            max_value=99,
            step=2,
            default=5,
        )
    },
    outputs=[OutputSlotSpec(name="image", kind=OutputKind.IMAGE)],
)


BILATERAL_FILTER_SPEC = OperationSpec(
    name="bilateral_filter",
    display_name="Bilateral Filter",
    category=OperationCategory.FILTERING,
    description="경계를 보존하면서 공간·색상 차이를 기준으로 평활화합니다.",
    inputs=[
        InputSlotSpec(
            name="image",
            kind=InputKind.IMAGE,
            image_constraint=ImageConstraint(
                allowed_dtypes=[ImageDType.UINT8, ImageDType.FLOAT32]
            ),
        )
    ],
    parameters={
        "diameter": DiscreteParameterSpec(
            title="Diameter", min_value=1, max_value=31, default=9
        ),
        "sigma_color": ContinuousParameterSpec(
            title="Sigma Color",
            min_value=0.1,
            max_value=500.0,
            default=75.0,
        ),
        "sigma_space": ContinuousParameterSpec(
            title="Sigma Space",
            min_value=0.1,
            max_value=500.0,
            default=75.0,
        ),
    },
    outputs=[OutputSlotSpec(name="image", kind=OutputKind.IMAGE)],
)


def box_blur_handler(
    *, inputs: Mapping[str, Any], params: Mapping[str, Any]
) -> OperationOutput:
    import cv2

    image: ImageData = inputs["image"]
    size = params["kernel_size"]
    result = cv2.blur(image.data, (size, size))
    return OperationOutput(images={"image": as_image(result, source=image)})


def median_blur_handler(
    *, inputs: Mapping[str, Any], params: Mapping[str, Any]
) -> OperationOutput:
    import cv2

    image: ImageData = inputs["image"]
    result = cv2.medianBlur(image.data, params["kernel_size"])
    return OperationOutput(images={"image": as_image(result, source=image)})


def bilateral_filter_handler(
    *, inputs: Mapping[str, Any], params: Mapping[str, Any]
) -> OperationOutput:
    import cv2

    image: ImageData = inputs["image"]
    ensure_pixel_budget(
        pixels=image.width * image.height,
        operation="bilateral_filter",
        max_pixels=16_000_000,
    )
    result = cv2.bilateralFilter(
        image.data,
        params["diameter"],
        params["sigma_color"],
        params["sigma_space"],
    )
    return OperationOutput(images={"image": as_image(result, source=image)})
