import pytest

from src.schemas import ExecutionRequest
from src.validators.parameter import (
    ParameterValidationError,
    ParameterValidator,
)


def test_gaussian_blur_valid(
    gaussian_blur_spec,
):

    request = ExecutionRequest(
        operation="gaussian_blur",
        params={
            "kernel_size": 7,
            "sigma_x": 1.5,
            "border_type": "reflect",
        },
    )

    result = ParameterValidator.validate_request(
        request,
        gaussian_blur_spec,
    )

    assert result.params["kernel_size"] == 7
    assert result.params["sigma_x"] == 1.5
    assert result.params["sigma_y"] == 0.0
    assert result.provided_params == {
        "kernel_size",
        "sigma_x",
        "border_type",
    }

def test_gaussian_blur_invalid_kernel(
    gaussian_blur_spec,
):

    request = ExecutionRequest(
        operation="gaussian_blur",
        params={
            "kernel_size": 4,
        },
    )

    with pytest.raises(
        ParameterValidationError
    ):
        ParameterValidator.validate_request(
            request,
            gaussian_blur_spec,
        )


def test_reports_all_individual_parameter_issues(
    gaussian_blur_spec,
):
    request = ExecutionRequest(
        operation="gaussian_blur",
        params={
            "kernel_size": 4,
            "sigma_x": 100,
            "border_type": "invalid",
            "unknown": 123,
        },
    )

    with pytest.raises(ParameterValidationError) as exc_info:
        ParameterValidator.validate_request(
            request,
            gaussian_blur_spec,
        )

    error = exc_info.value.to_dict()

    assert error["error"] == "parameter_validation_error"
    assert {
        issue["code"]
        for issue in error["issues"]
    } == {
        "unknown_parameter",
        "invalid_step",
        "above_maximum",
        "invalid_choice",
    }
