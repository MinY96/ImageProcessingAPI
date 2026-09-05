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

from ..common import as_image, ensure_pixel_budget
from .common import dtype_scale, mask_values, validate_pair


_INTEGER_IMAGES = ImageConstraint(
    allowed_dtypes=[ImageDType.UINT8, ImageDType.UINT16]
)


IMAGE_ARITHMETIC_SPEC = OperationSpec(
    name="image_arithmetic",
    display_name="Image Arithmetic",
    category=OperationCategory.COMPOSITING,
    description="동일 규격 이미지의 산술 연산을 normalized float32로 수행합니다.",
    inputs=[
        InputSlotSpec(name="image1", kind=InputKind.IMAGE, image_constraint=_INTEGER_IMAGES),
        InputSlotSpec(name="image2", kind=InputKind.IMAGE, image_constraint=_INTEGER_IMAGES),
    ],
    parameters={
        "operation": CategoryParameterSpec(
            title="Operation",
            choices=[
                CategoryChoice(value=value, label=value.replace("_", " ").title())
                for value in [
                    "add",
                    "subtract",
                    "absolute_difference",
                    "multiply",
                    "divide",
                    "minimum",
                    "maximum",
                ]
            ],
            default="subtract",
        ),
        "scale": ContinuousParameterSpec(
            title="Scale", min_value=0.0, max_value=100.0, default=1.0
        ),
        "offset": ContinuousParameterSpec(
            title="Normalized Offset", min_value=-10.0, max_value=10.0, default=0.0
        ),
        "epsilon": ContinuousParameterSpec(
            title="Division Epsilon", min_value=1e-8, max_value=1.0, default=1e-6
        ),
    },
    outputs=[OutputSlotSpec(name="image", kind=OutputKind.IMAGE)],
)


WEIGHTED_SUM_SPEC = OperationSpec(
    name="weighted_sum",
    display_name="Weighted Sum",
    category=OperationCategory.COMPOSITING,
    description="alpha*image1 + beta*image2 + gamma를 포화 연산합니다.",
    inputs=[
        InputSlotSpec(name="image1", kind=InputKind.IMAGE, image_constraint=_INTEGER_IMAGES),
        InputSlotSpec(name="image2", kind=InputKind.IMAGE, image_constraint=_INTEGER_IMAGES),
    ],
    parameters={
        "alpha": ContinuousParameterSpec(
            title="First Weight", min_value=-10.0, max_value=10.0, default=0.5
        ),
        "beta": ContinuousParameterSpec(
            title="Second Weight", min_value=-10.0, max_value=10.0, default=0.5
        ),
        "gamma": ContinuousParameterSpec(
            title="Normalized Bias", min_value=-10.0, max_value=10.0, default=0.0
        ),
    },
    outputs=[OutputSlotSpec(name="image", kind=OutputKind.IMAGE)],
)


BITWISE_OPERATION_SPEC = OperationSpec(
    name="bitwise_operation",
    display_name="Bitwise Operation",
    category=OperationCategory.COMPOSITING,
    description="AND/OR/XOR/NOT와 NAND/NOR/XNOR를 선택적 mask와 함께 수행합니다.",
    inputs=[
        InputSlotSpec(name="image1", kind=InputKind.IMAGE, image_constraint=_INTEGER_IMAGES),
        InputSlotSpec(
            name="image2", kind=InputKind.IMAGE, required=False, image_constraint=_INTEGER_IMAGES
        ),
        InputSlotSpec(
            name="mask", kind=InputKind.MASK, required=False, image_constraint=_INTEGER_IMAGES
        ),
    ],
    parameters={
        "operation": CategoryParameterSpec(
            title="Operation",
            choices=[
                CategoryChoice(value=value, label=value.upper())
                for value in ["and", "or", "xor", "not", "nand", "nor", "xnor"]
            ],
            default="and",
        )
    },
    outputs=[OutputSlotSpec(name="image", kind=OutputKind.IMAGE)],
)


def image_arithmetic_handler(
    *, inputs: Mapping[str, Any], params: Mapping[str, Any]
) -> OperationOutput:
    first: ImageData = inputs["image1"]
    second: ImageData = inputs["image2"]
    validate_pair(first, second, "image_arithmetic")
    ensure_pixel_budget(
        pixels=first.width * first.height,
        operation="image_arithmetic",
        max_pixels=32_000_000,
    )
    maximum = dtype_scale(first, "image_arithmetic")
    a = first.data.astype(np.float32) / maximum
    b = second.data.astype(np.float32) / maximum
    mode = params["operation"]
    if mode == "add":
        result = a + b
    elif mode == "subtract":
        result = a - b
    elif mode == "absolute_difference":
        result = np.abs(a - b)
    elif mode == "multiply":
        result = a * b
    elif mode == "divide":
        result = a / np.maximum(np.abs(b), params["epsilon"])
    elif mode == "minimum":
        result = np.minimum(a, b)
    else:
        result = np.maximum(a, b)
    result = result * params["scale"] + params["offset"]
    output = np.rint(np.clip(result, 0.0, 1.0) * maximum).astype(first.data.dtype)
    return OperationOutput(images={"image": as_image(output, source=first)})


def weighted_sum_handler(
    *, inputs: Mapping[str, Any], params: Mapping[str, Any]
) -> OperationOutput:
    first: ImageData = inputs["image1"]
    second: ImageData = inputs["image2"]
    validate_pair(first, second, "weighted_sum")
    maximum = dtype_scale(first, "weighted_sum")
    output = first.data.astype(np.float32) * params["alpha"]
    output += second.data.astype(np.float32) * params["beta"]
    output += params["gamma"] * maximum
    result = np.rint(np.clip(output, 0.0, maximum)).astype(first.data.dtype)
    return OperationOutput(images={"image": as_image(result, source=first)})


def bitwise_operation_handler(
    *, inputs: Mapping[str, Any], params: Mapping[str, Any]
) -> OperationOutput:
    first: ImageData = inputs["image1"]
    mode = params["operation"]
    second = inputs.get("image2")
    if mode != "not" and second is None:
        raise OperationExecutionError(
            code="missing_second_image",
            message=f"bitwise {mode} requires image2",
        )
    if second is not None:
        validate_pair(first, second, "bitwise_operation")
    a = first.data
    if mode == "not":
        result = np.bitwise_not(a)
    else:
        b = second.data
        if mode in {"and", "nand"}:
            result = np.bitwise_and(a, b)
        elif mode in {"or", "nor"}:
            result = np.bitwise_or(a, b)
        else:
            result = np.bitwise_xor(a, b)
        if mode in {"nand", "nor", "xnor"}:
            result = np.bitwise_not(result)
    mask = inputs.get("mask")
    if mask is not None:
        selected = mask_values(mask, first.shape, "bitwise_operation") > 0
        result = np.where(selected, result, np.zeros((), dtype=result.dtype))
    return OperationOutput(images={"image": as_image(result, source=first)})
