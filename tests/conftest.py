import pytest

from src.schemas import (
    CategoryChoice,
    CategoryParameterSpec,
    ContinuousParameterSpec,
    DiscreteParameterSpec,
    InputKind,
    InputSlotSpec,
    OperationCategory,
    OperationSpec,
    OutputKind,
    OutputSlotSpec,
)


@pytest.fixture
def gaussian_blur_spec() -> OperationSpec:
    return OperationSpec(
        name="gaussian_blur",
        display_name="Gaussian Blur",
        category=OperationCategory.FILTERING,
        inputs=[
            InputSlotSpec(
                name="image",
                kind=InputKind.IMAGE,
            )
        ],
        parameters={
            "kernel_size": DiscreteParameterSpec(
                title="Kernel Size",
                min_value=3,
                max_value=31,
                step=2,
                default=5,
            ),
            "sigma_x": ContinuousParameterSpec(
                title="Sigma X",
                min_value=0.0,
                max_value=20.0,
                default=0.0,
            ),
            "sigma_y": ContinuousParameterSpec(
                title="Sigma Y",
                min_value=0.0,
                max_value=20.0,
                default=0.0,
            ),
            "border_type": CategoryParameterSpec(
                title="Border Type",
                choices=[
                    CategoryChoice(
                        value="default",
                        label="Default",
                    ),
                    CategoryChoice(
                        value="reflect",
                        label="Reflect",
                    ),
                ],
                default="default",
            ),
        },
        outputs=[
            OutputSlotSpec(
                name="image",
                kind=OutputKind.IMAGE,
            )
        ],
    )
