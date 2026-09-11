from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from uuid import uuid4

from .errors import (
    DuplicateTestDatasetError,
    TestDatasetImageNotFoundError,
    TestDatasetNotFoundError,
    TestDatasetRevisionConflictError,
)
from .schemas import (
    AddImagesRequest,
    BatchGroundTruthRequest,
    FolderImportRequest,
    FolderImportResult,
    GroundTruthLabel,
    TestDatasetCreateRequest,
    TestDatasetImage,
    TestDatasetImagePage,
    TestDatasetRecord,
    TestDatasetSummary,
    TestDatasetUpdateRequest,
    UpdateTestImageRequest,
)
from .store import TestDatasetStore


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TestDatasetService:
    def __init__(self, store: TestDatasetStore, *, max_images: int = 100_000) -> None:
        self._store = store
        self._max_images = max_images
        self._lock = RLock()

    @staticmethod
    def summarize(record: TestDatasetRecord) -> TestDatasetSummary:
        ok_count = sum(item.ground_truth == GroundTruthLabel.OK for item in record.images)
        ng_count = sum(item.ground_truth == GroundTruthLabel.NG for item in record.images)
        return TestDatasetSummary(
            dataset_id=record.dataset_id,
            name=record.name,
            description=record.description,
            root_path=record.root_path,
            image_count=len(record.images),
            ok_count=ok_count,
            ng_count=ng_count,
            unlabeled_count=len(record.images) - ok_count - ng_count,
            revision=record.revision,
            updated_at=record.updated_at,
        )

    @staticmethod
    def _check_revision(record: TestDatasetRecord, expected_revision: int | None) -> None:
        if expected_revision is not None and expected_revision != record.revision:
            raise TestDatasetRevisionConflictError(
                f"test dataset revision conflict: expected {expected_revision}, current {record.revision}"
            )

    def list(self, *, search: str | None = None) -> list[TestDatasetSummary]:
        records = self._store.load_all()
        normalized = search.casefold().strip() if search else None
        if normalized:
            records = [
                item for item in records
                if normalized in " ".join(filter(None, [item.dataset_id, item.name, item.description])).casefold()
            ]
        records.sort(key=lambda item: (item.updated_at, item.dataset_id), reverse=True)
        return [self.summarize(item) for item in records]

    def get(self, dataset_id: str) -> TestDatasetRecord:
        record = self._store.load(dataset_id)
        if record is None:
            raise TestDatasetNotFoundError(f"test dataset does not exist: {dataset_id}")
        return record.model_copy(deep=True)

    def list_images(
        self,
        dataset_id: str,
        *,
        offset: int,
        limit: int,
        ground_truth: GroundTruthLabel | None = None,
        unlabeled_only: bool = False,
        search: str | None = None,
    ) -> TestDatasetImagePage:
        record = self.get(dataset_id)
        images = record.images
        if ground_truth is not None:
            images = [item for item in images if item.ground_truth == ground_truth]
        if unlabeled_only:
            images = [item for item in images if item.ground_truth is None]
        normalized = search.casefold().strip() if search else None
        if normalized:
            images = [
                item for item in images
                if normalized in " ".join(
                    filter(None, [item.image_id, item.file_path, item.relative_path, " ".join(item.tags)])
                ).casefold()
            ]
        total = len(images)
        return TestDatasetImagePage(
            items=[item.model_copy(deep=True) for item in images[offset:offset + limit]],
            total=total,
            offset=offset,
            limit=limit,
        )

    def create(self, request: TestDatasetCreateRequest) -> TestDatasetRecord:
        with self._lock:
            dataset_id = request.dataset_id or uuid4().hex
            if self._store.load(dataset_id) is not None:
                raise DuplicateTestDatasetError(f"test dataset already exists: {dataset_id}")
            now = _utc_now()
            root = None
            if request.root_path:
                root = str(Path(request.root_path).expanduser().resolve())
            record = TestDatasetRecord(
                dataset_id=dataset_id,
                name=request.name,
                description=request.description,
                root_path=root,
                images=[],
                revision=1,
                created_at=now,
                updated_at=now,
            )
            self._store.save(record)
            return record.model_copy(deep=True)

    def update(self, dataset_id: str, request: TestDatasetUpdateRequest) -> TestDatasetRecord:
        with self._lock:
            current = self.get(dataset_id)
            self._check_revision(current, request.expected_revision)
            root = None
            if request.root_path:
                root = str(Path(request.root_path).expanduser().resolve())
            updated = current.model_copy(
                update={
                    "name": request.name,
                    "description": request.description,
                    "root_path": root,
                    "revision": current.revision + 1,
                    "updated_at": _utc_now(),
                },
                deep=True,
            )
            updated = TestDatasetRecord.model_validate(updated.model_dump(mode="python"))
            self._store.save(updated)
            return updated.model_copy(deep=True)

    def delete(self, dataset_id: str, *, expected_revision: int | None = None) -> None:
        with self._lock:
            current = self.get(dataset_id)
            self._check_revision(current, expected_revision)
            self._store.delete(dataset_id)

    def import_folder(self, dataset_id: str, request: FolderImportRequest) -> FolderImportResult:
        with self._lock:
            current = self.get(dataset_id)
            self._check_revision(current, request.expected_revision)
            root = Path(request.folder_path).expanduser().resolve()
            if not root.is_dir():
                raise ValueError(f"folder does not exist: {root}")
            iterator = root.rglob("*") if request.recursive else root.glob("*")
            paths = sorted(
                path.resolve() for path in iterator
                if path.is_file() and path.suffix.lower() in set(request.extensions)
            )
            if len(paths) > self._max_images:
                raise ValueError(f"folder contains too many images: {len(paths)} > {self._max_images}")

            existing_by_path = {Path(item.file_path).resolve(): item for item in current.images}
            images = list(current.images)
            index_by_path = {Path(item.file_path).resolve(): index for index, item in enumerate(images)}
            added = replaced = skipped = auto_labeled = unlabeled = 0

            for path in paths:
                label = self._infer_label(path, root, request) if request.auto_label_from_parent else None
                if label is not None:
                    auto_labeled += 1
                else:
                    unlabeled += 1
                relative = path.relative_to(root).as_posix()
                item = TestDatasetImage(
                    image_id=(existing_by_path[path].image_id if path in existing_by_path else uuid4().hex),
                    file_path=str(path),
                    relative_path=relative,
                    ground_truth=label,
                    file_size_bytes=path.stat().st_size,
                    tags=(existing_by_path[path].tags if path in existing_by_path else []),
                    metadata=(existing_by_path[path].metadata if path in existing_by_path else {}),
                )
                if path in index_by_path:
                    if request.replace_existing:
                        images[index_by_path[path]] = item
                        replaced += 1
                    else:
                        skipped += 1
                else:
                    images.append(item)
                    index_by_path[path] = len(images) - 1
                    added += 1

            if len(images) > self._max_images:
                raise ValueError(f"test dataset exceeds image limit: {len(images)} > {self._max_images}")
            updated = current.model_copy(
                update={
                    "root_path": str(root),
                    "images": images,
                    "revision": current.revision + 1,
                    "updated_at": _utc_now(),
                },
                deep=True,
            )
            updated = TestDatasetRecord.model_validate(updated.model_dump(mode="python"))
            self._store.save(updated)
            return FolderImportResult(
                dataset=self.summarize(updated),
                discovered=len(paths),
                added=added,
                replaced=replaced,
                skipped_duplicates=skipped,
                auto_labeled=auto_labeled,
                unlabeled=unlabeled,
            )

    @staticmethod
    def _infer_label(path: Path, root: Path, request: FolderImportRequest) -> GroundTruthLabel | None:
        try:
            relative_parent = path.parent.relative_to(root)
        except ValueError:
            return None
        for part in reversed(relative_parent.parts):
            label = request.label_mapping.get(part.casefold())
            if label is not None:
                return label
        return None

    def add_images(self, dataset_id: str, request: AddImagesRequest) -> TestDatasetRecord:
        with self._lock:
            current = self.get(dataset_id)
            self._check_revision(current, request.expected_revision)
            existing = {Path(item.file_path).resolve() for item in current.images}
            images = list(current.images)
            root = Path(current.root_path).resolve() if current.root_path else None
            for raw in request.file_paths:
                path = Path(raw).expanduser().resolve()
                if not path.is_file():
                    raise ValueError(f"image file does not exist: {path}")
                if path in existing:
                    continue
                relative = None
                if root is not None:
                    try:
                        relative = path.relative_to(root).as_posix()
                    except ValueError:
                        relative = None
                images.append(TestDatasetImage(
                    image_id=uuid4().hex,
                    file_path=str(path),
                    relative_path=relative,
                    ground_truth=request.ground_truth,
                    file_size_bytes=path.stat().st_size,
                ))
                existing.add(path)
            if len(images) > self._max_images:
                raise ValueError(f"test dataset exceeds image limit: {len(images)} > {self._max_images}")
            return self._save_images_update(current, images)

    def update_image(
        self, dataset_id: str, image_id: str, request: UpdateTestImageRequest
    ) -> TestDatasetRecord:
        with self._lock:
            current = self.get(dataset_id)
            self._check_revision(current, request.expected_revision)
            images = list(current.images)
            index = next((i for i, item in enumerate(images) if item.image_id == image_id), None)
            if index is None:
                raise TestDatasetImageNotFoundError(f"test dataset image does not exist: {image_id}")
            images[index] = images[index].model_copy(
                update={
                    "ground_truth": request.ground_truth,
                    "tags": request.tags,
                    "metadata": request.metadata,
                },
                deep=True,
            )
            return self._save_images_update(current, images)

    def batch_ground_truth(
        self, dataset_id: str, request: BatchGroundTruthRequest
    ) -> TestDatasetRecord:
        with self._lock:
            current = self.get(dataset_id)
            self._check_revision(current, request.expected_revision)
            requested = set(request.image_ids)
            known = {item.image_id for item in current.images}
            missing = sorted(requested - known)
            if missing:
                raise TestDatasetImageNotFoundError(f"test dataset images do not exist: {missing[:20]}")
            images = [
                item.model_copy(update={"ground_truth": request.ground_truth}, deep=True)
                if item.image_id in requested else item
                for item in current.images
            ]
            return self._save_images_update(current, images)

    def delete_image(
        self, dataset_id: str, image_id: str, *, expected_revision: int | None = None
    ) -> TestDatasetRecord:
        with self._lock:
            current = self.get(dataset_id)
            self._check_revision(current, expected_revision)
            if not any(item.image_id == image_id for item in current.images):
                raise TestDatasetImageNotFoundError(f"test dataset image does not exist: {image_id}")
            images = [item for item in current.images if item.image_id != image_id]
            return self._save_images_update(current, images)

    def _save_images_update(
        self, current: TestDatasetRecord, images: list[TestDatasetImage]
    ) -> TestDatasetRecord:
        updated = current.model_copy(
            update={
                "images": images,
                "revision": current.revision + 1,
                "updated_at": _utc_now(),
            },
            deep=True,
        )
        updated = TestDatasetRecord.model_validate(updated.model_dump(mode="python"))
        self._store.save(updated)
        return updated.model_copy(deep=True)
