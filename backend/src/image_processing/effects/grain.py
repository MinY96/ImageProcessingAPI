from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np

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

from ..adjustment.common import color_and_alpha, integer_scale, restore_alpha
from ..common import as_image, ensure_pixel_budget


ADD_GRAIN_SPEC = OperationSpec(
    name="add_grain",
    display_name="Add Film Grain",
    category=OperationCategory.EFFECTS,
    description="seed로 재현 가능한 monochrome/color film grain을 추가합니다.",
    inputs=[
        InputSlotSpec(
            name="image",
            kind=InputKind.IMAGE,
            image_constraint=ImageConstraint(
                allowed_dtypes=[ImageDType.UINT8, ImageDType.UINT16]
            ),
        )
    ],
    parameters={
        "amount": ContinuousParameterSpec(
            title="Amount", min_value=0.0, max_value=1.0, default=0.08
        ),
        "distribution": CategoryParameterSpec(
            title="Distribution",
            choices=[
                CategoryChoice(value="gaussian", label="Gaussian"),
                CategoryChoice(value="uniform", label="Uniform"),
            ],
            default="gaussian",
        ),
        "monochromatic": CategoryParameterSpec(
            title="Monochromatic",
            choices=[
                CategoryChoice(value=True, label="Enabled"),
                CategoryChoice(value=False, label="Disabled"),
            ],
            default=True,
        ),
        "grain_size": DiscreteParameterSpec(
            title="Grain Size", min_value=1, max_value=32, default=1
        ),
        "random_seed": DiscreteParameterSpec(
            title="Random Seed", min_value=0, max_value=2_147_483_647, default=42
        ),
    },
    outputs=[OutputSlotSpec(name="image", kind=OutputKind.IMAGE)],
)


def add_grain_handler(
    *, inputs: Mapping[str, Any], params: Mapping[str, Any]
) -> OperationOutput:
    import cv2

    image: ImageData = inputs["image"]
    ensure_pixel_budget(
        pixels=image.width * image.height,
        operation="add_grain",
        max_pixels=64_000_000,
    )
    scale = integer_scale(image, "add_grain")
    color, alpha = color_and_alpha(image)
    channels = 1 if color.ndim == 2 or params["monochromatic"] else color.shape[2]
    grain_size = params["grain_size"]
    noise_height = (image.height + grain_size - 1) // grain_size
    noise_width = (image.width + grain_size - 1) // grain_size
    shape = (noise_height, noise_width) if channels == 1 else (noise_height, noise_width, channels)
    rng = np.random.default_rng(params["random_seed"])
    if params["distribution"] == "gaussian":
        noise = rng.normal(0.0, 1.0, shape).astype(np.float32)
    else:
        noise = rng.uniform(-np.sqrt(3.0), np.sqrt(3.0), shape).astype(np.float32)
    if grain_size > 1:
        noise = cv2.resize(noise, (image.width, image.height), interpolation=cv2.INTER_NEAREST)
    if color.ndim == 3 and noise.ndim == 2:
        noise = noise[..., None]
    output = color.astype(np.float32) + noise * (params["amount"] * scale)
    output = np.rint(np.clip(output, 0.0, scale)).astype(image.data.dtype)
    return OperationOutput(
        images={"image": as_image(restore_alpha(output, alpha), source=image)}
    )
