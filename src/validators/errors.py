from __future__ import annotations

from typing import Any

from src.schemas.validation import (
    InputValidationIssue,
    OutputValidationIssue,
    ParameterValidationIssue,
)


class ParameterValidationError(ValueError):
    """개별 및 교차 parameter 검증 오류를 한 번에 전달한다."""

    def __init__(
        self,
        issues: list[ParameterValidationIssue],
    ) -> None:
        self.issues = issues

        message = "; ".join(
            f"{issue.parameter}: {issue.message}"
            for issue in issues
        )

        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": "parameter_validation_error",
            "issues": [
                issue.model_dump(mode="json")
                for issue in self.issues
            ],
        }


class InputValidationError(ValueError):
    """실행 입력이 OperationSpec의 입력 슬롯과 맞지 않을 때 발생한다."""

    def __init__(
        self,
        issues: list[InputValidationIssue],
    ) -> None:
        self.issues = issues
        super().__init__(
            "; ".join(
                f"{issue.input_name}: {issue.message}"
                for issue in issues
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": "input_validation_error",
            "issues": [
                issue.model_dump(mode="json")
                for issue in self.issues
            ],
        }


class OutputValidationError(ValueError):
    """handler 반환값이 OperationSpec의 출력 계약과 맞지 않을 때 발생한다."""

    def __init__(
        self,
        issues: list[OutputValidationIssue],
    ) -> None:
        self.issues = issues
        super().__init__(
            "; ".join(
                f"{issue.output_name}: {issue.message}"
                for issue in issues
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": "output_validation_error",
            "issues": [
                issue.model_dump(mode="json")
                for issue in self.issues
            ],
        }
