from __future__ import annotations

from src.schemas.enums import ColorSpace, OutputKind
from src.schemas.operation import OperationSpec
from src.schemas.result import OperationOutput
from src.schemas.validation import OutputValidationIssue

from .errors import OutputValidationError


class OutputValidator:
    """handler 출력이 OperationSpec의 출력 슬롯과 일치하는지 검증한다."""

    _IMAGE_KINDS = {OutputKind.IMAGE, OutputKind.MASK}

    @classmethod
    def validate(
        cls,
        output: OperationOutput,
        operation_spec: OperationSpec,
    ) -> None:
        issues: list[OutputValidationIssue] = []
        slots = {
            slot.name: slot
            for slot in operation_spec.outputs
        }
        provided_names = set(output.images) | set(output.data)

        for name in sorted(provided_names - set(slots)):
            issues.append(
                OutputValidationIssue(
                    output_name=name,
                    code="unknown_output",
                    message=(
                        f"handler returned an undefined output for "
                        f"{operation_spec.name}"
                    ),
                )
            )

        for name, slot in slots.items():
            if name not in provided_names:
                issues.append(
                    OutputValidationIssue(
                        output_name=name,
                        code="missing_output",
                        message="handler did not return required output",
                    )
                )
                continue

            if slot.kind in cls._IMAGE_KINDS and name not in output.images:
                issues.append(
                    OutputValidationIssue(
                        output_name=name,
                        code="invalid_output_container",
                        message="image-like output must be stored in images",
                    )
                )
                continue

            if slot.kind not in cls._IMAGE_KINDS and name not in output.data:
                issues.append(
                    OutputValidationIssue(
                        output_name=name,
                        code="invalid_output_container",
                        message="non-image output must be stored in data",
                    )
                )
                continue

            if (
                slot.kind == OutputKind.MASK
                and output.images[name].color_space
                not in {ColorSpace.GRAY, ColorSpace.BINARY}
            ):
                issues.append(
                    OutputValidationIssue(
                        output_name=name,
                        code="invalid_mask_color_space",
                        message="mask output must be gray or binary",
                        value=output.images[name].color_space.value,
                    )
                )

        duplicated_names = set(output.images) & set(output.data)
        for name in sorted(duplicated_names):
            issues.append(
                OutputValidationIssue(
                    output_name=name,
                    code="duplicate_output",
                    message="output name exists in both images and data",
                )
            )

        if issues:
            raise OutputValidationError(issues)
