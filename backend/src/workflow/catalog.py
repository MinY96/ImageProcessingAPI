from __future__ import annotations

from threading import RLock

from src.workflow.compiler import CompiledWorkflow
from src.workflow.errors import DuplicateWorkflowError, WorkflowNotFoundError
from src.workflow.executor import WorkflowExecutor
from src.workflow.schemas import GraphRecipeSpec


class WorkflowCatalog:
    def __init__(self, executor: WorkflowExecutor) -> None:
        self._executor = executor
        self._items: dict[str, CompiledWorkflow] = {}
        self._lock = RLock()

    def register(self, recipe: GraphRecipeSpec, *, replace: bool = False) -> None:
        compiled = self._executor.compile(recipe)
        with self._lock:
            if recipe.name in self._items and not replace:
                raise DuplicateWorkflowError(f"graph recipe already registered: {recipe.name}")
            self._items[recipe.name] = compiled

    def contains(self, name: str) -> bool:
        with self._lock:
            return name in self._items

    def get(self, name: str) -> CompiledWorkflow:
        with self._lock:
            item = self._items.get(name)
        if item is None:
            raise WorkflowNotFoundError(f"graph recipe is not registered: {name}")
        return item

    def get_spec(self, name: str) -> GraphRecipeSpec:
        return self.get(name).spec.model_copy(deep=True)

    def list_specs(self) -> list[GraphRecipeSpec]:
        with self._lock:
            return [self._items[name].spec.model_copy(deep=True) for name in sorted(self._items)]

    def unregister(self, name: str) -> None:
        with self._lock:
            if name not in self._items:
                raise WorkflowNotFoundError(f"graph recipe is not registered: {name}")
            del self._items[name]
