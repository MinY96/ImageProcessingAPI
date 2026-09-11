from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np

from src.schemas import (
    ColorSpace,
    ImageConstraint,
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


DFT_SPECTRUM_SPEC = OperationSpec(
    name="dft_spectrum",
    display_name="DFT Magnitude Spectrum",
    category=OperationCategory.TRANSFORM,
    description="2D discrete Fourier transform의 중앙 정렬 magnitude spectrum을 만듭니다.",
    inputs=[
        InputSlotSpec(
            name="image",
            kind=InputKind.IMAGE,
            image_constraint=ImageConstraint(
                allowed_color_spaces=[ColorSpace.GRAY]
            ),
        )
    ],
    outputs=[OutputSlotSpec(name="image", kind=OutputKind.IMAGE)],
)


def dft_spectrum_handler(
    *, inputs: Mapping[str, Any], params: Mapping[str, Any]
) -> OperationOutput:
    import cv2

    image: ImageData = inputs["image"]
    ensure_pixel_budget(
        pixels=image.width * image.height,
        operation="dft_spectrum",
        max_pixels=16_000_000,
    )
    transformed = np.fft.fft2(image.data.astype(np.float32, copy=False))
    shifted = np.fft.fftshift(transformed)
    magnitude = np.log1p(np.abs(shifted))
    normalized = cv2.normalize(
        magnitude,
        None,
        0,
        255,
        cv2.NORM_MINMAX,
        dtype=cv2.CV_8U,
    )
    return OperationOutput(
        images={
            "image": as_image(
                normalized,
                source=image,
                color_space=ColorSpace.GRAY,
            )
        }
    )
