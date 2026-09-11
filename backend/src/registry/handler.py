from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from src.schemas.result import OperationOutput


class OperationHandler(Protocol):
    """Registry에 등록할 이미지 처리 handler의 공통 호출 규약."""

    def __call__(
        self,
        *,
        inputs: Mapping[str, Any],
        params: Mapping[str, Any],
    ) -> OperationOutput:
        ...
