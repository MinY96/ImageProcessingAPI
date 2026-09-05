from __future__ import annotations

from collections.abc import Mapping
from typing import Any

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
    OperationCategory,
    OperationOutput,
    OperationSpec,
    OutputKind,
    OutputSlotSpec,
)

from ..common import as_image, to_bgr


FIND_CONTOURS_SPEC = OperationSpec(
    name="find_contours",
    display_name="Find Contours",
    category=OperationCategory.CONTOUR,
    description="이진 영상에서 contour를 찾고 주요 형상 지표를 계산합니다.",
    inputs=[
        InputSlotSpec(
            name="image",
            kind=InputKind.MASK,
            image_constraint=ImageConstraint(
                allowed_color_spaces=[ColorSpace.GRAY, ColorSpace.BINARY],
                allowed_dtypes=[ImageDType.UINT8],
            ),
        )
    ],
    parameters={
        "retrieval_mode": CategoryParameterSpec(
            title="Retrieval Mode",
            choices=[
                CategoryChoice(value="external", label="External"),
                CategoryChoice(value="list", label="List"),
                CategoryChoice(value="ccomp", label="Two Level"),
                CategoryChoice(value="tree", label="Tree"),
            ],
            default="external",
        ),
        "approximation": CategoryParameterSpec(
            title="Approximation",
            choices=[
                CategoryChoice(value="simple", label="Simple"),
                CategoryChoice(value="none", label="None"),
            ],
            default="simple",
        ),
        "min_area": ContinuousParameterSpec(
            title="Minimum Area",
            unit="pixel^2",
            min_value=0.0,
            max_value=1_000_000_000.0,
            default=0.0,
        ),
        "max_contours": DiscreteParameterSpec(
            title="Maximum Contours",
            min_value=1,
            max_value=10_000,
            default=1_000,
        ),
        "thickness": DiscreteParameterSpec(
            title="Drawing Thickness", min_value=1, max_value=20, default=2
        ),
    },
    outputs=[
        OutputSlotSpec(name="image", kind=OutputKind.IMAGE),
        OutputSlotSpec(name="contours", kind=OutputKind.CONTOURS),
        OutputSlotSpec(name="features", kind=OutputKind.METRICS),
    ],
)


def find_contours_handler(
    *, inputs: Mapping[str, Any], params: Mapping[str, Any]
) -> OperationOutput:
    import cv2

    image: ImageData = inputs["image"]
    retrieval_modes = {
        "external": cv2.RETR_EXTERNAL,
        "list": cv2.RETR_LIST,
        "ccomp": cv2.RETR_CCOMP,
        "tree": cv2.RETR_TREE,
    }
    approximations = {
        "simple": cv2.CHAIN_APPROX_SIMPLE,
        "none": cv2.CHAIN_APPROX_NONE,
    }
    contours, _ = cv2.findContours(
        image.data.copy(),
        retrieval_modes[params["retrieval_mode"]],
        approximations[params["approximation"]],
    )
    selected = [
        contour
        for contour in contours
        if cv2.contourArea(contour) >= params["min_area"]
    ]
    selected.sort(key=cv2.contourArea, reverse=True)
    selected = selected[: params["max_contours"]]

    features = []
    for index, contour in enumerate(selected):
        area = float(cv2.contourArea(contour))
        perimeter = float(cv2.arcLength(contour, True))
        x, y, width, height = cv2.boundingRect(contour)
        moments = cv2.moments(contour)
        centroid = None
        if moments["m00"] != 0:
            centroid = [
                moments["m10"] / moments["m00"],
                moments["m01"] / moments["m00"],
            ]
        features.append(
            {
                "index": index,
                "area": area,
                "perimeter": perimeter,
                "bounding_box": [x, y, width, height],
                "centroid": centroid,
            }
        )

    annotated = to_bgr(image)
    cv2.drawContours(
        annotated,
        selected,
        -1,
        (0, 255, 0),
        params["thickness"],
    )
    compact_contours = [
        contour.reshape(-1, 2)
        for contour in selected
    ]
    return OperationOutput(
        images={
            "image": as_image(
                annotated,
                source=image,
                color_space=ColorSpace.BGR,
            )
        },
        data={"contours": compact_contours, "features": features},
    )
