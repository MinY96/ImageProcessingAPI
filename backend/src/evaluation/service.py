from __future__ import annotations

from .dataset_service import TestDatasetService
from .engine import EvaluationEngine
from .errors import EvaluationRunNotFoundError
from .schemas import (
    EvaluationPrediction,
    EvaluationRequest,
    EvaluationResultPage,
    EvaluationRun,
    EvaluationRunSummary,
    GroundTruthLabel,
)
from .store import EvaluationRunStore


class EvaluationService:
    def __init__(
        self,
        *,
        dataset_service: TestDatasetService,
        engine: EvaluationEngine,
        store: EvaluationRunStore,
    ) -> None:
        self._dataset_service = dataset_service
        self._engine = engine
        self._store = store

    @staticmethod
    def _summary(run: EvaluationRun) -> EvaluationRunSummary:
        return EvaluationRunSummary(
            evaluation_id=run.evaluation_id,
            dataset=run.dataset,
            recipe=run.recipe,
            summary=run.summary,
            created_at=run.created_at,
        )

    def list(self, *, dataset_id: str | None = None, recipe_name: str | None = None) -> list[EvaluationRunSummary]:
        runs = self._store.load_all()
        if dataset_id is not None:
            runs = [item for item in runs if item.dataset.dataset_id == dataset_id]
        if recipe_name is not None:
            runs = [item for item in runs if item.recipe.name == recipe_name]
        runs.sort(key=lambda item: (item.created_at, item.evaluation_id), reverse=True)
        return [self._summary(item) for item in runs]

    def create(self, request: EvaluationRequest) -> EvaluationRun:
        dataset = self._dataset_service.get(request.dataset_id)
        run = self._engine.run(dataset, request)
        self._store.save(run)
        return run.model_copy(deep=True)

    def get(self, evaluation_id: str) -> EvaluationRun:
        run = self._store.load(evaluation_id)
        if run is None:
            raise EvaluationRunNotFoundError(f"evaluation run does not exist: {evaluation_id}")
        return run.model_copy(deep=True)

    def delete(self, evaluation_id: str) -> None:
        self.get(evaluation_id)
        self._store.delete(evaluation_id)

    def results(
        self,
        evaluation_id: str,
        *,
        offset: int,
        limit: int,
        prediction: EvaluationPrediction | None = None,
        ground_truth: GroundTruthLabel | None = None,
        correct: bool | None = None,
        errors_only: bool = False,
    ) -> EvaluationResultPage:
        run = self.get(evaluation_id)
        items = run.results
        if prediction is not None:
            items = [item for item in items if item.prediction == prediction]
        if ground_truth is not None:
            items = [item for item in items if item.ground_truth == ground_truth]
        if correct is not None:
            items = [item for item in items if item.correct is correct]
        if errors_only:
            items = [item for item in items if item.prediction == EvaluationPrediction.ERROR]
        total = len(items)
        return EvaluationResultPage(items=items[offset:offset + limit], total=total, offset=offset, limit=limit)
