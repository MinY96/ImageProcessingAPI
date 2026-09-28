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

from ..common import ensure_pixel_budget


REMOVE_BACKGROUND_SPEC = OperationSpec(
    name="remove_background",
    display_name="Remove Background (GrabCut)",
    category=OperationCategory.SEGMENTATION,
    description=(
        "사용자가 지정한 전경 사각형을 바탕으로 GrabCut 배경 분리를 수행하고 "
        "투명 알파 채널이 포함된 BGRA 이미지를 반환합니다."
    ),
    inputs=[
        InputSlotSpec(
            name="image",
            kind=InputKind.IMAGE,
            image_constraint=ImageConstraint(
                allowed_color_spaces=[ColorSpace.BGR, ColorSpace.BGRA],
                allowed_dtypes=[ImageDType.UINT8],
            ),
        )
    ],
    parameters={
        "x": DiscreteParameterSpec(title="Foreground Rectangle X", min_value=0, max_value=8191, required=True),
        "y": DiscreteParameterSpec(title="Foreground Rectangle Y", min_value=0, max_value=8191, required=True),
        "width": DiscreteParameterSpec(title="Foreground Rectangle Width", min_value=2, max_value=8192, required=True),
        "height": DiscreteParameterSpec(title="Foreground Rectangle Height", min_value=2, max_value=8192, required=True),
        "iterations": DiscreteParameterSpec(title="GrabCut Iterations", min_value=1, max_value=20, default=5),
        "edge_feather": DiscreteParameterSpec(title="Edge Feather Radius", min_value=0, max_value=31, default=3),
    },
    outputs=[
        OutputSlotSpec(name="image", kind=OutputKind.IMAGE),
        OutputSlotSpec(name="mask", kind=OutputKind.MASK),
        OutputSlotSpec(name="foreground_ratio", kind=OutputKind.SCALAR),
        OutputSlotSpec(name="rectangle", kind=OutputKind.ARRAY),
    ],
)


def remove_background_handler(
    *, inputs: Mapping[str, Any], params: Mapping[str, Any]
) -> OperationOutput:
    import cv2

    image: ImageData = inputs["image"]
    ensure_pixel_budget(
        pixels=image.width * image.height,
        operation="remove_background",
        max_pixels=16_000_000,
    )
    x, y, width, height = (int(params[name]) for name in ("x", "y", "width", "height"))
    if x + width > image.width or y + height > image.height:
        raise OperationExecutionError(
            code="invalid_foreground_rectangle",
            message="foreground rectangle must fit inside the image",
            details={"image_size": [image.width, image.height], "rectangle": [x, y, width, height]},
        )
    if width < 2 or height < 2:
        raise OperationExecutionError(
            code="invalid_foreground_rectangle",
            message="foreground rectangle width and height must be at least 2 pixels",
        )
    if x == 0 and y == 0 and width == image.width and height == image.height:
        raise OperationExecutionError(
            code="invalid_foreground_rectangle",
            message="foreground rectangle must leave some background pixels outside the rectangle",
        )

    bgr = image.data[:, :, :3] if image.data.ndim == 3 and image.data.shape[2] == 4 else image.data
    mask = np.zeros((image.height, image.width), dtype=np.uint8)
    background_model = np.zeros((1, 65), dtype=np.float64)
    foreground_model = np.zeros((1, 65), dtype=np.float64)
    try:
        cv2.grabCut(
            bgr,
            mask,
            (x, y, width, height),
            background_model,
            foreground_model,
            int(params.get("iterations", 5)),
            cv2.GC_INIT_WITH_RECT,
        )
    except cv2.error as exc:
        raise OperationExecutionError(
            code="grabcut_failed",
            message="GrabCut could not separate the foreground; select a tighter rectangle",
            details={"reason": str(exc)},
        ) from exc

    alpha = np.where(
        (mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0
    ).astype(np.uint8)
    if image.data.ndim == 3 and image.data.shape[2] == 4:
        alpha = cv2.min(alpha, image.data[:, :, 3])

    feather = int(params.get("edge_feather", 0))
    if feather > 0:
        kernel = feather * 2 + 1
        soft = cv2.GaussianBlur(alpha, (kernel, kernel), 0)
        # Preserve confident interiors and smooth only the immediate contour band.
        eroded = cv2.erode(alpha, np.ones((3, 3), np.uint8), iterations=1)
        dilated = cv2.dilate(alpha, np.ones((3, 3), np.uint8), iterations=1)
        edge_band = cv2.subtract(dilated, eroded) > 0
        alpha[edge_band] = soft[edge_band]

    bgra = cv2.cvtColor(bgr, cv2.COLOR_BGR2BGRA)
    bgra[:, :, 3] = alpha
    foreground_mask = np.where(alpha > 0, 255, 0).astype(np.uint8)
    return OperationOutput(
        images={
            "image": ImageData(data=bgra, color_space=ColorSpace.BGRA, name=image.name),
            "mask": ImageData(data=foreground_mask, color_space=ColorSpace.BINARY, name="foreground_mask"),
        },
        data={
            "foreground_ratio": float(np.count_nonzero(foreground_mask) / foreground_mask.size),
            "rectangle": [x, y, width, height],
        },
    )
