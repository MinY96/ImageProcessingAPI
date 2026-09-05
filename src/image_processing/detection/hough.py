from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np

from src.registry.errors import OperationExecutionError
from src.schemas import (
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

from ..common import as_image, ensure_pixel_budget, to_bgr


_GRAY_OR_BINARY_INPUT = InputSlotSpec(
    name="image",
    kind=InputKind.IMAGE,
    image_constraint=ImageConstraint(
        allowed_color_spaces=[ColorSpace.GRAY, ColorSpace.BINARY],
        allowed_dtypes=[ImageDType.UINT8],
    ),
)


HOUGH_LINES_P_SPEC = OperationSpec(
    name="hough_lines_p",
    display_name="Probabilistic Hough Lines",
    category=OperationCategory.DETECTION,
    description="이진 edge 영상에서 선분을 검출합니다.",
    inputs=[_GRAY_OR_BINARY_INPUT],
    parameters={
        "rho": ContinuousParameterSpec(
            title="Rho Resolution",
            min_value=0.1,
            max_value=100.0,
            default=1.0,
        ),
        "theta_degrees": ContinuousParameterSpec(
            title="Theta Resolution",
            unit="degree",
            min_value=0.1,
            max_value=180.0,
            default=1.0,
        ),
        "threshold": DiscreteParameterSpec(
            title="Vote Threshold", min_value=1, max_value=100_000, default=50
        ),
        "min_line_length": ContinuousParameterSpec(
            title="Minimum Line Length",
            min_value=0.0,
            max_value=100_000.0,
            default=30.0,
        ),
        "max_line_gap": ContinuousParameterSpec(
            title="Maximum Line Gap",
            min_value=0.0,
            max_value=100_000.0,
            default=10.0,
        ),
        "max_detections": DiscreteParameterSpec(
            title="Maximum Detections",
            min_value=1,
            max_value=10_000,
            default=1_000,
        ),
    },
    outputs=[
        OutputSlotSpec(name="image", kind=OutputKind.IMAGE),
        OutputSlotSpec(name="lines", kind=OutputKind.ARRAY),
    ],
)


HOUGH_CIRCLES_SPEC = OperationSpec(
    name="hough_circles",
    display_name="Hough Circles",
    category=OperationCategory.DETECTION,
    description="Hough gradient 방법으로 원을 검출합니다.",
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
        "dp": ContinuousParameterSpec(
            title="Accumulator Ratio",
            min_value=1.0,
            max_value=10.0,
            default=1.2,
        ),
        "min_distance": ContinuousParameterSpec(
            title="Minimum Center Distance",
            min_value=1.0,
            max_value=100_000.0,
            default=20.0,
        ),
        "canny_threshold": ContinuousParameterSpec(
            title="Canny High Threshold",
            min_value=1.0,
            max_value=1_000.0,
            default=100.0,
        ),
        "accumulator_threshold": ContinuousParameterSpec(
            title="Accumulator Threshold",
            min_value=1.0,
            max_value=1_000.0,
            default=30.0,
        ),
        "min_radius": DiscreteParameterSpec(
            title="Minimum Radius", min_value=0, max_value=8192, default=0
        ),
        "max_radius": DiscreteParameterSpec(
            title="Maximum Radius",
            description="0이면 OpenCV 자동 상한을 사용합니다.",
            min_value=0,
            max_value=8192,
            default=0,
        ),
        "max_detections": DiscreteParameterSpec(
            title="Maximum Detections",
            min_value=1,
            max_value=10_000,
            default=1_000,
        ),
    },
    outputs=[
        OutputSlotSpec(name="image", kind=OutputKind.IMAGE),
        OutputSlotSpec(name="circles", kind=OutputKind.ARRAY),
    ],
)


def hough_lines_p_handler(
    *, inputs: Mapping[str, Any], params: Mapping[str, Any]
) -> OperationOutput:
    import cv2

    image: ImageData = inputs["image"]
    ensure_pixel_budget(
        pixels=image.width * image.height,
        operation="hough_lines_p",
        max_pixels=32_000_000,
    )
    detected = cv2.HoughLinesP(
        image.data,
        params["rho"],
        np.deg2rad(params["theta_degrees"]),
        params["threshold"],
        minLineLength=params["min_line_length"],
        maxLineGap=params["max_line_gap"],
    )
    lines = (
        np.empty((0, 4), dtype=np.int32)
        if detected is None
        else detected.reshape(-1, 4)[: params["max_detections"]]
    )
    annotated = to_bgr(image)
    for x1, y1, x2, y2 in lines:
        cv2.line(
            annotated,
            (int(x1), int(y1)),
            (int(x2), int(y2)),
            (0, 0, 255),
            2,
            cv2.LINE_AA,
        )
    return OperationOutput(
        images={
            "image": as_image(
                annotated,
                source=image,
                color_space=ColorSpace.BGR,
            )
        },
        data={"lines": lines},
    )


def hough_circles_handler(
    *, inputs: Mapping[str, Any], params: Mapping[str, Any]
) -> OperationOutput:
    import cv2

    image: ImageData = inputs["image"]
    ensure_pixel_budget(
        pixels=image.width * image.height,
        operation="hough_circles",
        max_pixels=32_000_000,
    )
    if (
        params["max_radius"] != 0
        and params["min_radius"] > params["max_radius"]
    ):
        raise OperationExecutionError(
            code="invalid_parameter_combination",
            message="min_radius must be <= max_radius when max_radius is set",
            details={
                "min_radius": params["min_radius"],
                "max_radius": params["max_radius"],
            },
        )
    blurred = cv2.medianBlur(image.data, 5)
    detected = cv2.HoughCircles(
        blurred,
        cv2.HOUGH_GRADIENT,
        dp=params["dp"],
        minDist=params["min_distance"],
        param1=params["canny_threshold"],
        param2=params["accumulator_threshold"],
        minRadius=params["min_radius"],
        maxRadius=params["max_radius"],
    )
    circles = (
        np.empty((0, 3), dtype=np.float32)
        if detected is None
        else detected.reshape(-1, 3)[: params["max_detections"]]
    )
    annotated = to_bgr(image)
    for center_x, center_y, radius in circles:
        center = (int(round(center_x)), int(round(center_y)))
        cv2.circle(
            annotated,
            center,
            int(round(radius)),
            (0, 255, 0),
            2,
            cv2.LINE_AA,
        )
        cv2.circle(annotated, center, 2, (0, 0, 255), 3)
    return OperationOutput(
        images={
            "image": as_image(
                annotated,
                source=image,
                color_space=ColorSpace.BGR,
            )
        },
        data={"circles": circles},
    )
