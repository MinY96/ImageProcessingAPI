from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np

from src.schemas.enums import ColorSpace, InputKind
from src.schemas.image import ImageConstraint, ImageData
from src.schemas.operation import InputSlotSpec, OperationSpec
from src.schemas.validation import InputValidationIssue

from .errors import InputValidationError


class InputValidator:
    """OperationSpec의 입력 슬롯 정의를 기준으로 실행 입력을 검증한다."""

    _IMAGE_KINDS = {
        InputKind.IMAGE,
        InputKind.MASK,
        InputKind.TEMPLATE,
    }

    @classmethod
    def validate(
        cls,
        inputs: Mapping[str, Any],
        operation_spec: OperationSpec,
    ) -> dict[str, Any]:
        return cls.validate_slots(
            inputs=inputs,
            slots=operation_spec.inputs,
            owner_name=operation_spec.name,
        )

    @classmethod
    def validate_slots(
        cls,
        *,
        inputs: Mapping[str, Any],
        slots: list[InputSlotSpec],
        owner_name: str,
    ) -> dict[str, Any]:
        issues: list[InputValidationIssue] = []
        slot_map = {
            slot.name: slot
            for slot in slots
        }

        for name in sorted(set(inputs) - set(slot_map)):
            issues.append(
                InputValidationIssue(
                    input_name=name,
                    code="unknown_input",
                    message=(
                        f"unknown input for {owner_name}"
                    ),
                )
            )

        for name, slot in slot_map.items():
            if name not in inputs:
                if slot.required:
                    issues.append(
                        InputValidationIssue(
                            input_name=name,
                            code="missing_required_input",
                            message="required input is missing",
                        )
                    )
                continue

            issue = cls._validate_slot(
                value=inputs[name],
                slot=slot,
            )

            if issue is not None:
                issues.append(issue)

        if issues:
            raise InputValidationError(issues)

        return {
            name: inputs[name]
            for name in slot_map
            if name in inputs
        }

    @classmethod
    def _validate_slot(
        cls,
        value: Any,
        slot: InputSlotSpec,
    ) -> InputValidationIssue | None:
        if slot.kind in cls._IMAGE_KINDS:
            if not isinstance(value, ImageData):
                return InputValidationIssue(
                    input_name=slot.name,
                    code="invalid_input_type",
                    message="input must be ImageData",
                    value=type(value).__name__,
                )

            if (
                slot.kind == InputKind.MASK
                and value.color_space
                not in {ColorSpace.GRAY, ColorSpace.BINARY}
            ):
                return InputValidationIssue(
                    input_name=slot.name,
                    code="invalid_mask_color_space",
                    message="mask input must be gray or binary",
                    value=value.color_space.value,
                )

            return cls._validate_image_constraint(
                image=value,
                slot=slot,
            )

        if (
            slot.kind == InputKind.ARRAY
            and not isinstance(value, (list, tuple, np.ndarray))
        ):
            return InputValidationIssue(
                input_name=slot.name,
                code="invalid_input_type",
                message="input must be a list, tuple, or numpy.ndarray",
                value=type(value).__name__,
            )

        if (
            slot.kind == InputKind.MARKERS
            and not isinstance(value, np.ndarray)
        ):
            return InputValidationIssue(
                input_name=slot.name,
                code="invalid_input_type",
                message="input must be a numpy.ndarray",
                value=type(value).__name__,
            )

        if (
            slot.kind in {InputKind.CONTOURS, InputKind.POINTS}
            and not isinstance(value, (list, tuple, np.ndarray))
        ):
            return InputValidationIssue(
                input_name=slot.name,
                code="invalid_input_type",
                message="input must be a list, tuple, or numpy.ndarray",
                value=type(value).__name__,
            )

        if slot.kind == InputKind.MODEL:
            from src.machine_learning.schemas import ModelData

            if not isinstance(value, ModelData):
                return InputValidationIssue(
                    input_name=slot.name,
                    code="invalid_input_type",
                    message="input must be ModelData",
                    value=type(value).__name__,
                )

        return None

    @staticmethod
    def _validate_image_constraint(
        image: ImageData,
        slot: InputSlotSpec,
    ) -> InputValidationIssue | None:
        constraint = slot.image_constraint

        if constraint is None:
            return None

        checks = InputValidator._image_constraint_checks(
            image=image,
            constraint=constraint,
        )

        for passed, code, message, value in checks:
            if not passed:
                return InputValidationIssue(
                    input_name=slot.name,
                    code=code,
                    message=message,
                    value=value,
                )

        return None

    @staticmethod
    def _image_constraint_checks(
        image: ImageData,
        constraint: ImageConstraint,
    ) -> list[tuple[bool, str, str, Any]]:
        color_spaces = {
            item.value
            for item in constraint.allowed_color_spaces
        }
        dtypes = {
            item.value
            for item in constraint.allowed_dtypes
        }

        return [
            (
                not color_spaces
                or image.color_space.value in color_spaces,
                "invalid_color_space",
                f"allowed color spaces are {sorted(color_spaces)}",
                image.color_space.value,
            ),
            (
                not dtypes or image.dtype in dtypes,
                "invalid_image_dtype",
                f"allowed image dtypes are {sorted(dtypes)}",
                image.dtype,
            ),
            (
                constraint.min_width is None
                or image.width >= constraint.min_width,
                "image_too_narrow",
                f"image width must be >= {constraint.min_width}",
                image.width,
            ),
            (
                constraint.max_width is None
                or image.width <= constraint.max_width,
                "image_too_wide",
                f"image width must be <= {constraint.max_width}",
                image.width,
            ),
            (
                constraint.min_height is None
                or image.height >= constraint.min_height,
                "image_too_short",
                f"image height must be >= {constraint.min_height}",
                image.height,
            ),
            (
                constraint.max_height is None
                or image.height <= constraint.max_height,
                "image_too_tall",
                f"image height must be <= {constraint.max_height}",
                image.height,
            ),
        ]
