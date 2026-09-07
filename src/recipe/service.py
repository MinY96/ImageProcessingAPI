from __future__ import annotations

from datetime import datetime, timezone
from threading import RLock

from src.pipeline import PipelineCatalog, PipelineExecutor, PipelineValidationError

from .errors import (
    DuplicateRecipeError,
    ReadonlyRecipeError,
    RecipeNotFoundError,
    RecipeRevisionConflictError,
)
from .schemas import (
    RecipeCloneRequest,
    RecipeCreateRequest,
    RecipeRecord,
    RecipeSource,
    RecipeSummary,
    RecipeUpdateRequest,
)
from .store import RecipeStore


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RecipeService:
    """기본 Pipeline과 사용자 Recipe를 하나의 Recipe API로 제공한다."""

    def __init__(
        self,
        *,
        executor: PipelineExecutor,
        catalog: PipelineCatalog,
        store: RecipeStore,
        readonly_names: set[str],
    ) -> None:
        self._executor = executor
        self._catalog = catalog
        self._store = store
        self._readonly_names = set(readonly_names)
        self._user_records: dict[str, RecipeRecord] = {}
        self._lock = RLock()
        self._load_user_recipes()

    def _load_user_recipes(self) -> None:
        for record in self._store.load_all():
            if record.source != RecipeSource.USER or record.readonly:
                raise ValueError(
                    f"persisted recipe must be a mutable user recipe: {record.name}"
                )
            if record.name in self._readonly_names:
                raise DuplicateRecipeError(
                    f"persisted recipe conflicts with readonly pipeline: {record.name}"
                )
            if record.pipeline.name != record.name:
                raise ValueError(
                    f"recipe name and pipeline name differ: {record.name} != {record.pipeline.name}"
                )
            self._executor.compile(record.pipeline)
            self._catalog.register(record.pipeline)
            self._user_records[record.name] = record

    @staticmethod
    def _summary(record: RecipeRecord) -> RecipeSummary:
        return RecipeSummary(
            name=record.name,
            display_name=record.pipeline.display_name,
            description=record.pipeline.description,
            version=record.pipeline.version,
            source=record.source,
            readonly=record.readonly,
            tags=record.tags,
            revision=record.revision,
            step_count=len(record.pipeline.steps),
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    def _builtin_record(self, name: str) -> RecipeRecord:
        if name not in self._readonly_names:
            raise RecipeNotFoundError(f"recipe does not exist: {name}")
        pipeline = self._catalog.get_spec(name)
        return RecipeRecord(
            name=name,
            pipeline=pipeline,
            source=RecipeSource.BUILTIN,
            readonly=True,
            revision=1,
        )

    def list(
        self,
        *,
        source: RecipeSource | None = None,
        tag: str | None = None,
        search: str | None = None,
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
            if tag is not None and tag not in record.tags:
                continue
            if normalized_search:
                haystack = " ".join(
                    filter(
                        None,
                        [
                            record.name,
                            record.pipeline.display_name,
                            record.pipeline.description,
                            " ".join(record.tags),
                        ],
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
        pipeline = request.pipeline
        with self._lock:
            if pipeline.name in self._readonly_names or pipeline.name in self._user_records:
                raise DuplicateRecipeError(f"recipe already exists: {pipeline.name}")

            self._executor.compile(pipeline)
            now = _utc_now()
            record = RecipeRecord(
                name=pipeline.name,
                pipeline=pipeline.model_copy(deep=True),
                source=RecipeSource.USER,
                readonly=False,
                tags=request.tags,
                revision=1,
                created_at=now,
                updated_at=now,
            )
            self._store.save(record)
            self._catalog.register(record.pipeline)
            self._user_records[record.name] = record
            return record.model_copy(deep=True)

    def clone(self, name: str, request: RecipeCloneRequest) -> RecipeRecord:
        source = self.get(name)
        pipeline = source.pipeline.model_copy(
            update={
                "name": request.name,
                "display_name": request.display_name or source.pipeline.display_name,
                "description": (
                    request.description
                    if request.description is not None
                    else source.pipeline.description
                ),
            },
            deep=True,
        )
        tags = source.tags if request.tags is None else request.tags
        return self.create(RecipeCreateRequest(pipeline=pipeline, tags=tags))

    def update(self, name: str, request: RecipeUpdateRequest) -> RecipeRecord:
        with self._lock:
            if name in self._readonly_names:
                raise ReadonlyRecipeError(f"readonly recipe cannot be modified: {name}")
            current = self._user_records.get(name)
            if current is None:
                raise RecipeNotFoundError(f"recipe does not exist: {name}")
            if request.pipeline.name != name:
                raise ValueError("pipeline.name must match the recipe name in the URL")
            if request.expected_revision is not None and request.expected_revision != current.revision:
                raise RecipeRevisionConflictError(
                    f"recipe revision conflict: expected {request.expected_revision}, current {current.revision}"
                )

            self._executor.compile(request.pipeline)
            updated = RecipeRecord(
                name=name,
                pipeline=request.pipeline.model_copy(deep=True),
                source=RecipeSource.USER,
                readonly=False,
                tags=request.tags,
                revision=current.revision + 1,
                created_at=current.created_at,
                updated_at=_utc_now(),
            )
            self._store.save(updated)
            self._catalog.register(updated.pipeline, replace=True)
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
            self._catalog.unregister(name)
            del self._user_records[name]
