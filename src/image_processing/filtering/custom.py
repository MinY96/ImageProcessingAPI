from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np

from src.registry.errors import OperationExecutionError
from src.schemas import (
    CategoryChoice,
    CategoryParameterSpec,
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

from ..common import as_image


FILTER_2D_SPEC = OperationSpec(
    name="filter_2d",
    display_name="Custom 2D Filter",
    category=OperationCategory.FILTERING,
    description="JSON/ndarray로 전달한 2D kernel을 사용해 convolution을 수행합니다.",
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
        ),
        InputSlotSpec(name="kernel", kind=InputKind.ARRAY),
    ],
    parameters={
        "delta": ContinuousParameterSpec(
            title="Delta",
            min_value=-100_000.0,
            max_value=100_000.0,
            default=0.0,
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
        ),
    },
    outputs=[OutputSlotSpec(name="image", kind=OutputKind.IMAGE)],
)


def filter_2d_handler(
    *, inputs: Mapping[str, Any], params: Mapping[str, Any]
) -> OperationOutput:
    import cv2

    image: ImageData = inputs["image"]
    try:
        kernel = np.asarray(inputs["kernel"], dtype=np.float32)
    except (TypeError, ValueError) as exc:
        raise OperationExecutionError(
            code="invalid_kernel",
            message="kernel must contain numeric values",
        ) from exc

    if (
        kernel.ndim != 2
        or kernel.size == 0
        or kernel.shape[0] > 31
        or kernel.shape[1] > 31
        or kernel.shape[0] % 2 == 0
        or kernel.shape[1] % 2 == 0
    ):
        raise OperationExecutionError(
            code="invalid_kernel",
            message="kernel must be a non-empty odd 2D array up to 31x31",
            details={"shape": list(kernel.shape)},
        )
    if not np.isfinite(kernel).all():
        raise OperationExecutionError(
            code="invalid_kernel",
            message="kernel values must be finite",
        )

    borders = {
        "default": cv2.BORDER_DEFAULT,
        "constant": cv2.BORDER_CONSTANT,
        "replicate": cv2.BORDER_REPLICATE,
        "reflect": cv2.BORDER_REFLECT,
        "reflect_101": cv2.BORDER_REFLECT_101,
    }
    result = cv2.filter2D(
        image.data,
        ddepth=-1,
        kernel=kernel,
        delta=params["delta"],
        borderType=borders[params["border_type"]],
    )
    return OperationOutput(images={"image": as_image(result, source=image)})
