class EvaluationError(RuntimeError):
    """TestDataset / Evaluation 관리 오류의 기본 예외."""


class TestDatasetNotFoundError(EvaluationError):
    pass


class DuplicateTestDatasetError(EvaluationError):
    pass


class TestDatasetRevisionConflictError(EvaluationError):
    pass


class TestDatasetImageNotFoundError(EvaluationError):
    pass


class TestDatasetStoreError(EvaluationError):
    pass


class EvaluationRunNotFoundError(EvaluationError):
    pass


class EvaluationStoreError(EvaluationError):
    pass


class EvaluationValidationError(EvaluationError):
    pass


class EvaluationActiveError(EvaluationError):
    pass
