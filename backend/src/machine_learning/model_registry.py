from __future__ import annotations

from threading import RLock

from .schemas import ModelData, ModelSpec


class DuplicateModelError(ValueError):
    pass


class ModelNotFoundError(KeyError):
    pass


class ModelRegistry:
    """학습 모델을 ID/semantic version으로 보관하는 thread-safe registry."""

    def __init__(self) -> None:
        self._models: dict[tuple[str, str], ModelData] = {}
        self._lock = RLock()

    def register(self, model: ModelData, *, replace: bool = False) -> None:
        key = (model.spec.model_id, model.spec.version)
        with self._lock:
            if key in self._models and not replace:
                raise DuplicateModelError(
                    f"model is already registered: {key[0]}@{key[1]}"
                )
            self._models[key] = model

    def get(self, model_id: str, version: str) -> ModelData:
        key = (model_id, version)
        with self._lock:
            model = self._models.get(key)
        if model is None:
            raise ModelNotFoundError(f"model is not registered: {model_id}@{version}")
        return model

    def list_specs(self) -> list[ModelSpec]:
        with self._lock:
            models = [self._models[key] for key in sorted(self._models)]
        return [item.spec.model_copy(deep=True) for item in models]

    def unregister(self, model_id: str, version: str) -> None:
        key = (model_id, version)
        with self._lock:
            if key not in self._models:
                raise ModelNotFoundError(
                    f"model is not registered: {model_id}@{version}"
                )
            del self._models[key]
