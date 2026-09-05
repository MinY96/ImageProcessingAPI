from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np

from src.registry.errors import OperationExecutionError
from src.schemas import (
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

from ..common import as_image, ensure_pixel_budget


GRABCUT_SPEC = OperationSpec(
    name="grabcut",
    display_name="GrabCut",
    category=OperationCategory.SEGMENTATION,
    description="지정 사각형을 초기 전경 영역으로 사용해 배경을 분리합니다.",
    inputs=[
        InputSlotSpec(
            name="image",
            kind=InputKind.IMAGE,
            image_constraint=ImageConstraint(
                allowed_color_spaces=[ColorSpace.BGR],
                allowed_dtypes=[ImageDType.UINT8],
            ),
        )
    ],
    parameters={
        "x": DiscreteParameterSpec(
            title="Rectangle X", min_value=0, max_value=8191, required=True
        ),
        "y": DiscreteParameterSpec(
            title="Rectangle Y", min_value=0, max_value=8191, required=True
        ),
        "width": DiscreteParameterSpec(
            title="Rectangle Width", min_value=1, max_value=8192, required=True
        ),
        "height": DiscreteParameterSpec(
            title="Rectangle Height", min_value=1, max_value=8192, required=True
        ),
        "iterations": DiscreteParameterSpec(
            title="Iterations", min_value=1, max_value=20, default=5
        ),
    },
    outputs=[
        OutputSlotSpec(name="image", kind=OutputKind.IMAGE),
        OutputSlotSpec(name="mask", kind=OutputKind.MASK),
    ],
)


def grabcut_handler(
    *, inputs: Mapping[str, Any], params: Mapping[str, Any]
) -> OperationOutput:
    import cv2

    image: ImageData = inputs["image"]
    ensure_pixel_budget(
        pixels=image.width * image.height,
        operation="grabcut",
        max_pixels=32_000_000,
    )
    rectangle = (
        params["x"],
        params["y"],
        params["width"],
        params["height"],
    )
    if (
        params["x"] + params["width"] > image.width
        or params["y"] + params["height"] > image.height
    ):
        raise OperationExecutionError(
            code="invalid_rectangle",
            message="GrabCut rectangle must fit inside the image",
            details={
                "rectangle": list(rectangle),
                "image_size": [image.width, image.height],
            },
        )

    mask = np.zeros(image.data.shape[:2], dtype=np.uint8)
    background_model = np.zeros((1, 65), dtype=np.float64)
    foreground_model = np.zeros((1, 65), dtype=np.float64)
    cv2.grabCut(
        image.data,
        mask,
        rectangle,
        background_model,
        foreground_model,
        params["iterations"],
        cv2.GC_INIT_WITH_RECT,
    )
    binary_mask = np.where(
        (mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD),
        255,
        0,
    ).astype(np.uint8)
    foreground = cv2.bitwise_and(
        image.data, image.data, mask=binary_mask
    )
    return OperationOutput(
        images={
            "image": as_image(foreground, source=image),
            "mask": as_image(
                binary_mask,
                source=image,
                color_space=ColorSpace.BINARY,
            ),
        }
    )
