from __future__ import annotations

from typing import Any

from .base import BaseSchema


class ParameterValidationIssue(BaseSchema):
    """한 개의 parameter 또는 parameter 관계 검증 오류."""

    parameter: str
    code: str
    message: str
    value: Any = None


class InputValidationIssue(BaseSchema):
    """한 개의 입력 슬롯 검증 오류."""

    input_name: str
    code: str
    message: str
    value: Any = None


class OutputValidationIssue(BaseSchema):
    """handler 반환값과 OutputSlotSpec 사이의 계약 오류."""

    output_name: str
    code: str
    message: str
    value: Any = None


class PipelineValidationIssue(BaseSchema):
    """Pipeline 구성과 Registry 계약 사이의 검증 오류."""

    location: str
    code: str
    message: str
    value: Any = None
