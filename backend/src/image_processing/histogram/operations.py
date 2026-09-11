from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from src.registry.errors import OperationExecutionError
from src.schemas import (
    CategoryChoice,
    CategoryParameterSpec,
    ColorSpace,
    ContinuousParameterSpec,
    DiscreteParameterSpec,
    ImageConstraint,
    ImageDType,
    ImageData,
    InputKind,
    InputSlotSpec,
    LessThanConstraint,
    OperationCategory,
    OperationOutput,
    OperationSpec,
    OutputKind,
    OutputSlotSpec,
)

from ..common import as_image


HISTOGRAM_SPEC = OperationSpec(
    name="histogram",
    display_name="Calculate Histogram",
    category=OperationCategory.HISTOGRAM,
    description="지정 채널의 히스토그램과 bin edge를 계산합니다.",
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
        "channel": DiscreteParameterSpec(
            title="Channel Index", min_value=0, max_value=3, default=0
        ),
        "bins": DiscreteParameterSpec(
            title="Bins", min_value=2, max_value=1024, default=256
        ),
        "range_start": DiscreteParameterSpec(
            title="Range Start", min_value=0, max_value=255, default=0
        ),
        "range_end": DiscreteParameterSpec(
            title="Range End", min_value=1, max_value=256, default=256
        ),
        "normalize": CategoryParameterSpec(
            title="Normalize",
            choices=[
                CategoryChoice(value=False, label="Disabled"),
                CategoryChoice(value=True, label="L1 Normalize"),
            ],
            default=False,
        ),
    },
    constraints=[
        LessThanConstraint(left="range_start", right="range_end")
    ],
    outputs=[
        OutputSlotSpec(name="histogram", kind=OutputKind.ARRAY),
        OutputSlotSpec(name="bin_edges", kind=OutputKind.ARRAY),
    ],
)


EQUALIZE_HISTOGRAM_SPEC = OperationSpec(
    name="equalize_histogram",
    display_name="Equalize Histogram",
    category=OperationCategory.HISTOGRAM,
    description="단일 채널 uint8 영상에 전역 histogram equalization을 적용합니다.",
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
    outputs=[OutputSlotSpec(name="image", kind=OutputKind.IMAGE)],
)


CLAHE_SPEC = OperationSpec(
    name="clahe",
    display_name="CLAHE",
    category=OperationCategory.HISTOGRAM,
    description="대비 제한 adaptive histogram equalization을 적용합니다.",
    inputs=EQUALIZE_HISTOGRAM_SPEC.inputs,
    parameters={
        "clip_limit": ContinuousParameterSpec(
            title="Clip Limit",
            min_value=0.1,
            max_value=100.0,
            default=2.0,
        ),
        "tile_grid_size": DiscreteParameterSpec(
            title="Tile Grid Size",
            min_value=2,
            max_value=64,
            default=8,
        ),
    },
    outputs=[OutputSlotSpec(name="image", kind=OutputKind.IMAGE)],
)


def histogram_handler(
    *, inputs: Mapping[str, Any], params: Mapping[str, Any]
) -> OperationOutput:
    import cv2
    import numpy as np

    image: ImageData = inputs["image"]
    channel = params["channel"]
    if channel >= image.channels:
        raise OperationExecutionError(
            code="invalid_channel",
            message="histogram channel index exceeds image channels",
            details={"channel": channel, "channels": image.channels},
        )

    histogram = cv2.calcHist(
        [image.data],
        [channel],
        None,
        [params["bins"]],
        [params["range_start"], params["range_end"]],
    ).reshape(-1)
    if params["normalize"]:
        total = float(histogram.sum())
        if total > 0:
            histogram = histogram / total

    bin_edges = np.linspace(
        params["range_start"],
        params["range_end"],
        params["bins"] + 1,
        dtype=np.float32,
    )
    return OperationOutput(
        data={"histogram": histogram, "bin_edges": bin_edges}
    )


def equalize_histogram_handler(
    *, inputs: Mapping[str, Any], params: Mapping[str, Any]
) -> OperationOutput:
    import cv2

    image: ImageData = inputs["image"]
    result = cv2.equalizeHist(image.data)
    return OperationOutput(images={"image": as_image(result, source=image)})


def clahe_handler(
    *, inputs: Mapping[str, Any], params: Mapping[str, Any]
) -> OperationOutput:
    import cv2

    image: ImageData = inputs["image"]
    size = params["tile_grid_size"]
    result = cv2.createCLAHE(
        clipLimit=params["clip_limit"],
        tileGridSize=(size, size),
    ).apply(image.data)
    return OperationOutput(images={"image": as_image(result, source=image)})
