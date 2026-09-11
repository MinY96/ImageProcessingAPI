# src/schemas/constraint.py

from __future__ import annotations

from typing import Annotated, Any, Literal, TypeAlias

from pydantic import Field, model_validator

from .base import BaseSchema
from .enums import ConstraintType

class ConstraintBase(BaseSchema):
    message: str | None = None

    def referenced_parameters(self) -> set[str]:
        raise NotImplementedError

class LessThanConstraint(ConstraintBase):
    type: Literal[
        ConstraintType.LESS_THAN
    ] = ConstraintType.LESS_THAN

    left: str
    right: str

    def referenced_parameters(self) -> set[str]:
        return {self.left, self.right}

class LessThanEqualConstraint(ConstraintBase):
    type: Literal[
        ConstraintType.LESS_THAN_EQUAL
    ] = ConstraintType.LESS_THAN_EQUAL

    left: str
    right: str

    def referenced_parameters(self) -> set[str]:
        return {self.left, self.right}

class GreaterThanConstraint(ConstraintBase):
    type: Literal[
        ConstraintType.GREATER_THAN
    ] = ConstraintType.GREATER_THAN

    left: str
    right: str

    def referenced_parameters(self) -> set[str]:
        return {self.left, self.right}


class GreaterThanEqualConstraint(ConstraintBase):
    type: Literal[
        ConstraintType.GREATER_THAN_EQUAL
    ] = ConstraintType.GREATER_THAN_EQUAL

    left: str
    right: str

    def referenced_parameters(self) -> set[str]:
        return {self.left, self.right}

class RequireTogetherConstraint(ConstraintBase):
    type: Literal[
        ConstraintType.REQUIRE_TOGETHER
    ] = ConstraintType.REQUIRE_TOGETHER

    parameters: list[str]

    @model_validator(mode="after")
    def validate_parameters(
        self,
    ) -> "RequireTogetherConstraint":

        if len(self.parameters) < 2:
            raise ValueError(
                "require_together requires "
                "at least two parameters"
            )

        if len(self.parameters) != len(
            set(self.parameters)
        ):
            raise ValueError(
                "parameters must be unique"
            )

        return self

    def referenced_parameters(self) -> set[str]:
        return set(self.parameters)

class MutuallyExclusiveConstraint(ConstraintBase):
    type: Literal[
        ConstraintType.MUTUALLY_EXCLUSIVE
    ] = ConstraintType.MUTUALLY_EXCLUSIVE

    parameters: list[str]

    @model_validator(mode="after")
    def validate_parameters(
        self,
    ) -> "MutuallyExclusiveConstraint":

        if len(self.parameters) < 2:
            raise ValueError(
                "mutually_exclusive requires "
                "at least two parameters"
            )

        if len(self.parameters) != len(
            set(self.parameters)
        ):
            raise ValueError(
                "parameters must be unique"
            )

        return self

    def referenced_parameters(self) -> set[str]:
        return set(self.parameters)

class ExactlyOneGroupConstraint(ConstraintBase):
    type: Literal[
        ConstraintType.EXACTLY_ONE_GROUP
    ] = ConstraintType.EXACTLY_ONE_GROUP

    groups: list[list[str]]

    @model_validator(mode="after")
    def validate_groups(
        self,
    ) -> "ExactlyOneGroupConstraint":

        if len(self.groups) < 2:
            raise ValueError(
                "exactly_one_group requires "
                "at least two groups"
            )

        for group in self.groups:

            if not group:
                raise ValueError(
                    "group must not be empty"
                )

            if len(group) != len(set(group)):
                raise ValueError(
                    "group parameters must be unique"
                )

        normalized_groups = [
            frozenset(group)
            for group in self.groups
        ]

        if len(normalized_groups) != len(
            set(normalized_groups)
        ):
            raise ValueError(
                "groups must be unique"
            )

        return self

    def referenced_parameters(self) -> set[str]:
        return {
            parameter
            for group in self.groups
            for parameter in group
        }

class ConditionalRequiredConstraint(ConstraintBase):
    type: Literal[
        ConstraintType.CONDITIONAL_REQUIRED
    ] = ConstraintType.CONDITIONAL_REQUIRED

    parameter: str

    equals: Any

    required_parameters: list[str]

    @model_validator(mode="after")
    def validate_required_parameters(
        self,
    ) -> "ConditionalRequiredConstraint":
        if not self.required_parameters:
            raise ValueError(
                "required_parameters must not be empty"
            )

        if len(self.required_parameters) != len(
            set(self.required_parameters)
        ):
            raise ValueError(
                "required_parameters must be unique"
            )

        if self.parameter in self.required_parameters:
            raise ValueError(
                "condition parameter cannot require itself"
            )

        return self

    def referenced_parameters(self) -> set[str]:
        return {
            self.parameter,
            *self.required_parameters,
        }

ConstraintSpec: TypeAlias = Annotated[
    LessThanConstraint
    | LessThanEqualConstraint
    | GreaterThanConstraint
    | GreaterThanEqualConstraint
    | RequireTogetherConstraint
    | MutuallyExclusiveConstraint
    | ExactlyOneGroupConstraint
    | ConditionalRequiredConstraint,
    Field(discriminator="type"),
]
