from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np

from src.schemas import (
    ColorSpace,
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


WATERSHED_SPEC = OperationSpec(
    name="watershed",
    display_name="Watershed Segmentation",
    category=OperationCategory.SEGMENTATION,
    description="Otsu와 distance transform으로 marker를 자동 생성해 분할합니다.",
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
        "foreground_ratio": ContinuousParameterSpec(
            title="Foreground Distance Ratio",
            min_value=0.05,
            max_value=0.95,
            default=0.4,
        )
    },
    outputs=[
        OutputSlotSpec(name="image", kind=OutputKind.IMAGE),
        OutputSlotSpec(name="labels", kind=OutputKind.IMAGE),
    ],
)


def watershed_handler(
    *, inputs: Mapping[str, Any], params: Mapping[str, Any]
) -> OperationOutput:
    import cv2

    image: ImageData = inputs["image"]
    ensure_pixel_budget(
        pixels=image.width * image.height,
        operation="watershed",
        max_pixels=16_000_000,
    )
    gray = cv2.cvtColor(image.data, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(
        gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU
    )
    kernel = np.ones((3, 3), dtype=np.uint8)
    opening = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=2)
    sure_background = cv2.dilate(opening, kernel, iterations=3)
    distance = cv2.distanceTransform(opening, cv2.DIST_L2, 5)
    _, sure_foreground = cv2.threshold(
        distance,
        params["foreground_ratio"] * float(distance.max()),
        255,
        cv2.THRESH_BINARY,
    )
    sure_foreground = sure_foreground.astype(np.uint8)
    unknown = cv2.subtract(sure_background, sure_foreground)
    _, markers = cv2.connectedComponents(sure_foreground)
    markers = markers.astype(np.int32) + 1
    markers[unknown == 255] = 0
    labels = cv2.watershed(image.data.copy(), markers)

    annotated = image.data.copy()
    annotated[labels == -1] = (0, 0, 255)
    return OperationOutput(
        images={
            "image": as_image(annotated, source=image),
            "labels": as_image(
                labels,
                source=image,
                color_space=ColorSpace.UNKNOWN,
            ),
        }
    )
