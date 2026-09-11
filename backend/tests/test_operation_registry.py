from collections.abc import Mapping
from typing import Any

import numpy as np
import pytest

from src.registry import (
    DuplicateOperationError,
    OperationRegistry,
)
from src.schemas import (
    ColorSpace,
    DiscreteParameterSpec,
    ImageData,
    InputKind,
    InputSlotSpec,
    OperationCategory,
    OperationOutput,
    OperationSpec,
    OutputKind,
    OutputSlotSpec,
)


def make_spec() -> OperationSpec:
    return OperationSpec(
        name="identity",
        display_name="Identity",
        category=OperationCategory.FILTERING,
        inputs=[
            InputSlotSpec(name="image", kind=InputKind.IMAGE)
        ],
        parameters={
            "iterations": DiscreteParameterSpec(
                title="Iterations",
                min_value=1,
                max_value=10,
                default=1,
            )
        },
        outputs=[
            OutputSlotSpec(name="image", kind=OutputKind.IMAGE)
        ],
    )


def identity_handler(
    *,
    inputs: Mapping[str, Any],
    params: Mapping[str, Any],
) -> OperationOutput:
    assert params["iterations"] >= 1
    return OperationOutput(images={"image": inputs["image"]})


@pytest.fixture
def image() -> ImageData:
    return ImageData(
        data=np.arange(64, dtype=np.uint8).reshape(8, 8),
        color_space=ColorSpace.GRAY,
    )


def test_register_list_and_execute(image):
    registry = OperationRegistry()
    registry.register(spec=make_spec(), handler=identity_handler)

    result = registry.execute(
        operation="identity",
        inputs={"image": image},
        params={},
    )

    assert registry.contains("identity")
    assert [spec.name for spec in registry.list_specs()] == ["identity"]
    assert result.success is True
    assert result.output.images["image"] is image
    assert result.metadata.duration_ms >= 0
    assert registry.revision == 1


def test_registry_stores_defensive_spec_copy():
    registry = OperationRegistry()
    spec = make_spec()
    registry.register(spec=spec, handler=identity_handler)

    spec.display_name = "Changed Outside"
    returned = registry.get_spec("identity")
    returned.display_name = "Changed Returned Copy"

    assert registry.get_spec("identity").display_name == "Identity"


def test_duplicate_registration_is_rejected():
    registry = OperationRegistry()
    registry.register(spec=make_spec(), handler=identity_handler)

    with pytest.raises(DuplicateOperationError):
        registry.register(spec=make_spec(), handler=identity_handler)


def test_decorator_registration(image):
    registry = OperationRegistry()

    @registry.operation(make_spec())
    def decorated_handler(
        *,
        inputs: Mapping[str, Any],
        params: Mapping[str, Any],
    ) -> OperationOutput:
        return OperationOutput(images={"image": inputs["image"]})

    result = registry.execute(
        operation="identity",
        inputs={"image": image},
    )

    assert decorated_handler is not None
    assert result.success is True


def test_unknown_operation_returns_failure():
    result = OperationRegistry().execute(operation="missing")

    assert result.success is False
    assert result.error is not None
    assert result.error.code == "operation_not_found"


def test_input_validation_failure_is_result():
    registry = OperationRegistry()
    registry.register(spec=make_spec(), handler=identity_handler)

    result = registry.execute(operation="identity", inputs={})

    assert result.success is False
    assert result.error is not None
    assert result.error.code == "input_validation_error"
    assert result.error.details["issues"][0]["code"] == (
        "missing_required_input"
    )


def test_parameter_validation_failure_is_result(image):
    registry = OperationRegistry()
    registry.register(spec=make_spec(), handler=identity_handler)

    result = registry.execute(
        operation="identity",
        inputs={"image": image},
        params={"iterations": 100},
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.code == "parameter_validation_error"
    assert result.error.details["issues"][0]["code"] == "above_maximum"


def test_handler_exception_is_result(image):
    registry = OperationRegistry()

    def failing_handler(**kwargs):
        raise RuntimeError("intentional failure")

    registry.register(spec=make_spec(), handler=failing_handler)
    result = registry.execute(
        operation="identity",
        inputs={"image": image},
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.code == "handler_execution_error"
    assert result.error.details["exception_type"] == "RuntimeError"


def test_invalid_handler_return_type_is_result(image):
    registry = OperationRegistry()

    def invalid_handler(**kwargs):
        return image

    registry.register(spec=make_spec(), handler=invalid_handler)
    result = registry.execute(
        operation="identity",
        inputs={"image": image},
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.code == "invalid_handler_output"


def test_output_contract_failure_is_result(image):
    registry = OperationRegistry()

    def empty_handler(**kwargs):
        return OperationOutput()

    registry.register(spec=make_spec(), handler=empty_handler)
    result = registry.execute(
        operation="identity",
        inputs={"image": image},
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.code == "output_validation_error"
    assert result.error.details["issues"][0]["code"] == "missing_output"
