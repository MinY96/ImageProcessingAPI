from __future__ import annotations

from .core import OperationRegistry


def create_default_registry() -> OperationRegistry:
    """프로젝트가 기본 제공하는 operation이 등록된 새 Registry를 만든다."""

    from src.image_processing.builtins import register_builtin_operations

    registry = OperationRegistry()
    register_builtin_operations(registry)
    return registry
