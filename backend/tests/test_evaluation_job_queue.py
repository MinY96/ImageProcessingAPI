from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.evaluation import (
    DatasetSnapshot,
    EvaluationActiveError,
    EvaluationEngine,
    EvaluationItemResult,
    EvaluationJobManager,
    EvaluationPrediction,
    EvaluationProgress,
    EvaluationRequest,
    EvaluationRun,
    EvaluationRunNotFoundError,
    EvaluationRunStore,
    EvaluationStatus,
    GroundTruthLabel,
    RecipeSnapshot,
    TestDatasetImage as DatasetImage,
    TestDatasetRecord as DatasetRecord,
)
from src.evaluation.engine import EvaluationExecutionResult, EvaluationPreparation


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _dataset(count: int = 20) -> DatasetRecord:
    now = _utc_now()
    return DatasetRecord(
        dataset_id="queue_dataset",
        name="Queue Dataset",
        images=[
            DatasetImage(
                image_id=f"img_{index}",
                file_path=f"/tmp/img_{index}.png",
                ground_truth=GroundTruthLabel.OK,
            )
            for index in range(count)
        ],
        revision=1,
        created_at=now,
        updated_at=now,
    )


class _FakeDatasetService:
    def __init__(self, dataset: DatasetRecord) -> None:
        self.dataset = dataset

    def get(self, dataset_id: str) -> DatasetRecord:
        assert dataset_id == self.dataset.dataset_id
        return self.dataset.model_copy(deep=True)


class _SlowFakeEngine:
    summarize = EvaluationEngine.summarize

    def __init__(self, delay_seconds: float = 0.01) -> None:
        self.delay_seconds = delay_seconds
        self.recipe = RecipeSnapshot(
            name="queue_recipe",
            kind="graph",
            version="1.0.0",
            revision=1,
        )

    def prepare(
        self, dataset: DatasetRecord, request: EvaluationRequest
    ) -> EvaluationPreparation:
        assert request.recipe_name == self.recipe.name
        labeled = sum(item.ground_truth is not None for item in dataset.images)
        return EvaluationPreparation(
            dataset=DatasetSnapshot(
                dataset_id=dataset.dataset_id,
                name=dataset.name,
                revision=dataset.revision,
                image_count=len(dataset.images),
            ),
            recipe=self.recipe,
            labeled_images=labeled,
        )

    def run(
        self,
        dataset: DatasetRecord,
        request: EvaluationRequest,
        *,
        expected_recipe: RecipeSnapshot | None = None,
        progress_callback=None,
        should_cancel=None,
    ) -> EvaluationExecutionResult:
        assert expected_recipe == self.recipe
        results: list[EvaluationItemResult] = []
        cancelled = False
        for item in dataset.images:
            if should_cancel is not None and should_cancel():
                cancelled = True
                break
            time.sleep(self.delay_seconds)
            results.append(
                EvaluationItemResult(
                    image_id=item.image_id,
                    file_path=item.file_path,
                    ground_truth=GroundTruthLabel.OK,
                    prediction=EvaluationPrediction.OK,
                    correct=True,
                    duration_ms=self.delay_seconds * 1000,
                )
            )
            if progress_callback is not None:
                progress_callback(len(results), len(dataset.images), results)
        return EvaluationExecutionResult(
            summary=self.summarize(total_images=len(dataset.images), results=results),
            results=results,
            cancelled=cancelled,
        )


def _manager(tmp_path: Path, *, delay_seconds: float = 0.01) -> EvaluationJobManager:
    dataset = _dataset()
    return EvaluationJobManager(
        dataset_service=_FakeDatasetService(dataset),
        engine=_SlowFakeEngine(delay_seconds=delay_seconds),
        store=EvaluationRunStore(tmp_path / "evaluations"),
        checkpoint_interval=2,
        worker_count=1,
    )


def _request() -> EvaluationRequest:
    return EvaluationRequest(
        dataset_id="queue_dataset",
        recipe_name="queue_recipe",
        score_output=None,
    )


def test_queued_job_can_be_cancelled_and_active_job_cannot_be_deleted(tmp_path: Path):
    manager = _manager(tmp_path)
    accepted = manager.submit(_request())
    assert accepted.status == EvaluationStatus.QUEUED

    with pytest.raises(EvaluationActiveError):
        manager.delete(accepted.evaluation_id)

    cancelled = manager.cancel(accepted.evaluation_id)
    assert cancelled.status == EvaluationStatus.CANCELLED
    assert cancelled.finished_at is not None

    manager.delete(accepted.evaluation_id)
    with pytest.raises(EvaluationRunNotFoundError):
        manager.get(accepted.evaluation_id)


def test_running_job_reports_progress_and_cancels_between_items(tmp_path: Path):
    manager = _manager(tmp_path, delay_seconds=0.01)
    manager.start()
    try:
        accepted = manager.submit(_request())
        deadline = time.monotonic() + 3.0
        running = None
        while time.monotonic() < deadline:
            current = manager.get(accepted.evaluation_id)
            if current.status == EvaluationStatus.RUNNING and current.progress.processed > 0:
                running = current
                break
            time.sleep(0.005)
        assert running is not None

        requested = manager.cancel(accepted.evaluation_id)
        assert requested.status == EvaluationStatus.CANCEL_REQUESTED

        deadline = time.monotonic() + 3.0
        terminal = None
        while time.monotonic() < deadline:
            current = manager.get(accepted.evaluation_id)
            if current.status in {
                EvaluationStatus.CANCELLED,
                EvaluationStatus.FAILED,
                EvaluationStatus.COMPLETED,
            }:
                terminal = current
                break
            time.sleep(0.005)

        assert terminal is not None
        assert terminal.status == EvaluationStatus.CANCELLED
        assert 0 < terminal.progress.processed < terminal.progress.total
        assert len(terminal.results) == terminal.progress.processed
    finally:
        manager.shutdown()


def test_startup_marks_orphaned_running_job_as_failed(tmp_path: Path):
    store = EvaluationRunStore(tmp_path / "evaluations")
    dataset = _dataset()
    preparation = _SlowFakeEngine().prepare(dataset, _request())
    orphan = EvaluationRun(
        evaluation_id="orphaned_run",
        status=EvaluationStatus.RUNNING,
        progress=EvaluationProgress(total=20, processed=3, percent=15.0),
        dataset=preparation.dataset,
        recipe=preparation.recipe,
        request=_request(),
        created_at=_utc_now(),
        started_at=_utc_now(),
    )
    store.save(orphan)

    manager = EvaluationJobManager(
        dataset_service=_FakeDatasetService(dataset),
        engine=_SlowFakeEngine(),
        store=store,
        checkpoint_interval=2,
        worker_count=1,
    )
    manager.start()
    try:
        recovered = manager.get("orphaned_run")
        assert recovered.status == EvaluationStatus.FAILED
        assert recovered.failure is not None
        assert recovered.failure.code == "application_terminated"
        assert recovered.finished_at is not None
    finally:
        manager.shutdown()
