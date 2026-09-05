# src/validators/parameter.py

from __future__ import annotations

import math
from numbers import Integral, Real
from typing import Any, Mapping

from src.schemas.execution import (
    ExecutionRequest,
    ValidatedExecutionRequest,
)
from src.schemas.operation import OperationSpec
from src.schemas.parameter import (
    CategoryParameterSpec,
    ContinuousParameterSpec,
    DiscreteParameterSpec,
)
from src.schemas.validation import ParameterValidationIssue

from .cross_parameter import CrossParameterValidator
from .errors import ParameterValidationError

class ParameterValidator:
    """
    OperationSpec의 parameter 정의를 기준으로
    실제 실행 parameter를 검증하고 정규화한다.
    """

    @classmethod
    def validate_request(
        cls,
        request: ExecutionRequest,
        operation_spec: OperationSpec,
    ) -> ValidatedExecutionRequest:

        if request.operation != operation_spec.name:
            raise ValueError(
                "request.operation does not match "
                f"operation_spec.name: "
                f"{request.operation!r} != "
                f"{operation_spec.name!r}"
            )

        validated_params = cls.validate_params(
            params=request.params,
            operation_spec=operation_spec,
        )

        provided_params = set(request.params)

        CrossParameterValidator.validate(
            params=validated_params,
            provided_params=provided_params,
            operation_spec=operation_spec,
        )

        return ValidatedExecutionRequest(
            operation=request.operation,
            provided_params=provided_params,
            params=validated_params,
        )

    @classmethod
    def validate_params(
        cls,
        params: Mapping[str, Any],
        operation_spec: OperationSpec,
    ) -> dict[str, Any]:

        issues: list[ParameterValidationIssue] = []
        validated: dict[str, Any] = {}

        parameter_specs = operation_spec.parameters

        # ---------------------------------------
        # 1. 정의되지 않은 parameter 검사
        # ---------------------------------------

        unknown_names = (
            set(params.keys())
            - set(parameter_specs.keys())
        )

        for name in sorted(unknown_names):
            issues.append(
                ParameterValidationIssue(
                    parameter=name,
                    code="unknown_parameter",
                    message=(
                        f"unknown parameter for "
                        f"{operation_spec.name}"
                    ),
                    value=params[name],
                )
            )

        # ---------------------------------------
        # 2. 각 parameter 검증
        # ---------------------------------------

        for name, parameter_spec in parameter_specs.items():

            supplied = name in params

            if not supplied:

                # default 존재
                if parameter_spec.default is not None:
                    validated[name] = parameter_spec.default
                    continue

                # required인데 값도 default도 없음
                if parameter_spec.required:
                    issues.append(
                        ParameterValidationIssue(
                            parameter=name,
                            code="missing_required",
                            message="required parameter is missing",
                        )
                    )

                # optional + default 없음
                continue

            raw_value = params[name]

            try:
                validated_value = cls._validate_value(
                    value=raw_value,
                    spec=parameter_spec,
                )

                validated[name] = validated_value

            except ParameterValidationIssueError as exc:
                issues.append(
                    ParameterValidationIssue(
                        parameter=name,
                        code=exc.code,
                        message=exc.message,
                        value=raw_value,
                    )
                )

        if issues:
            raise ParameterValidationError(issues)

        return validated

    @classmethod
    def _validate_value(
        cls,
        value: Any,
        spec: (
            ContinuousParameterSpec
            | DiscreteParameterSpec
            | CategoryParameterSpec
        ),
    ) -> Any:

        if isinstance(
            spec,
            ContinuousParameterSpec,
        ):
            return cls._validate_continuous(
                value=value,
                spec=spec,
            )

        if isinstance(
            spec,
            DiscreteParameterSpec,
        ):
            return cls._validate_discrete(
                value=value,
                spec=spec,
            )

        if isinstance(
            spec,
            CategoryParameterSpec,
        ):
            return cls._validate_category(
                value=value,
                spec=spec,
            )

        raise TypeError(
            f"unsupported ParameterSpec: "
            f"{type(spec).__name__}"
        )

    @staticmethod
    def _validate_continuous(
        value: Any,
        spec: ContinuousParameterSpec,
    ) -> float:

        # Python에서 bool은 int subclass이므로
        # 반드시 먼저 차단한다.
        if isinstance(value, bool):
            raise ParameterValidationIssueError(
                code="invalid_type",
                message="value must be a real number",
            )

        if not isinstance(value, Real):
            raise ParameterValidationIssueError(
                code="invalid_type",
                message="value must be a real number",
            )

        normalized = float(value)

        if not math.isfinite(normalized):
            raise ParameterValidationIssueError(
                code="non_finite",
                message="value must be finite",
            )

        if normalized < spec.min_value:
            raise ParameterValidationIssueError(
                code="below_minimum",
                message=(
                    f"value must be >= "
                    f"{spec.min_value}"
                ),
            )

        if normalized > spec.max_value:
            raise ParameterValidationIssueError(
                code="above_maximum",
                message=(
                    f"value must be <= "
                    f"{spec.max_value}"
                ),
            )

        return normalized

    @staticmethod
    def _validate_discrete(
        value: Any,
        spec: DiscreteParameterSpec,
    ) -> int:

        if isinstance(value, bool):
            raise ParameterValidationIssueError(
                code="invalid_type",
                message="value must be an integer",
            )

        if not isinstance(value, Integral):
            raise ParameterValidationIssueError(
                code="invalid_type",
                message="value must be an integer",
            )

        normalized = int(value)

        # explicit values mode
        if spec.values is not None:

            if normalized not in spec.values:
                raise ParameterValidationIssueError(
                    code="invalid_choice",
                    message=(
                        "value must be one of "
                        f"{spec.values}"
                    ),
                )

            return normalized

        # range mode
        assert spec.min_value is not None
        assert spec.max_value is not None

        if normalized < spec.min_value:
            raise ParameterValidationIssueError(
                code="below_minimum",
                message=(
                    f"value must be >= "
                    f"{spec.min_value}"
                ),
            )

        if normalized > spec.max_value:
            raise ParameterValidationIssueError(
                code="above_maximum",
                message=(
                    f"value must be <= "
                    f"{spec.max_value}"
                ),
            )

        step = spec.step or 1

        if (
            normalized - spec.min_value
        ) % step != 0:
            raise ParameterValidationIssueError(
                code="invalid_step",
                message=(
                    f"value must align with "
                    f"min={spec.min_value}, "
                    f"step={step}"
                ),
            )

        return normalized

    @staticmethod
    def _validate_category(
        value: Any,
        spec: CategoryParameterSpec,
    ) -> Any:

        for choice in spec.choices:

            if (
                type(value) is type(choice.value)
                and value == choice.value
            ):
                return value

        allowed = [
            choice.value
            for choice in spec.choices
        ]

        raise ParameterValidationIssueError(
            code="invalid_choice",
            message=(
                f"value must be one of "
                f"{allowed}"
            ),
        )

class ParameterValidationIssueError(ValueError):
    def __init__(
        self,
        code: str,
        message: str,
    ) -> None:
        self.code = code
        self.message = message

        super().__init__(message)
