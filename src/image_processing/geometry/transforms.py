from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from src.schemas import (
    CategoryChoice,
    CategoryParameterSpec,
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

from ..common import as_image, ensure_output_size, points_array


_GEOMETRY_IMAGE_INPUT = InputSlotSpec(
    name="image",
    kind=InputKind.IMAGE,
    image_constraint=ImageConstraint(
        allowed_dtypes=[
            ImageDType.UINT8,
            ImageDType.UINT16,
            ImageDType.INT16,
            ImageDType.FLOAT32,
            ImageDType.FLOAT64,
        ]
    ),
)


_INTERPOLATION_PARAMETER = CategoryParameterSpec(
    title="Interpolation",
    choices=[
        CategoryChoice(value="nearest", label="Nearest"),
        CategoryChoice(value="linear", label="Linear"),
        CategoryChoice(value="cubic", label="Cubic"),
    ],
    default="linear",
)


ROTATE_SPEC = OperationSpec(
    name="rotate",
    display_name="Rotate",
    category=OperationCategory.GEOMETRY,
    description="중심을 기준으로 회전하고 필요하면 전체 결과가 보이도록 확장합니다.",
    inputs=[_GEOMETRY_IMAGE_INPUT],
    parameters={
        "angle": ContinuousParameterSpec(
            title="Angle", unit="degree", min_value=-360.0, max_value=360.0, default=0.0
        ),
        "scale": ContinuousParameterSpec(
            title="Scale", min_value=0.01, max_value=10.0, default=1.0
        ),
        "expand": CategoryParameterSpec(
            title="Expand Canvas",
            choices=[
                CategoryChoice(value=False, label="Disabled"),
                CategoryChoice(value=True, label="Enabled"),
            ],
            default=False,
        ),
        "interpolation": _INTERPOLATION_PARAMETER,
    },
    outputs=[OutputSlotSpec(name="image", kind=OutputKind.IMAGE)],
)


FLIP_SPEC = OperationSpec(
    name="flip",
    display_name="Flip",
    category=OperationCategory.GEOMETRY,
    description="이미지를 수평, 수직 또는 양방향으로 뒤집습니다.",
    inputs=[_GEOMETRY_IMAGE_INPUT],
    parameters={
        "direction": CategoryParameterSpec(
            title="Direction",
            choices=[
                CategoryChoice(value="horizontal", label="Horizontal"),
                CategoryChoice(value="vertical", label="Vertical"),
                CategoryChoice(value="both", label="Both"),
            ],
            default="horizontal",
        )
    },
    outputs=[OutputSlotSpec(name="image", kind=OutputKind.IMAGE)],
)


WARP_AFFINE_SPEC = OperationSpec(
    name="warp_affine",
    display_name="Warp Affine",
    category=OperationCategory.GEOMETRY,
    description="세 쌍의 대응점을 이용해 affine 변환을 적용합니다.",
    inputs=[
        _GEOMETRY_IMAGE_INPUT,
        InputSlotSpec(name="source_points", kind=InputKind.POINTS),
        InputSlotSpec(name="destination_points", kind=InputKind.POINTS),
    ],
    parameters={
        "width": DiscreteParameterSpec(
            title="Output Width", min_value=1, max_value=8192, required=True
        ),
        "height": DiscreteParameterSpec(
            title="Output Height", min_value=1, max_value=8192, required=True
        ),
        "interpolation": _INTERPOLATION_PARAMETER,
    },
    outputs=[OutputSlotSpec(name="image", kind=OutputKind.IMAGE)],
)


WARP_PERSPECTIVE_SPEC = OperationSpec(
    name="warp_perspective",
    display_name="Warp Perspective",
    category=OperationCategory.GEOMETRY,
    description="네 쌍의 대응점을 이용해 perspective 변환을 적용합니다.",
    inputs=[
        _GEOMETRY_IMAGE_INPUT,
        InputSlotSpec(name="source_points", kind=InputKind.POINTS),
        InputSlotSpec(name="destination_points", kind=InputKind.POINTS),
    ],
    parameters={
        "width": DiscreteParameterSpec(
            title="Output Width", min_value=1, max_value=8192, required=True
        ),
        "height": DiscreteParameterSpec(
            title="Output Height", min_value=1, max_value=8192, required=True
        ),
        "interpolation": _INTERPOLATION_PARAMETER,
    },
    outputs=[OutputSlotSpec(name="image", kind=OutputKind.IMAGE)],
)


def _interpolation(name: str) -> int:
    import cv2

    return {
        "nearest": cv2.INTER_NEAREST,
        "linear": cv2.INTER_LINEAR,
        "cubic": cv2.INTER_CUBIC,
    }[name]


def rotate_handler(
    *, inputs: Mapping[str, Any], params: Mapping[str, Any]
) -> OperationOutput:
    import cv2

    image: ImageData = inputs["image"]
    center = (image.width / 2.0, image.height / 2.0)
    matrix = cv2.getRotationMatrix2D(
        center, params["angle"], params["scale"]
    )
    width, height = image.width, image.height

    if params["expand"]:
        cosine = abs(matrix[0, 0])
        sine = abs(matrix[0, 1])
        width = math.ceil(image.height * sine + image.width * cosine)
        height = math.ceil(image.height * cosine + image.width * sine)
        matrix[0, 2] += width / 2.0 - center[0]
        matrix[1, 2] += height / 2.0 - center[1]

    ensure_output_size(width=width, height=height, operation="rotate")
    result = cv2.warpAffine(
        image.data,
        matrix,
        (width, height),
        flags=_interpolation(params["interpolation"]),
    )
    return OperationOutput(images={"image": as_image(result, source=image)})


def flip_handler(
    *, inputs: Mapping[str, Any], params: Mapping[str, Any]
) -> OperationOutput:
    import cv2

    image: ImageData = inputs["image"]
    codes = {"horizontal": 1, "vertical": 0, "both": -1}
    result = cv2.flip(image.data, codes[params["direction"]])
    return OperationOutput(images={"image": as_image(result, source=image)})


def warp_affine_handler(
    *, inputs: Mapping[str, Any], params: Mapping[str, Any]
) -> OperationOutput:
    import cv2

    image: ImageData = inputs["image"]
    width, height = params["width"], params["height"]
    ensure_output_size(width=width, height=height, operation="warp_affine")
    source = points_array(
        inputs["source_points"], expected_count=3, input_name="source_points"
    )
    destination = points_array(
        inputs["destination_points"],
        expected_count=3,
        input_name="destination_points",
    )
    matrix = cv2.getAffineTransform(source, destination)
    result = cv2.warpAffine(
        image.data,
        matrix,
        (width, height),
        flags=_interpolation(params["interpolation"]),
    )
    return OperationOutput(images={"image": as_image(result, source=image)})


def warp_perspective_handler(
    *, inputs: Mapping[str, Any], params: Mapping[str, Any]
) -> OperationOutput:
    import cv2

    image: ImageData = inputs["image"]
    width, height = params["width"], params["height"]
    ensure_output_size(
        width=width, height=height, operation="warp_perspective"
    )
    source = points_array(
        inputs["source_points"], expected_count=4, input_name="source_points"
    )
    destination = points_array(
        inputs["destination_points"],
        expected_count=4,
        input_name="destination_points",
    )
    matrix = cv2.getPerspectiveTransform(source, destination)
    result = cv2.warpPerspective(
        image.data,
        matrix,
        (width, height),
        flags=_interpolation(params["interpolation"]),
    )
    return OperationOutput(images={"image": as_image(result, source=image)})
