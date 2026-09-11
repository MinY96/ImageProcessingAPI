from __future__ import annotations

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


GAUSSIAN_BLUR_SPEC = OperationSpec(
    name="gaussian_blur",
    display_name="Gaussian Blur",
    category=OperationCategory.FILTERING,
    description="Gaussian kernel을 사용하여 이미지를 평활화합니다.",
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
        "kernel_size": DiscreteParameterSpec(
            title="Kernel Size",
            description="3 이상의 홀수 kernel 크기",
            min_value=3,
            max_value=99,
            step=2,
            default=5,
            order=0,
        ),
        "sigma_x": ContinuousParameterSpec(
            title="Sigma X",
            min_value=0.0,
            max_value=100.0,
            default=0.0,
            order=1,
        ),
        "sigma_y": ContinuousParameterSpec(
            title="Sigma Y",
            min_value=0.0,
            max_value=100.0,
            default=0.0,
            order=2,
        ),
        "border_type": CategoryParameterSpec(
            title="Border Type",
            choices=[
                CategoryChoice(value="default", label="Default"),
                CategoryChoice(value="constant", label="Constant"),
                CategoryChoice(value="replicate", label="Replicate"),
                CategoryChoice(value="reflect", label="Reflect"),
                CategoryChoice(value="reflect_101", label="Reflect 101"),
            ],
            default="default",
            order=3,
        ),
    },
    outputs=[
        OutputSlotSpec(name="image", kind=OutputKind.IMAGE)
    ],
)


def gaussian_blur_handler(
    *,
    inputs: Mapping[str, Any],
    params: Mapping[str, Any],
) -> OperationOutput:
    import cv2

    image: ImageData = inputs["image"]
    kernel_size = params["kernel_size"]
    border_types = {
        "default": cv2.BORDER_DEFAULT,
        "constant": cv2.BORDER_CONSTANT,
        "replicate": cv2.BORDER_REPLICATE,
        "reflect": cv2.BORDER_REFLECT,
        "reflect_101": cv2.BORDER_REFLECT_101,
    }

    blurred = cv2.GaussianBlur(
        src=image.data,
        ksize=(kernel_size, kernel_size),
        sigmaX=params["sigma_x"],
        sigmaY=params["sigma_y"],
        borderType=border_types[params["border_type"]],
    )

    return OperationOutput(
        images={
            "image": ImageData(
                data=blurred,
                color_space=image.color_space,
                name=image.name,
            )
        }
    )
