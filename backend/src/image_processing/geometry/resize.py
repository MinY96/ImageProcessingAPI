from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from src.schemas import (
    CategoryChoice,
    CategoryParameterSpec,
    ContinuousParameterSpec,
    DiscreteParameterSpec,
    ExactlyOneGroupConstraint,
    ImageData,
    ImageConstraint,
    ImageDType,
    InputKind,
    InputSlotSpec,
    OperationCategory,
    OperationOutput,
    OperationSpec,
    OutputKind,
    OutputSlotSpec,
)
from src.registry.errors import OperationExecutionError


MAX_OUTPUT_PIXELS = 64_000_000


RESIZE_SPEC = OperationSpec(
    name="resize",
    display_name="Resize",
    category=OperationCategory.GEOMETRY,
    description="픽셀 크기 또는 배율 중 한 가지 방식으로 크기를 변경합니다.",
    inputs=[
        InputSlotSpec(
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
    ],
    parameters={
        "width": DiscreteParameterSpec(
            title="Width",
            min_value=1,
            max_value=8192,
            order=0,
        ),
        "height": DiscreteParameterSpec(
            title="Height",
            min_value=1,
            max_value=8192,
            order=1,
        ),
        "scale_x": ContinuousParameterSpec(
            title="Scale X",
            min_value=0.01,
            max_value=10.0,
            order=2,
        ),
        "scale_y": ContinuousParameterSpec(
            title="Scale Y",
            min_value=0.01,
            max_value=10.0,
            order=3,
        ),
        "interpolation": CategoryParameterSpec(
            title="Interpolation",
            choices=[
                CategoryChoice(value="nearest", label="Nearest"),
                CategoryChoice(value="linear", label="Linear"),
                CategoryChoice(value="area", label="Area"),
                CategoryChoice(value="cubic", label="Cubic"),
                CategoryChoice(value="lanczos4", label="Lanczos 4"),
            ],
            default="linear",
            order=4,
        ),
    },
    constraints=[
        ExactlyOneGroupConstraint(
            groups=[
                ["width", "height"],
                ["scale_x", "scale_y"],
            ],
            message=(
                "Specify either width/height or scale_x/scale_y."
            ),
        )
    ],
    outputs=[
        OutputSlotSpec(name="image", kind=OutputKind.IMAGE)
    ],
)


def resize_handler(
    *,
    inputs: Mapping[str, Any],
    params: Mapping[str, Any],
) -> OperationOutput:
    import cv2

    image: ImageData = inputs["image"]
    interpolations = {
        "nearest": cv2.INTER_NEAREST,
        "linear": cv2.INTER_LINEAR,
        "area": cv2.INTER_AREA,
        "cubic": cv2.INTER_CUBIC,
        "lanczos4": cv2.INTER_LANCZOS4,
    }

    if "width" in params:
        target_width = params["width"]
        target_height = params["height"]
    else:
        target_width = round(image.width * params["scale_x"])
        target_height = round(image.height * params["scale_y"])

    target_pixels = target_width * target_height

    if target_width < 1 or target_height < 1:
        raise OperationExecutionError(
            code="invalid_output_size",
            message="resize output width and height must be at least 1",
            details={
                "width": target_width,
                "height": target_height,
            },
        )

    if target_pixels > MAX_OUTPUT_PIXELS:
        raise OperationExecutionError(
            code="resource_limit_exceeded",
            message="resize output exceeds the configured pixel limit",
            details={
                "width": target_width,
                "height": target_height,
                "pixels": target_pixels,
                "max_pixels": MAX_OUTPUT_PIXELS,
            },
        )

    if "width" in params:
        resized = cv2.resize(
            src=image.data,
            dsize=(target_width, target_height),
            interpolation=interpolations[params["interpolation"]],
        )
    else:
        resized = cv2.resize(
            src=image.data,
            dsize=(0, 0),
            fx=params["scale_x"],
            fy=params["scale_y"],
            interpolation=interpolations[params["interpolation"]],
        )

    return OperationOutput(
        images={
            "image": ImageData(
                data=resized,
                color_space=image.color_space,
                name=image.name,
            )
        }
    )
