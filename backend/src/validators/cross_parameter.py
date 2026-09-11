from __future__ import annotations

from collections.abc import Callable
from typing import Any

from src.schemas.constraint import (
    ConditionalRequiredConstraint,
    ConstraintSpec,
    ExactlyOneGroupConstraint,
    GreaterThanConstraint,
    GreaterThanEqualConstraint,
    LessThanConstraint,
    LessThanEqualConstraint,
    MutuallyExclusiveConstraint,
    RequireTogetherConstraint,
)
from src.schemas.operation import OperationSpec
from src.schemas.validation import ParameterValidationIssue

from .errors import ParameterValidationError


class CrossParameterValidator:
    """OperationSpec에 선언된 parameter 간 관계를 검증한다."""

    @classmethod
    def validate(
        cls,
        params: dict[str, Any],
        provided_params: set[str],
        operation_spec: OperationSpec,
    ) -> None:
        issues: list[ParameterValidationIssue] = []

        for constraint in operation_spec.constraints:
            issue = cls._validate_constraint(
                params=params,
                provided_params=provided_params,
                constraint=constraint,
            )

            if issue is not None:
                issues.append(issue)

        if issues:
            raise ParameterValidationError(issues)

    @classmethod
    def _validate_constraint(
        cls,
        params: dict[str, Any],
        provided_params: set[str],
        constraint: ConstraintSpec,
    ) -> ParameterValidationIssue | None:
        if isinstance(constraint, LessThanConstraint):
            return cls._validate_comparison(
                params,
                constraint,
                lambda left, right: left < right,
                "cross_less_than",
                "must be smaller than",
            )

        if isinstance(constraint, LessThanEqualConstraint):
            return cls._validate_comparison(
                params,
                constraint,
                lambda left, right: left <= right,
                "cross_less_than_equal",
                "must be <=",
            )

        if isinstance(constraint, GreaterThanConstraint):
            return cls._validate_comparison(
                params,
                constraint,
                lambda left, right: left > right,
                "cross_greater_than",
                "must be >",
            )

        if isinstance(constraint, GreaterThanEqualConstraint):
            return cls._validate_comparison(
                params,
                constraint,
                lambda left, right: left >= right,
                "cross_greater_than_equal",
                "must be >=",
            )

        if isinstance(constraint, RequireTogetherConstraint):
            return cls._validate_require_together(
                provided_params,
                constraint,
            )

        if isinstance(constraint, MutuallyExclusiveConstraint):
            return cls._validate_mutually_exclusive(
                provided_params,
                constraint,
            )

        if isinstance(constraint, ExactlyOneGroupConstraint):
            return cls._validate_exactly_one_group(
                provided_params,
                constraint,
            )

        if isinstance(constraint, ConditionalRequiredConstraint):
            return cls._validate_conditional_required(
                params,
                constraint,
            )

        raise TypeError(
            "unsupported constraint: "
            f"{type(constraint).__name__}"
        )

    @staticmethod
    def _validate_comparison(
        params: dict[str, Any],
        constraint: (
            LessThanConstraint
            | LessThanEqualConstraint
            | GreaterThanConstraint
            | GreaterThanEqualConstraint
        ),
        predicate: Callable[[Any, Any], bool],
        code: str,
        relation_message: str,
    ) -> ParameterValidationIssue | None:
        if (
            constraint.left not in params
            or constraint.right not in params
        ):
            return None

        left = params[constraint.left]
        right = params[constraint.right]

        if predicate(left, right):
            return None

        return ParameterValidationIssue(
            parameter=constraint.left,
            code=code,
            message=(
                constraint.message
                or (
                    f"{constraint.left} {relation_message} "
                    f"{constraint.right}"
                )
            ),
            value={
                constraint.left: left,
                constraint.right: right,
            },
        )

    @staticmethod
    def _validate_require_together(
        provided_params: set[str],
        constraint: RequireTogetherConstraint,
    ) -> ParameterValidationIssue | None:
        present = [
            name
            for name in constraint.parameters
            if name in provided_params
        ]

        if not present or len(present) == len(constraint.parameters):
            return None

        missing = [
            name
            for name in constraint.parameters
            if name not in provided_params
        ]

        return ParameterValidationIssue(
            parameter=",".join(constraint.parameters),
            code="require_together",
            message=(
                constraint.message
                or (
                    "parameters must be provided together: "
                    f"{constraint.parameters}"
                )
            ),
            value={"present": present, "missing": missing},
        )

    @staticmethod
    def _validate_mutually_exclusive(
        provided_params: set[str],
        constraint: MutuallyExclusiveConstraint,
    ) -> ParameterValidationIssue | None:
        present = [
            name
            for name in constraint.parameters
            if name in provided_params
        ]

        if len(present) <= 1:
            return None

        return ParameterValidationIssue(
            parameter=",".join(constraint.parameters),
            code="mutually_exclusive",
            message=(
                constraint.message
                or (
                    "only one of these parameters may be provided: "
                    f"{constraint.parameters}"
                )
            ),
            value={"provided": present},
        )

    @staticmethod
    def _validate_exactly_one_group(
        provided_params: set[str],
        constraint: ExactlyOneGroupConstraint,
    ) -> ParameterValidationIssue | None:
        complete_groups: list[list[str]] = []
        partial_groups: list[list[str]] = []

        for group in constraint.groups:
            count = sum(
                parameter in provided_params
                for parameter in group
            )

            if count == len(group):
                complete_groups.append(group)
            elif count > 0:
                partial_groups.append(group)

        if partial_groups:
            return ParameterValidationIssue(
                parameter="group",
                code="partial_group",
                message=(
                    constraint.message
                    or "all parameters in a group must be provided"
                ),
                value={"partial_groups": partial_groups},
            )

        if len(complete_groups) == 1:
            return None

        return ParameterValidationIssue(
            parameter="group",
            code="exactly_one_group",
            message=(
                constraint.message
                or "exactly one parameter group must be provided"
            ),
            value={
                "groups": constraint.groups,
                "matched_groups": complete_groups,
            },
        )

    @staticmethod
    def _validate_conditional_required(
        params: dict[str, Any],
        constraint: ConditionalRequiredConstraint,
    ) -> ParameterValidationIssue | None:
        if constraint.parameter not in params:
            return None

        if params.get(constraint.parameter) != constraint.equals:
            return None

        missing = [
            name
            for name in constraint.required_parameters
            if name not in params
        ]

        if not missing:
            return None

        return ParameterValidationIssue(
            parameter=constraint.parameter,
            code="conditional_required",
            message=(
                constraint.message
                or (
                    f"when {constraint.parameter}="
                    f"{constraint.equals!r}, required parameters are "
                    f"{constraint.required_parameters}"
                )
            ),
            value={
                "condition_value": params[constraint.parameter],
                "missing": missing,
            },
        )
