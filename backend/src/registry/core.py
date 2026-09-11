from __future__ import annotations

import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from threading import RLock
from types import MappingProxyType
from typing import Any

from src.schemas.execution import ExecutionRequest
from src.schemas.operation import OperationSpec
from src.schemas.result import (
    ExecutionMetadata,
    ExecutionResult,
    OperationError,
    OperationOutput,
)
from src.validators import (
    InputValidationError,
    InputValidator,
    OutputValidationError,
    OutputValidator,
    ParameterValidationError,
    ParameterValidator,
)

from .errors import (
    DuplicateOperationError,
    OperationExecutionError,
    OperationNotFoundError,
)
from .handler import OperationHandler


@dataclass(frozen=True, slots=True)
class RegisteredOperation:
    spec: OperationSpec
    handler: OperationHandler


class OperationRegistry:
    """
    OperationSpec과 handler를 연결하고 공통 실행 흐름을 제공한다.

    등록/조회는 lock으로 보호하지만 실제 이미지 처리 중에는 lock을
    유지하지 않으므로 여러 요청을 병렬 실행할 수 있다.
    """

    def __init__(self) -> None:
        self._operations: dict[str, RegisteredOperation] = {}
        self._lock = RLock()
        self._revision = 0

    def register(
        self,
        *,
        spec: OperationSpec,
        handler: OperationHandler,
        replace: bool = False,
    ) -> None:
        if not callable(handler):
            raise TypeError("handler must be callable")

        stored_spec = spec.model_copy(deep=True)

        with self._lock:
            if stored_spec.name in self._operations and not replace:
                raise DuplicateOperationError(
                    f"operation is already registered: {stored_spec.name}"
                )

            self._operations[stored_spec.name] = RegisteredOperation(
                spec=stored_spec,
                handler=handler,
            )
            self._revision += 1

    def operation(
        self,
        spec: OperationSpec,
        *,
        replace: bool = False,
    ) -> Callable[[OperationHandler], OperationHandler]:
        """함수를 operation handler로 등록하는 decorator."""

        def decorator(handler: OperationHandler) -> OperationHandler:
            self.register(
                spec=spec,
                handler=handler,
                replace=replace,
            )
            return handler

        return decorator

    def unregister(self, operation: str) -> None:
        with self._lock:
            if operation not in self._operations:
                raise OperationNotFoundError(
                    f"operation is not registered: {operation}"
                )
            del self._operations[operation]
            self._revision += 1

    @property
    def revision(self) -> int:
        with self._lock:
            return self._revision

    def contains(self, operation: str) -> bool:
        with self._lock:
            return operation in self._operations

    def get_spec(self, operation: str) -> OperationSpec:
        registration = self._get_registration(operation)
        return registration.spec.model_copy(deep=True)

    def list_specs(self) -> list[OperationSpec]:
        with self._lock:
            registrations = [
                self._operations[name]
                for name in sorted(self._operations)
            ]

        return [
            item.spec.model_copy(deep=True)
            for item in registrations
        ]

    def snapshot_specs(
        self,
        operations: Iterable[str],
    ) -> tuple[int, dict[str, OperationSpec]]:
        """요청한 operation spec과 Registry revision을 원자적으로 복사한다."""

        requested = set(operations)
        with self._lock:
            revision = self._revision
            specs = {
                name: registration.spec.model_copy(deep=True)
                for name, registration in self._operations.items()
                if name in requested
            }

        return revision, specs

    def execute(
        self,
        *,
        operation: str,
        inputs: Mapping[str, Any] | None = None,
        params: Mapping[str, Any] | None = None,
    ) -> ExecutionResult:
        """입력/파라미터 검증부터 handler 실행과 결과 검증까지 처리한다."""

        started_at = time.perf_counter()

        try:
            registration = self._get_registration(operation)
        except OperationNotFoundError as exc:
            return self._failure_result(
                operation=operation,
                code="operation_not_found",
                message=str(exc),
                details={},
                started_at=started_at,
            )

        input_values = dict(inputs or {})
        parameter_values = dict(params or {})

        try:
            validated_inputs = InputValidator.validate(
                inputs=input_values,
                operation_spec=registration.spec,
            )
        except InputValidationError as exc:
            return self._validation_failure_result(
                operation=operation,
                error=exc,
                started_at=started_at,
            )

        try:
            validated_request = ParameterValidator.validate_request(
                request=ExecutionRequest(
                    operation=operation,
                    params=parameter_values,
                ),
                operation_spec=registration.spec,
            )
        except ParameterValidationError as exc:
            return self._validation_failure_result(
                operation=operation,
                error=exc,
                started_at=started_at,
            )

        try:
            output = registration.handler(
                inputs=MappingProxyType(validated_inputs),
                params=MappingProxyType(validated_request.params),
            )
        except OperationExecutionError as exc:
            return self._failure_result(
                operation=operation,
                code=exc.code,
                message=str(exc),
                details=exc.details,
                started_at=started_at,
            )
        except Exception as exc:
            return self._failure_result(
                operation=operation,
                code="handler_execution_error",
                message=str(exc) or "operation handler failed",
                details={"exception_type": type(exc).__name__},
                started_at=started_at,
            )

        if not isinstance(output, OperationOutput):
            return self._failure_result(
                operation=operation,
                code="invalid_handler_output",
                message="handler must return OperationOutput",
                details={"returned_type": type(output).__name__},
                started_at=started_at,
            )

        try:
            OutputValidator.validate(
                output=output,
                operation_spec=registration.spec,
            )
        except OutputValidationError as exc:
            return self._validation_failure_result(
                operation=operation,
                error=exc,
                started_at=started_at,
            )

        return ExecutionResult(
            operation=operation,
            success=True,
            output=output,
            metadata=ExecutionMetadata(
                duration_ms=self._elapsed_ms(started_at)
            ),
        )

    def _get_registration(
        self,
        operation: str,
    ) -> RegisteredOperation:
        with self._lock:
            registration = self._operations.get(operation)

        if registration is None:
            raise OperationNotFoundError(
                f"operation is not registered: {operation}"
            )

        return registration

    @classmethod
    def _validation_failure_result(
        cls,
        *,
        operation: str,
        error: (
            InputValidationError
            | ParameterValidationError
            | OutputValidationError
        ),
        started_at: float,
    ) -> ExecutionResult:
        error_data = error.to_dict()
        return cls._failure_result(
            operation=operation,
            code=error_data["error"],
            message=str(error),
            details={"issues": error_data["issues"]},
            started_at=started_at,
        )

    @classmethod
    def _failure_result(
        cls,
        *,
        operation: str,
        code: str,
        message: str,
        details: dict[str, Any],
        started_at: float,
    ) -> ExecutionResult:
        return ExecutionResult(
            operation=operation,
            success=False,
            metadata=ExecutionMetadata(
                duration_ms=cls._elapsed_ms(started_at)
            ),
            error=OperationError(
                code=code,
                message=message,
                details=details,
            ),
        )

    @staticmethod
    def _elapsed_ms(started_at: float) -> float:
        return max(
            0.0,
            (time.perf_counter() - started_at) * 1000.0,
        )
