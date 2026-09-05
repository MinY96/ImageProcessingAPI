import pytest
from pydantic import ValidationError

from src.schemas import (
    DiscreteParameterSpec,
    InputKind,
    InputSlotSpec,
    LessThanConstraint,
    OperationCategory,
    OperationSpec,
    OutputKind,
    OutputSlotSpec,
)


def test_constraint_cannot_reference_unknown_parameter():
    with pytest.raises(ValidationError):
        OperationSpec(
            name="canny",
            display_name="Canny",
            category=OperationCategory.EDGE,
            inputs=[
                InputSlotSpec(name="image", kind=InputKind.IMAGE)
            ],
            parameters={
                "threshold_low": DiscreteParameterSpec(
                    title="Low",
                    min_value=0,
                    max_value=255,
                )
            },
            constraints=[
                LessThanConstraint(
                    left="threshold_low",
                    right="threshold_high",
                )
            ],
            outputs=[
                OutputSlotSpec(name="image", kind=OutputKind.IMAGE)
            ],
        )
