from __future__ import annotations

from src.workflow.schemas import WorkflowValidationIssue


class WorkflowErrorBase(RuntimeError):
    pass


class WorkflowValidationError(WorkflowErrorBase):
    def __init__(self, issues: list[WorkflowValidationIssue]) -> None:
        self.issues = issues
        super().__init__(f"workflow validation failed with {len(issues)} issue(s)")

    def to_dict(self) -> dict:
        return {
            "error": "workflow_validation_error",
            "issues": [item.model_dump(mode="json") for item in self.issues],
        }


class WorkflowNotFoundError(WorkflowErrorBase):
    pass


class DuplicateWorkflowError(WorkflowErrorBase):
    pass
