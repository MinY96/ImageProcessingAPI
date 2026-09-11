from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from src.registry.errors import OperationExecutionError
from src.schemas import (
    CategoryChoice,
    CategoryParameterSpec,
    ColorSpace,
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


_MATCH_IMAGE_CONSTRAINT = ImageConstraint(
    allowed_color_spaces=[ColorSpace.GRAY, ColorSpace.BGR],
    allowed_dtypes=[ImageDType.UINT8],
)


TEMPLATE_MATCH_SPEC = OperationSpec(
    name="template_match",
    display_name="Template Matching",
    category=OperationCategory.MATCHING,
    description="입력 영상에서 template와 가장 유사한 위치를 탐색합니다.",
    inputs=[
        InputSlotSpec(
            name="image",
            kind=InputKind.IMAGE,
            image_constraint=_MATCH_IMAGE_CONSTRAINT,
        ),
        InputSlotSpec(
            name="template",
            kind=InputKind.TEMPLATE,
            image_constraint=_MATCH_IMAGE_CONSTRAINT,
        ),
    ],
    parameters={
        "method": CategoryParameterSpec(
            title="Matching Method",
            choices=[
                CategoryChoice(value="sqdiff", label="Squared Difference"),
                CategoryChoice(
                    value="sqdiff_normed",
                    label="Squared Difference Normalized",
                ),
                CategoryChoice(value="ccorr", label="Cross Correlation"),
                CategoryChoice(
                    value="ccorr_normed", label="Cross Correlation Normalized"
                ),
                CategoryChoice(
                    value="ccoeff", label="Correlation Coefficient"
                ),
                CategoryChoice(
                    value="ccoeff_normed",
                    label="Correlation Coefficient Normalized",
                ),
            ],
            default="ccoeff_normed",
        )
    },
    outputs=[
        OutputSlotSpec(name="image", kind=OutputKind.IMAGE),
        OutputSlotSpec(name="response", kind=OutputKind.IMAGE),
        OutputSlotSpec(name="best_match", kind=OutputKind.METRICS),
    ],
)


def template_match_handler(
    *, inputs: Mapping[str, Any], params: Mapping[str, Any]
) -> OperationOutput:
    import cv2

    image: ImageData = inputs["image"]
    template: ImageData = inputs["template"]

    if image.color_space != template.color_space:
        raise OperationExecutionError(
            code="incompatible_inputs",
            message="image and template must use the same color space",
            details={
                "image_color_space": image.color_space.value,
                "template_color_space": template.color_space.value,
            },
        )
    if template.width > image.width or template.height > image.height:
        raise OperationExecutionError(
            code="invalid_template_size",
            message="template must fit inside the source image",
            details={
                "image_size": [image.width, image.height],
                "template_size": [template.width, template.height],
            },
        )

    response_pixels = (
        image.width - template.width + 1
    ) * (
        image.height - template.height + 1
    )
    ensure_pixel_budget(
        pixels=response_pixels,
        operation="template_match",
        max_pixels=16_000_000,
        resource="response",
    )

    methods = {
        "sqdiff": cv2.TM_SQDIFF,
        "sqdiff_normed": cv2.TM_SQDIFF_NORMED,
        "ccorr": cv2.TM_CCORR,
        "ccorr_normed": cv2.TM_CCORR_NORMED,
        "ccoeff": cv2.TM_CCOEFF,
        "ccoeff_normed": cv2.TM_CCOEFF_NORMED,
    }
    method_name = params["method"]
    response = cv2.matchTemplate(
        image.data,
        template.data,
        methods[method_name],
    )
    min_value, max_value, min_location, max_location = cv2.minMaxLoc(response)
    lower_is_better = method_name in {"sqdiff", "sqdiff_normed"}
    location = min_location if lower_is_better else max_location
    score = min_value if lower_is_better else max_value
    bottom_right = (
        location[0] + template.width,
        location[1] + template.height,
    )

    annotated = to_bgr(image)
    cv2.rectangle(annotated, location, bottom_right, (0, 0, 255), 2)
    return OperationOutput(
        images={
            "image": as_image(
                annotated,
                source=image,
                color_space=ColorSpace.BGR,
            ),
            "response": as_image(
                response,
                source=image,
                color_space=ColorSpace.GRAY,
                name="template_match_response",
            ),
        },
        data={
            "best_match": {
                "top_left": list(location),
                "bottom_right": list(bottom_right),
                "score": float(score),
                "lower_is_better": lower_is_better,
                "method": method_name,
            }
        },
    )
