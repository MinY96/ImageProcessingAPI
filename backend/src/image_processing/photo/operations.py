from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np

from src.registry.errors import OperationExecutionError
from src.schemas import (
    CategoryChoice,
    CategoryParameterSpec,
    ColorSpace,
    ContinuousParameterSpec,
    DiscreteParameterSpec,
    GreaterThanConstraint,
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

from ..common import as_image, ensure_pixel_budget, to_bgr


_PHOTO_IMAGE = ImageConstraint(
    allowed_color_spaces=[ColorSpace.BGR, ColorSpace.RGB],
    allowed_dtypes=[ImageDType.UINT8],
)
_PHOTO_MASK = ImageConstraint(
    allowed_color_spaces=[ColorSpace.GRAY, ColorSpace.BINARY],
    allowed_dtypes=[ImageDType.UINT8],
)


def _image_input(name: str = "image") -> InputSlotSpec:
    return InputSlotSpec(name=name, kind=InputKind.IMAGE, image_constraint=_PHOTO_IMAGE)


def _mask_input() -> InputSlotSpec:
    return InputSlotSpec(name="mask", kind=InputKind.MASK, image_constraint=_PHOTO_MASK)


def _sigma_parameters(default_s: float, default_r: float):
    return {
        "sigma_s": ContinuousParameterSpec(
            title="Spatial Sigma", min_value=0.0, max_value=200.0, default=default_s
        ),
        "sigma_r": ContinuousParameterSpec(
            title="Range Sigma", min_value=0.0, max_value=1.0, default=default_r
        ),
    }


EDGE_PRESERVING_FILTER_SPEC = OperationSpec(
    name="edge_preserving_filter",
    display_name="Edge Preserving Filter",
    category=OperationCategory.EFFECTS,
    inputs=[_image_input()],
    parameters={
        "method": CategoryParameterSpec(
            title="Method",
            choices=[
                CategoryChoice(value="recursive", label="Recursive"),
                CategoryChoice(value="normalized", label="Normalized Convolution"),
            ],
            default="recursive",
        ),
        **_sigma_parameters(60.0, 0.4),
    },
    outputs=[OutputSlotSpec(name="image", kind=OutputKind.IMAGE)],
)

DETAIL_ENHANCE_SPEC = OperationSpec(
    name="detail_enhance",
    display_name="Detail Enhance",
    category=OperationCategory.EFFECTS,
    inputs=[_image_input()],
    parameters=_sigma_parameters(10.0, 0.15),
    outputs=[OutputSlotSpec(name="image", kind=OutputKind.IMAGE)],
)

PENCIL_SKETCH_SPEC = OperationSpec(
    name="pencil_sketch",
    display_name="Pencil Sketch",
    category=OperationCategory.EFFECTS,
    inputs=[_image_input()],
    parameters={
        **_sigma_parameters(60.0, 0.07),
        "shade_factor": ContinuousParameterSpec(
            title="Shade Factor", min_value=0.0, max_value=0.1, default=0.02
        ),
    },
    outputs=[
        OutputSlotSpec(name="gray", kind=OutputKind.IMAGE),
        OutputSlotSpec(name="color", kind=OutputKind.IMAGE),
    ],
)

STYLIZATION_SPEC = OperationSpec(
    name="stylization",
    display_name="Stylization",
    category=OperationCategory.EFFECTS,
    inputs=[_image_input()],
    parameters=_sigma_parameters(60.0, 0.45),
    outputs=[OutputSlotSpec(name="image", kind=OutputKind.IMAGE)],
)

COLOR_CHANGE_SPEC = OperationSpec(
    name="color_change",
    display_name="Masked Color Change",
    category=OperationCategory.EFFECTS,
    inputs=[_image_input(), _mask_input()],
    parameters={
        name: ContinuousParameterSpec(
            title=f"{name.title()} Multiplier", min_value=0.5, max_value=2.5, default=1.0
        )
        for name in ("red", "green", "blue")
    },
    outputs=[OutputSlotSpec(name="image", kind=OutputKind.IMAGE)],
)

ILLUMINATION_CHANGE_SPEC = OperationSpec(
    name="illumination_change",
    display_name="Masked Illumination Change",
    category=OperationCategory.EFFECTS,
    inputs=[_image_input(), _mask_input()],
    parameters={
        "alpha": ContinuousParameterSpec(
            title="Alpha", min_value=0.0, max_value=2.0, default=0.2
        ),
        "beta": ContinuousParameterSpec(
            title="Beta", min_value=0.0, max_value=2.0, default=0.4
        ),
    },
    outputs=[OutputSlotSpec(name="image", kind=OutputKind.IMAGE)],
)

TEXTURE_FLATTENING_SPEC = OperationSpec(
    name="texture_flattening",
    display_name="Masked Texture Flattening",
    category=OperationCategory.EFFECTS,
    inputs=[_image_input(), _mask_input()],
    parameters={
        "low_threshold": DiscreteParameterSpec(
            title="Low Threshold", min_value=0, max_value=254, default=30
        ),
        "high_threshold": DiscreteParameterSpec(
            title="High Threshold", min_value=1, max_value=255, default=45
        ),
        "kernel_size": DiscreteParameterSpec(
            title="Kernel Size", values=[3, 5, 7], default=3
        ),
    },
    constraints=[GreaterThanConstraint(left="high_threshold", right="low_threshold")],
    outputs=[OutputSlotSpec(name="image", kind=OutputKind.IMAGE)],
)

SEAMLESS_CLONE_SPEC = OperationSpec(
    name="seamless_clone",
    display_name="Seamless Clone",
    category=OperationCategory.COMPOSITING,
    inputs=[_image_input("source"), _image_input("destination"), _mask_input()],
    parameters={
        "center_x": DiscreteParameterSpec(
            title="Destination Center X", min_value=0, max_value=8192, required=True
        ),
        "center_y": DiscreteParameterSpec(
            title="Destination Center Y", min_value=0, max_value=8192, required=True
        ),
        "mode": CategoryParameterSpec(
            title="Clone Mode",
            choices=[
                CategoryChoice(value=value, label=value.replace("_", " ").title())
                for value in ["normal", "mixed", "monochrome"]
            ],
            default="normal",
        ),
    },
    outputs=[OutputSlotSpec(name="image", kind=OutputKind.IMAGE)],
)


def _validated_mask(mask: ImageData, image: ImageData, operation: str) -> np.ndarray:
    if mask.shape[:2] != image.shape[:2]:
        raise OperationExecutionError(
            code="incompatible_mask_shape",
            message=f"{operation} mask must match its source image",
            details={"image": list(image.shape[:2]), "mask": list(mask.shape[:2])},
        )
    return np.ascontiguousarray(mask.data)


def _output(data: np.ndarray, source: ImageData, name: str | None = None):
    return as_image(data, source=source, color_space=ColorSpace.BGR, name=name)


def _photo_bgr(image: ImageData, operation: str) -> np.ndarray:
    ensure_pixel_budget(
        pixels=image.width * image.height,
        operation=operation,
        max_pixels=16_000_000,
    )
    return to_bgr(image)


def edge_preserving_filter_handler(*, inputs: Mapping[str, Any], params: Mapping[str, Any]):
    import cv2

    image: ImageData = inputs["image"]
    flags = cv2.RECURS_FILTER if params["method"] == "recursive" else cv2.NORMCONV_FILTER
    result = cv2.edgePreservingFilter(
        _photo_bgr(image, "edge_preserving_filter"),
        flags=flags,
        sigma_s=params["sigma_s"],
        sigma_r=params["sigma_r"],
    )
    return OperationOutput(images={"image": _output(result, image)})


def detail_enhance_handler(*, inputs: Mapping[str, Any], params: Mapping[str, Any]):
    import cv2

    image: ImageData = inputs["image"]
    result = cv2.detailEnhance(
        _photo_bgr(image, "detail_enhance"),
        sigma_s=params["sigma_s"],
        sigma_r=params["sigma_r"],
    )
    return OperationOutput(images={"image": _output(result, image)})


def pencil_sketch_handler(*, inputs: Mapping[str, Any], params: Mapping[str, Any]):
    import cv2

    image: ImageData = inputs["image"]
    gray, color = cv2.pencilSketch(
        _photo_bgr(image, "pencil_sketch"),
        sigma_s=params["sigma_s"],
        sigma_r=params["sigma_r"],
        shade_factor=params["shade_factor"],
    )
    return OperationOutput(
        images={
            "gray": as_image(gray, source=image, color_space=ColorSpace.GRAY, name="pencil_gray"),
            "color": _output(color, image, "pencil_color"),
        }
    )


def stylization_handler(*, inputs: Mapping[str, Any], params: Mapping[str, Any]):
    import cv2

    image: ImageData = inputs["image"]
    result = cv2.stylization(
        _photo_bgr(image, "stylization"),
        sigma_s=params["sigma_s"],
        sigma_r=params["sigma_r"],
    )
    return OperationOutput(images={"image": _output(result, image)})


def color_change_handler(*, inputs: Mapping[str, Any], params: Mapping[str, Any]):
    import cv2

    image: ImageData = inputs["image"]
    mask = _validated_mask(inputs["mask"], image, "color_change")
    result = cv2.colorChange(
        _photo_bgr(image, "color_change"),
        mask,
        red_mul=params["red"],
        green_mul=params["green"],
        blue_mul=params["blue"],
    )
    return OperationOutput(images={"image": _output(result, image)})


def illumination_change_handler(*, inputs: Mapping[str, Any], params: Mapping[str, Any]):
    import cv2

    image: ImageData = inputs["image"]
    mask = _validated_mask(inputs["mask"], image, "illumination_change")
    result = cv2.illuminationChange(
        _photo_bgr(image, "illumination_change"),
        mask,
        alpha=params["alpha"],
        beta=params["beta"],
    )
    return OperationOutput(images={"image": _output(result, image)})


def texture_flattening_handler(*, inputs: Mapping[str, Any], params: Mapping[str, Any]):
    import cv2

    image: ImageData = inputs["image"]
    mask = _validated_mask(inputs["mask"], image, "texture_flattening")
    result = cv2.textureFlattening(
        _photo_bgr(image, "texture_flattening"),
        mask,
        low_threshold=params["low_threshold"],
        high_threshold=params["high_threshold"],
        kernel_size=params["kernel_size"],
    )
    return OperationOutput(images={"image": _output(result, image)})


def seamless_clone_handler(*, inputs: Mapping[str, Any], params: Mapping[str, Any]):
    import cv2

    source: ImageData = inputs["source"]
    destination: ImageData = inputs["destination"]
    mask = _validated_mask(inputs["mask"], source, "seamless_clone")
    center = (params["center_x"], params["center_y"])
    if not (0 <= center[0] < destination.width and 0 <= center[1] < destination.height):
        raise OperationExecutionError(
            code="invalid_clone_center",
            message="clone center must be inside destination image",
            details={"center": list(center), "destination": [destination.width, destination.height]},
        )
    modes = {
        "normal": cv2.NORMAL_CLONE,
        "mixed": cv2.MIXED_CLONE,
        "monochrome": cv2.MONOCHROME_TRANSFER,
    }
    ensure_pixel_budget(
        pixels=source.width * source.height + destination.width * destination.height,
        operation="seamless_clone",
        max_pixels=32_000_000,
    )
    try:
        result = cv2.seamlessClone(
            to_bgr(source), to_bgr(destination), mask, center, modes[params["mode"]]
        )
    except cv2.error as exc:
        raise OperationExecutionError(
            code="seamless_clone_failed",
            message="source/mask extent must fit around center in destination",
        ) from exc
    return OperationOutput(images={"image": _output(result, destination)})
