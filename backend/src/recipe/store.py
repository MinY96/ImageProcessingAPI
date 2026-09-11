from __future__ import annotations

import os
from pathlib import Path
from threading import RLock

from pydantic import ValidationError

from .errors import RecipeStoreError
from .schemas import RecipeRecord


class RecipeStore:
    """사용자 Recipe를 JSON 파일로 영속화한다.

    Pipeline 이름은 스키마에서 안전한 식별자로 제한되므로 그대로 파일명으로 사용한다.
    쓰기는 같은 디렉터리의 임시 파일을 거쳐 os.replace()로 원자적으로 교체한다.
    """

    def __init__(self, directory: Path) -> None:
        self.directory = Path(directory)
        self._lock = RLock()

    def _path(self, name: str) -> Path:
        return self.directory / f"{name}.json"

    def load_all(self) -> list[RecipeRecord]:
        with self._lock:
            if not self.directory.exists():
                return []

            records: list[RecipeRecord] = []
            for path in sorted(self.directory.glob("*.json")):
                try:
                    records.append(RecipeRecord.model_validate_json(path.read_text(encoding="utf-8")))
                except (OSError, ValidationError, ValueError) as exc:
                    raise RecipeStoreError(
                        f"failed to load recipe file: {path.name}: {exc}"
                    ) from exc
            return records

    def save(self, record: RecipeRecord) -> None:
        with self._lock:
            self.directory.mkdir(parents=True, exist_ok=True)
            path = self._path(record.name)
            temp_path = path.with_suffix(".json.tmp")
            try:
                with temp_path.open("w", encoding="utf-8", newline="\n") as handle:
                    handle.write(record.model_dump_json(indent=2))
                    handle.write("\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temp_path, path)
            except OSError as exc:
                try:
                    temp_path.unlink(missing_ok=True)
                except OSError:
                    pass
                raise RecipeStoreError(f"failed to save recipe: {record.name}: {exc}") from exc

    def delete(self, name: str) -> None:
        with self._lock:
            try:
                self._path(name).unlink(missing_ok=True)
            except OSError as exc:
                raise RecipeStoreError(f"failed to delete recipe: {name}: {exc}") from exc
