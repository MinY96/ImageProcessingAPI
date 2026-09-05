import pytest

from src.schemas import (
    CategoryChoice,
    CategoryParameterSpec,
    ConditionalRequiredConstraint,
    ContinuousParameterSpec,
    DiscreteParameterSpec,
    ExactlyOneGroupConstraint,
    GreaterThanConstraint,
    GreaterThanEqualConstraint,
    InputKind,
    InputSlotSpec,
    LessThanConstraint,
    LessThanEqualConstraint,
    MutuallyExclusiveConstraint,
    OperationCategory,
    OperationSpec,
    OutputKind,
    OutputSlotSpec,
    RequireTogetherConstraint,
    ExecutionRequest,
)
from src.validators import (
    ParameterValidationError,
    ParameterValidator,
)


def make_spec(
    parameters,
    constraints,
) -> OperationSpec:
    return OperationSpec(
        name="test_operation",
        display_name="Test Operation",
        category=OperationCategory.FILTERING,
        inputs=[
            InputSlotSpec(
                name="image",
                kind=InputKind.IMAGE,
            )
        ],
        parameters=parameters,
        constraints=constraints,
        outputs=[
            OutputSlotSpec(
                name="image",
                kind=OutputKind.IMAGE,
            )
        ],
    )


def integer_parameter(
    title: str,
    default: int | None = None,
) -> DiscreteParameterSpec:
    return DiscreteParameterSpec(
        title=title,
        min_value=0,
        max_value=1000,
        default=default,
    )


def test_less_than_uses_resolved_default_values():
    spec = make_spec(
        parameters={
            "low": integer_parameter("Low", default=100),
            "high": integer_parameter("High", default=200),
        },
        constraints=[
            LessThanConstraint(left="low", right="high")
        ],
    )

    result = ParameterValidator.validate_request(
        ExecutionRequest(operation="test_operation"),
        spec,
    )

    assert result.params == {"low": 100, "high": 200}
    assert result.provided_params == set()


@pytest.mark.parametrize(
    ("constraint", "left", "right", "expected_code"),
    [
        (
            LessThanConstraint(left="left", right="right"),
            10,
            10,
            "cross_less_than",
        ),
        (
            LessThanEqualConstraint(left="left", right="right"),
            11,
            10,
            "cross_less_than_equal",
        ),
        (
            GreaterThanConstraint(left="left", right="right"),
            10,
            10,
            "cross_greater_than",
        ),
        (
            GreaterThanEqualConstraint(left="left", right="right"),
            9,
            10,
            "cross_greater_than_equal",
        ),
    ],
)
def test_comparison_constraints_fail(
    constraint,
    left,
    right,
    expected_code,
):
    spec = make_spec(
        parameters={
            "left": integer_parameter("Left"),
            "right": integer_parameter("Right"),
        },
        constraints=[constraint],
    )

    request = ExecutionRequest(
        operation="test_operation",
        params={"left": left, "right": right},
    )

    with pytest.raises(ParameterValidationError) as exc_info:
        ParameterValidator.validate_request(request, spec)

    assert exc_info.value.issues[0].code == expected_code


def test_require_together_uses_only_explicit_parameters():
    spec = make_spec(
        parameters={
            "width": integer_parameter("Width"),
            "height": integer_parameter("Height", default=512),
        },
        constraints=[
            RequireTogetherConstraint(
                parameters=["width", "height"]
            )
        ],
    )

    request = ExecutionRequest(
        operation="test_operation",
        params={"width": 512},
    )

    with pytest.raises(ParameterValidationError) as exc_info:
        ParameterValidator.validate_request(request, spec)

    assert exc_info.value.issues[0].code == "require_together"


def test_mutually_exclusive_rejects_multiple_explicit_parameters():
    spec = make_spec(
        parameters={
            "alpha": integer_parameter("Alpha"),
            "beta": integer_parameter("Beta"),
        },
        constraints=[
            MutuallyExclusiveConstraint(
                parameters=["alpha", "beta"]
            )
        ],
    )

    request = ExecutionRequest(
        operation="test_operation",
        params={"alpha": 1, "beta": 2},
    )

    with pytest.raises(ParameterValidationError) as exc_info:
        ParameterValidator.validate_request(request, spec)

    assert exc_info.value.issues[0].code == "mutually_exclusive"


@pytest.fixture
def resize_spec() -> OperationSpec:
    return make_spec(
        parameters={
            "width": integer_parameter("Width"),
            "height": integer_parameter("Height"),
            "scale_x": ContinuousParameterSpec(
                title="Scale X",
                min_value=0.05,
                max_value=10.0,
            ),
            "scale_y": ContinuousParameterSpec(
                title="Scale Y",
                min_value=0.05,
                max_value=10.0,
            ),
            "interpolation": CategoryParameterSpec(
                title="Interpolation",
                choices=[
                    CategoryChoice(value="linear", label="Linear")
                ],
                default="linear",
            ),
        },
        constraints=[
            ExactlyOneGroupConstraint(
                groups=[
                    ["width", "height"],
                    ["scale_x", "scale_y"],
                ]
            )
        ],
    )


def test_exactly_one_group_accepts_size_mode(resize_spec):
    result = ParameterValidator.validate_request(
        ExecutionRequest(
            operation="test_operation",
            params={"width": 512, "height": 512},
        ),
        resize_spec,
    )

    assert result.params["interpolation"] == "linear"


@pytest.mark.parametrize(
    ("params", "expected_code"),
    [
        ({"width": 512}, "partial_group"),
        ({}, "exactly_one_group"),
        (
            {
                "width": 512,
                "height": 512,
                "scale_x": 0.5,
                "scale_y": 0.5,
            },
            "exactly_one_group",
        ),
    ],
)
def test_exactly_one_group_rejects_invalid_modes(
    resize_spec,
    params,
    expected_code,
):
    with pytest.raises(ParameterValidationError) as exc_info:
        ParameterValidator.validate_request(
            ExecutionRequest(
                operation="test_operation",
                params=params,
            ),
            resize_spec,
        )

    assert exc_info.value.issues[0].code == expected_code


def test_conditional_required_uses_resolved_values():
    spec = make_spec(
        parameters={
            "mode": CategoryParameterSpec(
                title="Mode",
                choices=[
                    CategoryChoice(value="basic", label="Basic"),
                    CategoryChoice(value="advanced", label="Advanced"),
                ],
                default="advanced",
            ),
            "threshold": integer_parameter("Threshold"),
        },
        constraints=[
            ConditionalRequiredConstraint(
                parameter="mode",
                equals="advanced",
                required_parameters=["threshold"],
            )
        ],
    )

    with pytest.raises(ParameterValidationError) as exc_info:
        ParameterValidator.validate_request(
            ExecutionRequest(operation="test_operation"),
            spec,
        )

    assert exc_info.value.issues[0].code == "conditional_required"
