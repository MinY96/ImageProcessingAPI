from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from threading import RLock
from uuid import uuid4

from pydantic import ValidationError

from .errors import (
    AnnotationNotFoundError,
    DuplicateAnnotationError,
    DuplicateLabelError,
    LabelNotFoundError,
    LabelRevisionConflictError,
)
from .schemas import (
    Annotation,
    LabelClassSummary,
    LabelCreateRequest,
    LabelDocument,
    LabelListResponse,
    LabelSummary,
    LabelUpdateRequest,
)
from .store import LabelStore


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _with_annotation_id(annotation: Annotation, annotation_id: str | None = None) -> Annotation:
    resolved = annotation_id or annotation.annotation_id or uuid4().hex
    return annotation.model_copy(update={"annotation_id": resolved}, deep=True)


class LabelService:
    def __init__(self, store: LabelStore) -> None:
        self._store = store
        self._lock = RLock()

    @staticmethod
    def _summary(document: LabelDocument) -> LabelSummary:
        return LabelSummary(
            image_id=document.image_id,
            image_name=document.image_name,
            width=document.width,
            height=document.height,
            tags=document.tags,
            annotation_count=len(document.annotations),
            labels=sorted({annotation.label for annotation in document.annotations}),
            revision=document.revision,
            updated_at=document.updated_at,
        )

    @staticmethod
    def _check_revision(document: LabelDocument, expected_revision: int | None) -> None:
        if expected_revision is not None and expected_revision != document.revision:
            raise LabelRevisionConflictError(
                f"label revision conflict: expected {expected_revision}, current {document.revision}"
            )

    def list(
        self,
        *,
        offset: int,
        limit: int,
        label: str | None = None,
        tag: str | None = None,
        search: str | None = None,
    ) -> LabelListResponse:
        documents = self._store.load_all()
        normalized_search = search.casefold().strip() if search else None
        filtered: list[LabelDocument] = []
        for document in documents:
            if label is not None and not any(item.label == label for item in document.annotations):
                continue
            if tag is not None and tag not in document.tags:
                continue
            if normalized_search:
                haystack = " ".join(
                    [document.image_id, document.image_name, document.source_uri or "", " ".join(document.tags)]
                ).casefold()
                if normalized_search not in haystack:
                    continue
            filtered.append(document)

        filtered.sort(key=lambda item: (item.updated_at, item.image_id), reverse=True)
        total = len(filtered)
        page = filtered[offset : offset + limit]
        return LabelListResponse(
            items=[self._summary(item) for item in page],
            total=total,
            offset=offset,
            limit=limit,
        )

    def get(self, image_id: str) -> LabelDocument:
        document = self._store.load(image_id)
        if document is None:
            raise LabelNotFoundError(f"label document does not exist: {image_id}")
        return document.model_copy(deep=True)

    def create(self, request: LabelCreateRequest) -> LabelDocument:
        with self._lock:
            image_id = request.image_id or uuid4().hex
            if self._store.load(image_id) is not None:
                raise DuplicateLabelError(f"label document already exists: {image_id}")

            annotations = [_with_annotation_id(item) for item in request.annotations]
            annotation_ids = [item.annotation_id for item in annotations]
            if len(annotation_ids) != len(set(annotation_ids)):
                raise DuplicateAnnotationError("annotation_id values must be unique within an image")

            now = _utc_now()
            try:
                document = LabelDocument(
                    image_id=image_id,
                    image_name=request.image_name,
                    source_uri=request.source_uri,
                    width=request.width,
                    height=request.height,
                    tags=request.tags,
                    metadata=request.metadata,
                    annotations=annotations,
                    revision=1,
                    created_at=now,
                    updated_at=now,
                )
            except ValidationError as exc:
                raise ValueError(str(exc)) from exc
            self._store.save(document)
            return document.model_copy(deep=True)

    def update(self, image_id: str, request: LabelUpdateRequest) -> LabelDocument:
        with self._lock:
            current = self.get(image_id)
            self._check_revision(current, request.expected_revision)
            annotations = [_with_annotation_id(item) for item in request.annotations]
            annotation_ids = [item.annotation_id for item in annotations]
            if len(annotation_ids) != len(set(annotation_ids)):
                raise DuplicateAnnotationError("annotation_id values must be unique within an image")

            document = LabelDocument(
                image_id=image_id,
                image_name=request.image_name,
                source_uri=request.source_uri,
                width=request.width,
                height=request.height,
                tags=request.tags,
                metadata=request.metadata,
                annotations=annotations,
                revision=current.revision + 1,
                created_at=current.created_at,
                updated_at=_utc_now(),
            )
            self._store.save(document)
            return document.model_copy(deep=True)

    def delete(self, image_id: str, *, expected_revision: int | None = None) -> None:
        with self._lock:
            current = self.get(image_id)
            self._check_revision(current, expected_revision)
            self._store.delete(image_id)

    def add_annotation(
        self,
        image_id: str,
        annotation: Annotation,
        *,
        expected_revision: int | None = None,
    ) -> LabelDocument:
        with self._lock:
            current = self.get(image_id)
            self._check_revision(current, expected_revision)
            resolved = _with_annotation_id(annotation)
            if any(item.annotation_id == resolved.annotation_id for item in current.annotations):
                raise DuplicateAnnotationError(
                    f"annotation already exists: {resolved.annotation_id}"
                )
            updated = current.model_copy(
                update={
                    "annotations": [*current.annotations, resolved],
                    "revision": current.revision + 1,
                    "updated_at": _utc_now(),
                },
                deep=True,
            )
            updated = LabelDocument.model_validate(updated.model_dump(mode="python"))
            self._store.save(updated)
            return updated.model_copy(deep=True)

    def update_annotation(
        self,
        image_id: str,
        annotation_id: str,
        annotation: Annotation,
        *,
        expected_revision: int | None = None,
    ) -> LabelDocument:
        with self._lock:
            current = self.get(image_id)
            self._check_revision(current, expected_revision)
            index = next(
                (i for i, item in enumerate(current.annotations) if item.annotation_id == annotation_id),
                None,
            )
            if index is None:
                raise AnnotationNotFoundError(f"annotation does not exist: {annotation_id}")
            if annotation.annotation_id is not None and annotation.annotation_id != annotation_id:
                raise ValueError("annotation.annotation_id must match the annotation id in the URL")

            annotations = list(current.annotations)
            annotations[index] = _with_annotation_id(annotation, annotation_id)
            updated = current.model_copy(
                update={
                    "annotations": annotations,
                    "revision": current.revision + 1,
                    "updated_at": _utc_now(),
                },
                deep=True,
            )
            updated = LabelDocument.model_validate(updated.model_dump(mode="python"))
            self._store.save(updated)
            return updated.model_copy(deep=True)

    def delete_annotation(
        self,
        image_id: str,
        annotation_id: str,
        *,
        expected_revision: int | None = None,
    ) -> LabelDocument:
        with self._lock:
            current = self.get(image_id)
            self._check_revision(current, expected_revision)
            if not any(item.annotation_id == annotation_id for item in current.annotations):
                raise AnnotationNotFoundError(f"annotation does not exist: {annotation_id}")
            annotations = [
                item for item in current.annotations if item.annotation_id != annotation_id
            ]
            updated = current.model_copy(
                update={
                    "annotations": annotations,
                    "revision": current.revision + 1,
                    "updated_at": _utc_now(),
                },
                deep=True,
            )
            updated = LabelDocument.model_validate(updated.model_dump(mode="python"))
            self._store.save(updated)
            return updated.model_copy(deep=True)

    def list_classes(self) -> list[LabelClassSummary]:
        documents = self._store.load_all()
        annotation_counts: Counter[str] = Counter()
        image_ids_by_label: dict[str, set[str]] = defaultdict(set)
        for document in documents:
            for annotation in document.annotations:
                annotation_counts[annotation.label] += 1
                image_ids_by_label[annotation.label].add(document.image_id)

        return [
            LabelClassSummary(
                label=label,
                annotation_count=annotation_counts[label],
                image_count=len(image_ids_by_label[label]),
            )
            for label in sorted(annotation_counts)
        ]
