from __future__ import annotations

import hashlib
import os
from pathlib import Path
from threading import RLock

from pydantic import ValidationError

from .errors import LabelStoreError
from .schemas import LabelDocument


class LabelStore:
    """이미지별 LabelDocument를 JSON 파일로 저장한다.

    image_id를 직접 경로로 사용하지 않고 SHA-256 파일명으로 변환해 경로 조작 가능성을 제거한다.
    """

    def __init__(self, directory: Path) -> None:
        self.directory = Path(directory)
        self._lock = RLock()

    @staticmethod
    def _digest(image_id: str) -> str:
        return hashlib.sha256(image_id.encode("utf-8")).hexdigest()

    def _path(self, image_id: str) -> Path:
        return self.directory / f"{self._digest(image_id)}.json"

    def load(self, image_id: str) -> LabelDocument | None:
        with self._lock:
            path = self._path(image_id)
            if not path.exists():
                return None
            try:
                document = LabelDocument.model_validate_json(path.read_text(encoding="utf-8"))
            except (OSError, ValidationError, ValueError) as exc:
                raise LabelStoreError(f"failed to load label file: {path.name}: {exc}") from exc
            if document.image_id != image_id:
                raise LabelStoreError(
                    f"label store hash collision or corrupt file for image_id: {image_id}"
                )
            return document

    def load_all(self) -> list[LabelDocument]:
        with self._lock:
            if not self.directory.exists():
                return []
            documents: list[LabelDocument] = []
            for path in sorted(self.directory.glob("*.json")):
                try:
                    documents.append(
                        LabelDocument.model_validate_json(path.read_text(encoding="utf-8"))
                    )
                except (OSError, ValidationError, ValueError) as exc:
                    raise LabelStoreError(
                        f"failed to load label file: {path.name}: {exc}"
                    ) from exc
            return documents

    def save(self, document: LabelDocument) -> None:
        with self._lock:
            self.directory.mkdir(parents=True, exist_ok=True)
            path = self._path(document.image_id)
            temp_path = path.with_suffix(".json.tmp")
            try:
                with temp_path.open("w", encoding="utf-8", newline="\n") as handle:
                    handle.write(document.model_dump_json(indent=2))
                    handle.write("\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temp_path, path)
            except OSError as exc:
                try:
                    temp_path.unlink(missing_ok=True)
                except OSError:
                    pass
                raise LabelStoreError(
                    f"failed to save label document: {document.image_id}: {exc}"
                ) from exc

    def delete(self, image_id: str) -> None:
        with self._lock:
            try:
                self._path(image_id).unlink(missing_ok=True)
            except OSError as exc:
                raise LabelStoreError(
                    f"failed to delete label document: {image_id}: {exc}"
                ) from exc
