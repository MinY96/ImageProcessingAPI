from __future__ import annotations

from threading import RLock

from src.schemas import PipelineSpec

from .compiler import CompiledPipeline
from .executor import PipelineExecutor


class PipelineCatalogError(RuntimeError):
    """Pipeline Catalog 오류의 기본 예외."""


class DuplicatePipelineError(PipelineCatalogError):
    """같은 이름의 Pipeline을 중복 등록할 때 발생한다."""


class PipelineNotFoundError(PipelineCatalogError):
    """등록되지 않은 Pipeline을 조회할 때 발생한다."""


class PipelineCatalog:
    """검증된 Pipeline을 이름으로 조회하고 재사용하기 위한 Catalog."""

    def __init__(self, executor: PipelineExecutor) -> None:
        self._executor = executor
        self._pipelines: dict[str, CompiledPipeline] = {}
        self._lock = RLock()

    def register(
        self,
        pipeline: PipelineSpec,
        *,
        replace: bool = False,
    ) -> None:
        compiled = self._executor.compile(pipeline)

        with self._lock:
            if pipeline.name in self._pipelines and not replace:
                raise DuplicatePipelineError(
                    f"pipeline is already registered: {pipeline.name}"
                )
            self._pipelines[pipeline.name] = compiled

    def get(self, name: str) -> CompiledPipeline:
        with self._lock:
            compiled = self._pipelines.get(name)

        if compiled is None:
            raise PipelineNotFoundError(
                f"pipeline is not registered: {name}"
            )

        return compiled

    def get_spec(self, name: str) -> PipelineSpec:
        return self.get(name).spec.model_copy(deep=True)

    def list_specs(self) -> list[PipelineSpec]:
        with self._lock:
            compiled_pipelines = [
                self._pipelines[name]
                for name in sorted(self._pipelines)
            ]

        return [
            item.spec.model_copy(deep=True)
            for item in compiled_pipelines
        ]

    def contains(self, name: str) -> bool:
        with self._lock:
            return name in self._pipelines

    def unregister(self, name: str) -> None:
        with self._lock:
            if name not in self._pipelines:
                raise PipelineNotFoundError(
                    f"pipeline is not registered: {name}"
                )
            del self._pipelines[name]
