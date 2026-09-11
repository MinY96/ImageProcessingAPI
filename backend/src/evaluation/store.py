from __future__ import annotations

import hashlib
import os
from pathlib import Path
from threading import RLock

from pydantic import ValidationError

from .errors import EvaluationStoreError, TestDatasetStoreError
from .schemas import EvaluationRun, TestDatasetRecord


class _JsonStoreBase:
    def __init__(self, directory: Path) -> None:
        self.directory = Path(directory)
        self._lock = RLock()

    @staticmethod
    def _digest(identifier: str) -> str:
        return hashlib.sha256(identifier.encode("utf-8")).hexdigest()

    def _path(self, identifier: str) -> Path:
        return self.directory / f"{self._digest(identifier)}.json"

    def _write_atomic(self, path: Path, text: str, error_type, message: str) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(".json.tmp")
        try:
            with temp_path.open("w", encoding="utf-8", newline="\n") as handle:
                handle.write(text)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, path)
        except OSError as exc:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise error_type(f"{message}: {exc}") from exc


class TestDatasetStore(_JsonStoreBase):
    def load(self, dataset_id: str) -> TestDatasetRecord | None:
        with self._lock:
            path = self._path(dataset_id)
            if not path.exists():
                return None
            try:
                record = TestDatasetRecord.model_validate_json(path.read_text(encoding="utf-8"))
            except (OSError, ValidationError, ValueError) as exc:
                raise TestDatasetStoreError(f"failed to load test dataset: {exc}") from exc
            if record.dataset_id != dataset_id:
                raise TestDatasetStoreError("test dataset store hash collision or corrupt file")
            return record

    def load_all(self) -> list[TestDatasetRecord]:
        with self._lock:
            if not self.directory.exists():
                return []
            records: list[TestDatasetRecord] = []
            for path in sorted(self.directory.glob("*.json")):
                try:
                    records.append(TestDatasetRecord.model_validate_json(path.read_text(encoding="utf-8")))
                except (OSError, ValidationError, ValueError) as exc:
                    raise TestDatasetStoreError(f"failed to load test dataset {path.name}: {exc}") from exc
            return records

    def save(self, record: TestDatasetRecord) -> None:
        with self._lock:
            self._write_atomic(
                self._path(record.dataset_id),
                record.model_dump_json(indent=2),
                TestDatasetStoreError,
                f"failed to save test dataset: {record.dataset_id}",
            )

    def delete(self, dataset_id: str) -> None:
        with self._lock:
            try:
                self._path(dataset_id).unlink(missing_ok=True)
            except OSError as exc:
                raise TestDatasetStoreError(f"failed to delete test dataset: {dataset_id}: {exc}") from exc


class EvaluationRunStore(_JsonStoreBase):
    def load(self, evaluation_id: str) -> EvaluationRun | None:
        with self._lock:
            path = self._path(evaluation_id)
            if not path.exists():
                return None
            try:
                run = EvaluationRun.model_validate_json(path.read_text(encoding="utf-8"))
            except (OSError, ValidationError, ValueError) as exc:
                raise EvaluationStoreError(f"failed to load evaluation run: {exc}") from exc
            if run.evaluation_id != evaluation_id:
                raise EvaluationStoreError("evaluation store hash collision or corrupt file")
            return run

    def load_all(self) -> list[EvaluationRun]:
        with self._lock:
            if not self.directory.exists():
                return []
            runs: list[EvaluationRun] = []
            for path in sorted(self.directory.glob("*.json")):
                try:
                    runs.append(EvaluationRun.model_validate_json(path.read_text(encoding="utf-8")))
                except (OSError, ValidationError, ValueError) as exc:
                    raise EvaluationStoreError(f"failed to load evaluation run {path.name}: {exc}") from exc
            return runs

    def save(self, run: EvaluationRun) -> None:
        with self._lock:
            self._write_atomic(
                self._path(run.evaluation_id),
                run.model_dump_json(indent=2),
                EvaluationStoreError,
                f"failed to save evaluation run: {run.evaluation_id}",
            )

    def delete(self, evaluation_id: str) -> None:
        with self._lock:
            try:
                self._path(evaluation_id).unlink(missing_ok=True)
            except OSError as exc:
                raise EvaluationStoreError(f"failed to delete evaluation run: {evaluation_id}: {exc}") from exc
