from __future__ import annotations

from .jobs import EvaluationJobManager
from .schemas import (
    EvaluationJobAccepted,
    EvaluationPrediction,
    EvaluationRequest,
    EvaluationResultPage,
    EvaluationRun,
    EvaluationRunSummary,
    EvaluationStatus,
    GroundTruthLabel,
)


class EvaluationService:
    def __init__(self, job_manager: EvaluationJobManager) -> None:
        self._jobs = job_manager

    @staticmethod
    def _summary(run: EvaluationRun) -> EvaluationRunSummary:
        return EvaluationRunSummary(
            evaluation_id=run.evaluation_id,
            status=run.status,
            progress=run.progress,
            dataset=run.dataset,
            recipe=run.recipe,
            summary=run.summary,
            failure=run.failure,
            created_at=run.created_at,
            started_at=run.started_at,
            finished_at=run.finished_at,
        )

    def list(
        self,
        *,
        dataset_id: str | None = None,
        recipe_name: str | None = None,
        status: EvaluationStatus | None = None,
    ) -> list[EvaluationRunSummary]:
        runs = self._jobs.load_all()
        if dataset_id is not None:
            runs = [item for item in runs if item.dataset.dataset_id == dataset_id]
        if recipe_name is not None:
            runs = [item for item in runs if item.recipe.name == recipe_name]
        if status is not None:
            runs = [item for item in runs if item.status == status]
        runs.sort(key=lambda item: (item.created_at, item.evaluation_id), reverse=True)
        return [self._summary(item) for item in runs]

    def create(self, request: EvaluationRequest) -> EvaluationJobAccepted:
        return self._jobs.submit(request)

    def get(self, evaluation_id: str) -> EvaluationRun:
        return self._jobs.get(evaluation_id)

    def cancel(self, evaluation_id: str) -> EvaluationRun:
        return self._jobs.cancel(evaluation_id)

    def delete(self, evaluation_id: str) -> None:
        self._jobs.delete(evaluation_id)

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
        return EvaluationResultPage(
            items=items[offset : offset + limit],
            total=total,
            offset=offset,
            limit=limit,
        )
