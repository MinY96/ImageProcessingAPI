from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np

from src.schemas import (
    CategoryChoice,
    CategoryParameterSpec,
    ColorSpace,
    ContinuousParameterSpec,
    DiscreteParameterSpec,
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

from ..common import as_image, ensure_pixel_budget, to_bgr
from ..segmentation.kmeans import sampled_kmeans


COLOR_QUANTIZATION_SPEC = OperationSpec(
    name="color_quantization",
    display_name="K-Means Color Quantization",
    category=OperationCategory.COLOR,
    inputs=[
        InputSlotSpec(
            name="image",
            kind=InputKind.IMAGE,
            image_constraint=ImageConstraint(
                allowed_dtypes=[ImageDType.UINT8]
            ),
        )
    ],
    parameters={
        "colors": DiscreteParameterSpec(
            title="Number of Colors", min_value=2, max_value=256, default=8
        ),
        "sample_size": DiscreteParameterSpec(
            title="Training Sample Pixels",
            min_value=1000,
            max_value=1_000_000,
            default=100_000,
        ),
        "max_iterations": DiscreteParameterSpec(
            title="Maximum Iterations", min_value=1, max_value=1000, default=30
        ),
        "epsilon": ContinuousParameterSpec(
            title="Epsilon", min_value=0.0001, max_value=100.0, default=0.5
        ),
        "attempts": DiscreteParameterSpec(
            title="Attempts", min_value=1, max_value=20, default=3
        ),
        "initialization": CategoryParameterSpec(
            title="Initialization",
            choices=[
                CategoryChoice(value="kmeans_pp", label="K-Means++"),
                CategoryChoice(value="random", label="Random"),
            ],
            default="kmeans_pp",
        ),
        "random_seed": DiscreteParameterSpec(
            title="Random Seed", min_value=0, max_value=2_147_483_647, default=42
        ),
    },
    outputs=[
        OutputSlotSpec(name="image", kind=OutputKind.IMAGE),
        OutputSlotSpec(name="centers", kind=OutputKind.ARRAY),
        OutputSlotSpec(name="compactness", kind=OutputKind.SCALAR),
    ],
)


def color_quantization_handler(
    *, inputs: Mapping[str, Any], params: Mapping[str, Any]
) -> OperationOutput:
    image: ImageData = inputs["image"]
    ensure_pixel_budget(
        pixels=image.width * image.height,
        operation="color_quantization",
        max_pixels=16_000_000,
    )
    bgr = to_bgr(image)
    samples = np.asarray(bgr.reshape(-1, 3), dtype=np.float32)
    labels, centers, compactness = sampled_kmeans(
        samples,
        clusters=params["colors"],
        sample_size=params["sample_size"],
        max_iterations=params["max_iterations"],
        epsilon=params["epsilon"],
        attempts=params["attempts"],
        initialization=params["initialization"],
        random_seed=params["random_seed"],
    )
    quantized = np.clip(np.rint(centers[labels]), 0, 255).astype(np.uint8)
    quantized = quantized.reshape(bgr.shape)
    return OperationOutput(
        images={
            "image": as_image(
                quantized,
                source=image,
                color_space=ColorSpace.BGR,
                name="color_quantized",
            )
        },
        data={"centers": centers, "compactness": compactness},
    )
