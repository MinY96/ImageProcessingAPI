from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from src.registry.errors import OperationExecutionError
from src.schemas import (
    ColorSpace,
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


DRAW_ANNOTATIONS_SPEC = OperationSpec(
    name="draw_annotations",
    display_name="Draw Annotations",
    category=OperationCategory.ANNOTATION,
    description=(
        "선, 사각형, 원, 타원, polyline과 텍스트를 입력 영상의 복사본에 그립니다."
    ),
    inputs=[
        InputSlotSpec(name="image", kind=InputKind.IMAGE),
        InputSlotSpec(
            name="annotations",
            kind=InputKind.ARRAY,
            description="annotation dictionary 목록",
        ),
    ],
    outputs=[OutputSlotSpec(name="image", kind=OutputKind.IMAGE)],
)


def _fail(index: int, message: str) -> OperationExecutionError:
    return OperationExecutionError(
        code="invalid_annotation",
        message=f"annotations[{index}]: {message}",
        details={"index": index},
    )


def _point(value: Any, *, index: int, name: str) -> tuple[int, int]:
    try:
        values = list(value)
    except TypeError as exc:
        raise _fail(index, f"{name} must be [x, y]") from exc
    if len(values) != 2 or any(isinstance(item, bool) for item in values):
        raise _fail(index, f"{name} must be [x, y]")
    try:
        return int(values[0]), int(values[1])
    except (TypeError, ValueError) as exc:
        raise _fail(index, f"{name} coordinates must be integers") from exc


def _color(value: Any, *, index: int) -> tuple[int, int, int]:
    if value is None:
        return 0, 0, 255
    try:
        values = tuple(int(item) for item in value)
    except (TypeError, ValueError) as exc:
        raise _fail(index, "color must be a BGR triplet") from exc
    if len(values) != 3 or any(item < 0 or item > 255 for item in values):
        raise _fail(index, "color values must be three integers in [0, 255]")
    return values


def _integer(
    item: Mapping[str, Any],
    name: str,
    *,
    index: int,
    default: int | None = None,
    minimum: int | None = None,
) -> int:
    value = item.get(name, default)
    if value is None or isinstance(value, bool):
        raise _fail(index, f"{name} is required")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise _fail(index, f"{name} must be an integer") from exc
    if minimum is not None and result < minimum:
        raise _fail(index, f"{name} must be >= {minimum}")
    return result


def draw_annotations_handler(
    *, inputs: Mapping[str, Any], params: Mapping[str, Any]
) -> OperationOutput:
    import cv2

    image: ImageData = inputs["image"]
    annotations = inputs["annotations"]
    if not isinstance(annotations, (list, tuple, np.ndarray)):
        raise OperationExecutionError(
            code="invalid_annotations",
            message="annotations must be a sequence",
        )
    if len(annotations) > 10_000:
        raise OperationExecutionError(
            code="resource_limit_exceeded",
            message="draw_annotations accepts at most 10000 items",
            details={"provided": len(annotations), "maximum": 10_000},
        )

    ensure_pixel_budget(
        pixels=image.width * image.height,
        operation="draw_annotations",
        max_pixels=64_000_000,
    )
    output = to_bgr(image)
    line_types = {"8": cv2.LINE_8, "4": cv2.LINE_4, "aa": cv2.LINE_AA}
    fonts = {
        "simplex": cv2.FONT_HERSHEY_SIMPLEX,
        "plain": cv2.FONT_HERSHEY_PLAIN,
        "duplex": cv2.FONT_HERSHEY_DUPLEX,
        "complex": cv2.FONT_HERSHEY_COMPLEX,
    }

    for index, raw in enumerate(annotations):
        if not isinstance(raw, Mapping):
            raise _fail(index, "item must be an object")
        item = dict(raw)
        kind = item.get("type")
        if not isinstance(kind, str):
            raise _fail(index, "type is required")
        color = _color(item.get("color"), index=index)
        thickness = _integer(item, "thickness", index=index, default=2, minimum=-1)
        line_type_name = str(item.get("line_type", "aa")).lower()
        if line_type_name not in line_types:
            raise _fail(index, "line_type must be one of ['4', '8', 'aa']")
        line_type = line_types[line_type_name]

        if kind == "line":
            if thickness < 1:
                raise _fail(index, "line thickness must be >= 1")
            cv2.line(
                output,
                _point(item.get("start"), index=index, name="start"),
                _point(item.get("end"), index=index, name="end"),
                color,
                thickness,
                line_type,
            )
        elif kind == "rectangle":
            cv2.rectangle(
                output,
                _point(item.get("top_left"), index=index, name="top_left"),
                _point(item.get("bottom_right"), index=index, name="bottom_right"),
                color,
                thickness,
                line_type,
            )
        elif kind == "circle":
            cv2.circle(
                output,
                _point(item.get("center"), index=index, name="center"),
                _integer(item, "radius", index=index, minimum=1),
                color,
                thickness,
                line_type,
            )
        elif kind == "ellipse":
            cv2.ellipse(
                output,
                _point(item.get("center"), index=index, name="center"),
                _point(item.get("axes"), index=index, name="axes"),
                float(item.get("angle", 0.0)),
                float(item.get("start_angle", 0.0)),
                float(item.get("end_angle", 360.0)),
                color,
                thickness,
                line_type,
            )
        elif kind == "polyline":
            if thickness < 1:
                raise _fail(index, "polyline thickness must be >= 1")
            points = np.asarray(item.get("points"), dtype=np.int32)
            if points.ndim != 2 or points.shape[0] < 2 or points.shape[1] != 2:
                raise _fail(index, "points must have shape (N, 2), N >= 2")
            cv2.polylines(
                output,
                [points.reshape(-1, 1, 2)],
                bool(item.get("closed", True)),
                color,
                thickness,
                line_type,
            )
        elif kind == "text":
            if thickness < 1:
                raise _fail(index, "text thickness must be >= 1")
            text = item.get("text")
            if not isinstance(text, str) or not text:
                raise _fail(index, "text must be a non-empty string")
            font_name = str(item.get("font", "simplex")).lower()
            if font_name not in fonts:
                raise _fail(index, f"font must be one of {sorted(fonts)}")
            cv2.putText(
                output,
                text,
                _point(item.get("origin"), index=index, name="origin"),
                fonts[font_name],
                float(item.get("font_scale", 1.0)),
                color,
                thickness,
                line_type,
            )
        else:
            raise _fail(
                index,
                "type must be line, rectangle, circle, ellipse, polyline, or text",
            )

    return OperationOutput(
        images={
            "image": as_image(output, source=image, color_space=ColorSpace.BGR)
        }
    )
