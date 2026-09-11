# src/schemas/execution.py

from __future__ import annotations

from typing import Any

from pydantic import Field

from .base import BaseSchema


class ExecutionRequest(BaseSchema):
    """
    외부 또는 내부에서 전달되는 원본 실행 요청.

    params는 아직 OperationSpec에 의해 검증되지 않은 상태다.
    """

    operation: str = Field(
        pattern=r"^[a-z][a-z0-9_]*$"
    )

    params: dict[str, Any] = Field(
        default_factory=dict
    )


class ValidatedExecutionRequest(BaseSchema):
    """
    OperationSpec을 기준으로 모든 validation과
    default 처리가 완료된 실행 요청.
    """

    operation: str = Field(
        pattern=r"^[a-z][a-z0-9_]*$"
    )

    # 사용자가 실제로 전달한 parameter와 default로 채워진 값을
    # 구분하기 위해 별도로 보관한다.
    provided_params: set[str] = Field(
        default_factory=set
    )

    params: dict[str, Any]
