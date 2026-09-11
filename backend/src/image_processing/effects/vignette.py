from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np

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

from ..adjustment.common import color_and_alpha, integer_scale, restore_alpha
from ..common import as_image, ensure_pixel_budget


VIGNETTE_SPEC = OperationSpec(
    name="vignette",
    display_name="Vignette",
    category=OperationCategory.EFFECTS,
    description="중심과 반경을 지정하는 부드러운 radial vignette를 적용합니다.",
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
        "strength": ContinuousParameterSpec(
            title="Strength", min_value=0.0, max_value=1.0, default=0.5
        ),
        "radius": ContinuousParameterSpec(
            title="Radius", min_value=0.05, max_value=2.0, default=0.9
        ),
        "softness": ContinuousParameterSpec(
            title="Softness", min_value=0.01, max_value=1.0, default=0.5
        ),
        "center_x": ContinuousParameterSpec(
            title="Center X", min_value=0.0, max_value=1.0, default=0.5
        ),
        "center_y": ContinuousParameterSpec(
            title="Center Y", min_value=0.0, max_value=1.0, default=0.5
        ),
        "shape": CategoryParameterSpec(
            title="Shape",
            choices=[
                CategoryChoice(value="ellipse", label="Ellipse"),
                CategoryChoice(value="circle", label="Circle"),
            ],
            default="ellipse",
        ),
    },
    outputs=[OutputSlotSpec(name="image", kind=OutputKind.IMAGE)],
)


def _smoothstep(edge0: float, edge1: float, value: np.ndarray) -> np.ndarray:
    scaled = np.clip((value - edge0) / max(edge1 - edge0, 1e-6), 0.0, 1.0)
    return scaled * scaled * (3.0 - 2.0 * scaled)


def vignette_handler(
    *, inputs: Mapping[str, Any], params: Mapping[str, Any]
) -> OperationOutput:
    image: ImageData = inputs["image"]
    ensure_pixel_budget(
        pixels=image.width * image.height,
        operation="vignette",
        max_pixels=64_000_000,
    )
    scale = integer_scale(image, "vignette")
    color, alpha = color_and_alpha(image)
    y, x = np.ogrid[: image.height, : image.width]
    center_x = params["center_x"] * max(1, image.width - 1)
    center_y = params["center_y"] * max(1, image.height - 1)
    if params["shape"] == "circle":
        denominator = params["radius"] * max(image.width, image.height) * 0.5
        distance = np.sqrt((x - center_x) ** 2 + (y - center_y) ** 2) / denominator
    else:
        dx = (x - center_x) / (params["radius"] * max(1, image.width) * 0.5)
        dy = (y - center_y) / (params["radius"] * max(1, image.height) * 0.5)
        distance = np.sqrt(dx * dx + dy * dy)
    fade = _smoothstep(1.0 - params["softness"], 1.0, distance)
    factor = 1.0 - params["strength"] * fade
    if color.ndim == 3:
        factor = factor[..., None]
    output_color = np.rint(color.astype(np.float32) * factor)
    output_color = np.clip(output_color, 0.0, scale).astype(image.data.dtype)
    return OperationOutput(
        images={"image": as_image(restore_alpha(output_color, alpha), source=image)}
    )
