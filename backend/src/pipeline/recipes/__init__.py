from src.schemas import PipelineSpec

from .compositing import create_compositing_recipes
from .editing import create_editing_recipes
from .inspection import create_inspection_recipes


def create_builtin_recipes() -> list[PipelineSpec]:
    return [
        *create_editing_recipes(),
        *create_inspection_recipes(),
        *create_compositing_recipes(),
    ]


__all__ = [
    "create_builtin_recipes",
    "create_compositing_recipes",
    "create_editing_recipes",
    "create_inspection_recipes",
]
