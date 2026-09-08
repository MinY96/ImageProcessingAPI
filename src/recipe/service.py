from __future__ import annotations

from datetime import datetime, timezone
from threading import RLock

from src.pipeline import PipelineCatalog, PipelineExecutor
from src.workflow import WorkflowCatalog, WorkflowExecutor, WorkflowValidationError

from .errors import (
    DuplicateRecipeError,
    ReadonlyRecipeError,
    RecipeNotFoundError,
    RecipeRevisionConflictError,
)
from .schemas import (
    RecipeCloneRequest,
    RecipeCreateRequest,
    RecipeKind,
    RecipeRecord,
    RecipeSource,
    RecipeSummary,
    RecipeUpdateRequest,
)
from .store import RecipeStore


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RecipeService:
    """Linear Pipeline과 Graph Workflow를 하나의 Recipe API로 제공한다."""

    def __init__(
        self,
        *,
        executor: PipelineExecutor,
        catalog: PipelineCatalog,
        workflow_executor: WorkflowExecutor,
        workflow_catalog: WorkflowCatalog,
        store: RecipeStore,
        readonly_names: set[str],
        readonly_graph_names: set[str] | None = None,
    ) -> None:
        self._executor = executor
        self._catalog = catalog
        self._workflow_executor = workflow_executor
        self._workflow_catalog = workflow_catalog
        self._store = store
        self._readonly_linear_names = set(readonly_names)
        self._readonly_graph_names = set(readonly_graph_names or set())
        self._readonly_names = self._readonly_linear_names | self._readonly_graph_names
        self._user_records: dict[str, RecipeRecord] = {}
        self._lock = RLock()
        self._load_user_recipes()

    def _load_user_recipes(self) -> None:
        records = self._store.load_all()
        for record in records:
            if record.source != RecipeSource.USER or record.readonly:
                raise ValueError(
                    f"persisted recipe must be a mutable user recipe: {record.name}"
                )
            if record.name in self._readonly_names:
                raise DuplicateRecipeError(
                    f"persisted recipe conflicts with readonly recipe: {record.name}"
                )

        # Linear recipes have no graph-recipe dependency, so register them first.
        for record in records:
            if record.kind != RecipeKind.LINEAR:
                continue
            self._validate_record(record)
            self._register_record(record)
            self._user_records[record.name] = record

        # Graph subrecipes form a DAG. Persisted files are filename-sorted, not
        # dependency-sorted, so retry unresolved graphs until all dependencies
        # have been registered. This makes restart independent of file names.
        pending = {
            record.name: record
            for record in records
            if record.kind == RecipeKind.GRAPH
        }
        last_errors: dict[str, Exception] = {}
        while pending:
            progressed = False
            for name in list(pending):
                record = pending[name]
                try:
                    self._validate_record(record)
                    self._register_record(record)
                except WorkflowValidationError as exc:
                    last_errors[name] = exc
                    continue
                self._user_records[name] = record
                del pending[name]
                last_errors.pop(name, None)
                progressed = True
            if not progressed:
                details = "; ".join(
                    f"{name}: {last_errors.get(name)}" for name in sorted(pending)
                )
                raise ValueError(
                    "persisted graph recipes contain missing/cyclic subrecipe "
                    f"dependencies: {details}"
                )

    def _validate_record(self, record: RecipeRecord) -> None:
        if record.kind == RecipeKind.LINEAR:
            assert record.pipeline is not None
            self._executor.compile(record.pipeline)
        else:
            assert record.graph is not None
            self._workflow_executor.compile(record.graph)

    def _register_record(self, record: RecipeRecord, *, replace: bool = False) -> None:
        if record.kind == RecipeKind.LINEAR:
            assert record.pipeline is not None
            self._catalog.register(record.pipeline, replace=replace)
        else:
            assert record.graph is not None
            self._workflow_catalog.register(record.graph, replace=replace)

    @staticmethod
    def _artifact(record: RecipeRecord):
        return record.pipeline if record.kind == RecipeKind.LINEAR else record.graph

    @classmethod
    def _summary(cls, record: RecipeRecord) -> RecipeSummary:
        artifact = cls._artifact(record)
        assert artifact is not None
        return RecipeSummary(
            name=record.name,
            kind=record.kind,
            display_name=artifact.display_name,
            description=artifact.description,
            version=artifact.version,
            source=record.source,
            readonly=record.readonly,
            tags=record.tags,
            revision=record.revision,
            step_count=(len(record.pipeline.steps) if record.pipeline is not None else 0),
            node_count=(len(record.graph.nodes) if record.graph is not None else 0),
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    def _builtin_record(self, name: str) -> RecipeRecord:
        if name in self._readonly_linear_names:
            pipeline = self._catalog.get_spec(name)
            return RecipeRecord(
                name=name,
                kind=RecipeKind.LINEAR,
                pipeline=pipeline,
                source=RecipeSource.BUILTIN,
                readonly=True,
                revision=1,
            )
        if name in self._readonly_graph_names:
            graph = self._workflow_catalog.get_spec(name)
            return RecipeRecord(
                name=name,
                kind=RecipeKind.GRAPH,
                graph=graph,
                source=RecipeSource.BUILTIN,
                readonly=True,
                revision=1,
            )
        raise RecipeNotFoundError(f"recipe does not exist: {name}")

    def list(
        self,
        *,
        source: RecipeSource | None = None,
        tag: str | None = None,
        search: str | None = None,
        kind: RecipeKind | None = None,
    ) -> list[RecipeSummary]:
        with self._lock:
            records = [self._builtin_record(name) for name in sorted(self._readonly_names)]
            records.extend(
                self._user_records[name].model_copy(deep=True)
                for name in sorted(self._user_records)
            )

        normalized_search = search.casefold().strip() if search else None
        result: list[RecipeSummary] = []
        for record in records:
            if source is not None and record.source != source:
                continue
            if kind is not None and record.kind != kind:
                continue
            if tag is not None and tag not in record.tags:
                continue
            artifact = self._artifact(record)
            assert artifact is not None
            if normalized_search:
                haystack = " ".join(
                    filter(
                        None,
                        [record.name, artifact.display_name, artifact.description, " ".join(record.tags)],
                    )
                ).casefold()
                if normalized_search not in haystack:
                    continue
            result.append(self._summary(record))
        return result

    def get(self, name: str) -> RecipeRecord:
        with self._lock:
            user = self._user_records.get(name)
            if user is not None:
                return user.model_copy(deep=True)
        return self._builtin_record(name)

    def create(self, request: RecipeCreateRequest) -> RecipeRecord:
        assert request.kind is not None
        artifact = request.pipeline if request.kind == RecipeKind.LINEAR else request.graph
        assert artifact is not None
        with self._lock:
            if artifact.name in self._readonly_names or artifact.name in self._user_records:
                raise DuplicateRecipeError(f"recipe already exists: {artifact.name}")
            now = _utc_now()
            record = RecipeRecord(
                name=artifact.name,
                kind=request.kind,
                pipeline=(request.pipeline.model_copy(deep=True) if request.pipeline is not None else None),
                graph=(request.graph.model_copy(deep=True) if request.graph is not None else None),
                source=RecipeSource.USER,
                readonly=False,
                tags=request.tags,
                revision=1,
                created_at=now,
                updated_at=now,
            )
            self._validate_record(record)
            self._store.save(record)
            self._register_record(record)
            self._user_records[record.name] = record
            return record.model_copy(deep=True)

    def clone(self, name: str, request: RecipeCloneRequest) -> RecipeRecord:
        source = self.get(name)
        artifact = self._artifact(source)
        assert artifact is not None
        copied = artifact.model_copy(
            update={
                "name": request.name,
                "display_name": request.display_name or artifact.display_name,
                "description": request.description if request.description is not None else artifact.description,
            },
            deep=True,
        )
        tags = source.tags if request.tags is None else request.tags
        if source.kind == RecipeKind.LINEAR:
            return self.create(RecipeCreateRequest(kind=RecipeKind.LINEAR, pipeline=copied, tags=tags))
        return self.create(RecipeCreateRequest(kind=RecipeKind.GRAPH, graph=copied, tags=tags))

    def update(self, name: str, request: RecipeUpdateRequest) -> RecipeRecord:
        with self._lock:
            if name in self._readonly_names:
                raise ReadonlyRecipeError(f"readonly recipe cannot be modified: {name}")
            current = self._user_records.get(name)
            if current is None:
                raise RecipeNotFoundError(f"recipe does not exist: {name}")
            assert request.kind is not None
            if request.kind != current.kind:
                raise ValueError("recipe kind cannot be changed; clone/create a new recipe instead")
            artifact = request.pipeline if request.kind == RecipeKind.LINEAR else request.graph
            assert artifact is not None
            if artifact.name != name:
                raise ValueError("pipeline/graph name must match the recipe name in the URL")
            if request.expected_revision is not None and request.expected_revision != current.revision:
                raise RecipeRevisionConflictError(
                    f"recipe revision conflict: expected {request.expected_revision}, current {current.revision}"
                )

            updated = RecipeRecord(
                name=name,
                kind=request.kind,
                pipeline=(request.pipeline.model_copy(deep=True) if request.pipeline is not None else None),
                graph=(request.graph.model_copy(deep=True) if request.graph is not None else None),
                source=RecipeSource.USER,
                readonly=False,
                tags=request.tags,
                revision=current.revision + 1,
                created_at=current.created_at,
                updated_at=_utc_now(),
            )
            self._validate_record(updated)
            self._store.save(updated)
            self._register_record(updated, replace=True)
            self._user_records[name] = updated
            return updated.model_copy(deep=True)

    def delete(self, name: str, *, expected_revision: int | None = None) -> None:
        with self._lock:
            if name in self._readonly_names:
                raise ReadonlyRecipeError(f"readonly recipe cannot be deleted: {name}")
            current = self._user_records.get(name)
            if current is None:
                raise RecipeNotFoundError(f"recipe does not exist: {name}")
            if expected_revision is not None and expected_revision != current.revision:
                raise RecipeRevisionConflictError(
                    f"recipe revision conflict: expected {expected_revision}, current {current.revision}"
                )

            self._store.delete(name)
            if current.kind == RecipeKind.LINEAR:
                self._catalog.unregister(name)
            else:
                self._workflow_catalog.unregister(name)
            del self._user_records[name]
