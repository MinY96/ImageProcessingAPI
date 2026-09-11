import numpy as np
import pytest

from src.schemas import (
    ColorSpace,
    ImageConstraint,
    ImageDType,
    ImageData,
    InputKind,
    InputSlotSpec,
    OperationCategory,
    OperationSpec,
    OutputKind,
    OutputSlotSpec,
)
from src.validators import InputValidationError, InputValidator


def make_spec() -> OperationSpec:
    return OperationSpec(
        name="gray_operation",
        display_name="Gray Operation",
        category=OperationCategory.FILTERING,
        inputs=[
            InputSlotSpec(
                name="image",
                kind=InputKind.IMAGE,
                image_constraint=ImageConstraint(
                    allowed_color_spaces=[ColorSpace.GRAY],
                    allowed_dtypes=[ImageDType.UINT8],
                    min_width=4,
                    min_height=4,
                ),
            )
        ],
        outputs=[
            OutputSlotSpec(name="image", kind=OutputKind.IMAGE)
        ],
    )


def test_input_validator_accepts_valid_image():
    image = ImageData(
        data=np.zeros((8, 8), dtype=np.uint8),
        color_space=ColorSpace.GRAY,
    )

    result = InputValidator.validate(
        inputs={"image": image},
        operation_spec=make_spec(),
    )

    assert result["image"] is image


@pytest.mark.parametrize(
    ("inputs", "expected_code"),
    [
        ({}, "missing_required_input"),
        ({"image": "not-image"}, "invalid_input_type"),
        (
            {
                "image": ImageData(
                    data=np.zeros((8, 8, 3), dtype=np.uint8),
                    color_space=ColorSpace.BGR,
                )
            },
            "invalid_color_space",
        ),
        (
            {
                "image": ImageData(
                    data=np.zeros((2, 2), dtype=np.uint8),
                    color_space=ColorSpace.GRAY,
                )
            },
            "image_too_narrow",
        ),
    ],
)
def test_input_validator_rejects_invalid_input(
    inputs,
    expected_code,
):
    with pytest.raises(InputValidationError) as exc_info:
        InputValidator.validate(
            inputs=inputs,
            operation_spec=make_spec(),
        )

    assert exc_info.value.issues[0].code == expected_code
