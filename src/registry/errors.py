class RegistryError(RuntimeError):
    """Operation Registry 구성 오류의 기본 예외."""


class DuplicateOperationError(RegistryError):
    """동일한 이름의 operation을 중복 등록할 때 발생한다."""


class OperationNotFoundError(RegistryError):
    """등록되지 않은 operation을 조회할 때 발생한다."""


class OperationExecutionError(RuntimeError):
    """handler가 의도적으로 보고하는 안전한 실행 오류."""

    def __init__(
        self,
        *,
        code: str,
        message: str,
        details: dict | None = None,
    ) -> None:
        self.code = code
        self.details = details or {}
        super().__init__(message)
