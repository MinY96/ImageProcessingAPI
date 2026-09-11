from __future__ import annotations

from typing import Any

from src.schemas.validation import PipelineValidationIssue


class PipelineValidationError(ValueError):
    """PipelineSpec과 Registry 계약의 사전 검증 오류."""

    def __init__(
        self,
        issues: list[PipelineValidationIssue],
    ) -> None:
        self.issues = issues
        super().__init__(
            "; ".join(
                f"{issue.location}: {issue.message}"
                for issue in issues
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": "pipeline_validation_error",
            "issues": [
                issue.model_dump(mode="json")
                for issue in self.issues
            ],
        }
