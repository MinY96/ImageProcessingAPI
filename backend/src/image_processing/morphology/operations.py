from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from src.schemas import (
    CategoryChoice,
    CategoryParameterSpec,
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


MORPHOLOGY_SPEC = OperationSpec(
    name="morphology",
    display_name="Morphological Transform",
    category=OperationCategory.MORPHOLOGY,
    description=(
        "Erosion, dilation, opening, closing 및 morphology 기반 차영상을 "
        "계산합니다."
    ),
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
        "operation": CategoryParameterSpec(
            title="Operation",
            choices=[
                CategoryChoice(value="erode", label="Erode"),
                CategoryChoice(value="dilate", label="Dilate"),
                CategoryChoice(value="open", label="Open"),
                CategoryChoice(value="close", label="Close"),
                CategoryChoice(value="gradient", label="Gradient"),
                CategoryChoice(value="tophat", label="Top Hat"),
                CategoryChoice(value="blackhat", label="Black Hat"),
            ],
            default="open",
        ),
        "kernel_shape": CategoryParameterSpec(
            title="Kernel Shape",
            choices=[
                CategoryChoice(value="rect", label="Rectangle"),
                CategoryChoice(value="ellipse", label="Ellipse"),
                CategoryChoice(value="cross", label="Cross"),
            ],
            default="rect",
        ),
        "kernel_size": DiscreteParameterSpec(
            title="Kernel Size",
            min_value=1,
            max_value=99,
            step=2,
            default=3,
        ),
        "iterations": DiscreteParameterSpec(
            title="Iterations", min_value=1, max_value=20, default=1
        ),
    },
    outputs=[OutputSlotSpec(name="image", kind=OutputKind.IMAGE)],
)


def morphology_handler(
    *, inputs: Mapping[str, Any], params: Mapping[str, Any]
) -> OperationOutput:
    import cv2

    image: ImageData = inputs["image"]
    shapes = {
        "rect": cv2.MORPH_RECT,
        "ellipse": cv2.MORPH_ELLIPSE,
        "cross": cv2.MORPH_CROSS,
    }
    operations = {
        "open": cv2.MORPH_OPEN,
        "close": cv2.MORPH_CLOSE,
        "gradient": cv2.MORPH_GRADIENT,
        "tophat": cv2.MORPH_TOPHAT,
        "blackhat": cv2.MORPH_BLACKHAT,
    }
    size = params["kernel_size"]
    kernel = cv2.getStructuringElement(
        shapes[params["kernel_shape"]], (size, size)
    )

    if params["operation"] == "erode":
        result = cv2.erode(
            image.data,
            kernel,
            iterations=params["iterations"],
        )
    elif params["operation"] == "dilate":
        result = cv2.dilate(
            image.data,
            kernel,
            iterations=params["iterations"],
        )
    else:
        result = cv2.morphologyEx(
            image.data,
            operations[params["operation"]],
            kernel,
            iterations=params["iterations"],
        )

    return OperationOutput(images={"image": as_image(result, source=image)})
