from __future__ import annotations

from datetime import datetime, timezone
from queue import Queue
from threading import Event, RLock, Thread
from uuid import uuid4

from ..dataset_service import TestDatasetService
from ..engine import EvaluationEngine
from ..errors import (
    EvaluationActiveError,
    EvaluationRunNotFoundError,
    EvaluationValidationError,
)
from ..schemas import (
    EvaluationFailureInfo,
    EvaluationJobAccepted,
    EvaluationProgress,
    EvaluationRequest,
    EvaluationRun,
    EvaluationStatus,
)
from ..store import EvaluationRunStore


_TERMINAL_STATUSES = {
    EvaluationStatus.COMPLETED,
    EvaluationStatus.FAILED,
    EvaluationStatus.CANCELLED,
}
_ACTIVE_STATUSES = {
    EvaluationStatus.QUEUED,
    EvaluationStatus.RUNNING,
    EvaluationStatus.CANCEL_REQUESTED,
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _progress(total: int, processed: int) -> EvaluationProgress:
    percent = 100.0 if total == 0 else min(100.0, (processed / total) * 100.0)
    return EvaluationProgress(total=total, processed=processed, percent=percent)


class EvaluationJobManager:
    """Single-PC in-process evaluation queue.

    The API thread only validates/snapshots the submission and enqueues an id.
    Dedicated worker thread(s) execute heavy evaluations. Live progress is held
    in memory while complete result checkpoints are persisted periodically.
    """

    def __init__(
        self,
        *,
        dataset_service: TestDatasetService,
        engine: EvaluationEngine,
        store: EvaluationRunStore,
        checkpoint_interval: int = 50,
        worker_count: int = 1,
    ) -> None:
        if checkpoint_interval < 1:
            raise ValueError("checkpoint_interval must be >= 1")
        if worker_count < 1:
            raise ValueError("worker_count must be >= 1")

        self._dataset_service = dataset_service
        self._engine = engine
        self._store = store
        self._checkpoint_interval = checkpoint_interval
        self._worker_count = worker_count

        self._queue: Queue[str | None] = Queue()
        self._lock = RLock()
        self._stop_event = Event()
        self._started = False
        self._threads: list[Thread] = []
        self._live_runs: dict[str, EvaluationRun] = {}
        self._cancel_events: dict[str, Event] = {}

    def start(self) -> None:
        with self._lock:
            if self._started:
                return
            self._stop_event.clear()
            self._recover_persisted_jobs()
            self._threads = [
                Thread(
                    target=self._worker_loop,
                    name=f"evaluation-worker-{index + 1}",
                    daemon=True,
                )
                for index in range(self._worker_count)
            ]
            self._started = True
            for thread in self._threads:
                thread.start()

    def shutdown(self, *, timeout_seconds: float = 5.0) -> None:
        with self._lock:
            if not self._started:
                return
            self._stop_event.set()
            threads = list(self._threads)
            for _ in threads:
                self._queue.put(None)

        for thread in threads:
            thread.join(timeout=timeout_seconds)

        with self._lock:
            self._threads.clear()
            self._started = False

    def submit(self, request: EvaluationRequest) -> EvaluationJobAccepted:
        dataset = self._dataset_service.get(request.dataset_id)
        preparation = self._engine.prepare(dataset, request)
        now = _utc_now()
        run = EvaluationRun(
            evaluation_id=uuid4().hex,
            status=EvaluationStatus.QUEUED,
            progress=_progress(preparation.labeled_images, 0),
            dataset=preparation.dataset,
            recipe=preparation.recipe,
            request=request,
            summary=None,
            results=[],
            created_at=now,
        )
        self._store.save(run)
        with self._lock:
            self._live_runs[run.evaluation_id] = run
            self._cancel_events[run.evaluation_id] = Event()
        self._queue.put(run.evaluation_id)
        return EvaluationJobAccepted(
            evaluation_id=run.evaluation_id,
            status=run.status,
            progress=run.progress,
            created_at=run.created_at,
        )

    def get(self, evaluation_id: str) -> EvaluationRun:
        with self._lock:
            live = self._live_runs.get(evaluation_id)
            if live is not None:
                return live.model_copy(deep=True)
        run = self._store.load(evaluation_id)
        if run is None:
            raise EvaluationRunNotFoundError(
                f"evaluation run does not exist: {evaluation_id}"
            )
        return run.model_copy(deep=True)

    def load_all(self) -> list[EvaluationRun]:
        runs = {item.evaluation_id: item for item in self._store.load_all()}
        with self._lock:
            for evaluation_id, live in self._live_runs.items():
                runs[evaluation_id] = live.model_copy(deep=True)
        return list(runs.values())

    def cancel(self, evaluation_id: str) -> EvaluationRun:
        with self._lock:
            run = self._live_runs.get(evaluation_id)
            if run is None:
                run = self._store.load(evaluation_id)
                if run is None:
                    raise EvaluationRunNotFoundError(
                        f"evaluation run does not exist: {evaluation_id}"
                    )

            if run.status in _TERMINAL_STATUSES:
                return run.model_copy(deep=True)

            if run.status == EvaluationStatus.QUEUED:
                run.status = EvaluationStatus.CANCELLED
                run.finished_at = _utc_now()
                self._live_runs.pop(evaluation_id, None)
                self._cancel_events.pop(evaluation_id, None)
                snapshot = run.model_copy(deep=True)
            else:
                run.status = EvaluationStatus.CANCEL_REQUESTED
                cancel_event = self._cancel_events.setdefault(evaluation_id, Event())
                cancel_event.set()
                self._live_runs[evaluation_id] = run
                snapshot = run.model_copy(deep=True)

        self._store.save(snapshot)
        return snapshot.model_copy(deep=True)

    def delete(self, evaluation_id: str) -> None:
        run = self.get(evaluation_id)
        if run.status in _ACTIVE_STATUSES:
            raise EvaluationActiveError(
                f"active evaluation cannot be deleted; cancel it first: {evaluation_id}"
            )
        with self._lock:
            self._live_runs.pop(evaluation_id, None)
            self._cancel_events.pop(evaluation_id, None)
        self._store.delete(evaluation_id)

    def _recover_persisted_jobs(self) -> None:
        for run in self._store.load_all():
            if run.status == EvaluationStatus.QUEUED:
                self._live_runs[run.evaluation_id] = run
                self._cancel_events[run.evaluation_id] = Event()
                self._queue.put(run.evaluation_id)
                continue
            if run.status in {
                EvaluationStatus.RUNNING,
                EvaluationStatus.CANCEL_REQUESTED,
            }:
                run.status = EvaluationStatus.FAILED
                run.failure = EvaluationFailureInfo(
                    code="application_terminated",
                    message=(
                        "Application terminated while evaluation was running. "
                        "Submit a new evaluation to run it again."
                    ),
                )
                run.finished_at = _utc_now()
                self._store.save(run)

    def _worker_loop(self) -> None:
        while True:
            evaluation_id = self._queue.get()
            try:
                if evaluation_id is None:
                    return
                if self._stop_event.is_set():
                    # Leave queued jobs untouched so they can be restored next start.
                    continue
                self._run_job(evaluation_id)
            finally:
                self._queue.task_done()

    def _run_job(self, evaluation_id: str) -> None:
        with self._lock:
            run = self._live_runs.get(evaluation_id)
            if run is None:
                run = self._store.load(evaluation_id)
                if run is not None:
                    self._live_runs[evaluation_id] = run
            if run is None or run.status != EvaluationStatus.QUEUED:
                return

            cancel_event = self._cancel_events.setdefault(evaluation_id, Event())
            run.status = EvaluationStatus.RUNNING
            run.started_at = _utc_now()
            run.failure = None
            running_snapshot = run.model_copy(deep=True)

        self._store.save(running_snapshot)

        try:
            dataset = self._dataset_service.get(run.dataset.dataset_id)
            if dataset.revision != run.dataset.revision:
                raise EvaluationValidationError(
                    "test dataset changed after evaluation was queued; submit a new evaluation "
                    f"(queued revision={run.dataset.revision}, current revision={dataset.revision})"
                )

            def should_cancel() -> bool:
                return self._stop_event.is_set() or cancel_event.is_set()

            def on_progress(processed: int, total: int, results) -> None:
                checkpoint = processed % self._checkpoint_interval == 0 or processed == total
                with self._lock:
                    live = self._live_runs[evaluation_id]
                    live.progress = _progress(total, processed)
                    if checkpoint:
                        live.results = list(results)
                        live.summary = self._engine.summarize(
                            total_images=live.dataset.image_count,
                            results=live.results,
                        )
                        snapshot = live.model_copy(deep=True)
                    else:
                        snapshot = None
                if snapshot is not None:
                    self._store.save(snapshot)

            outcome = self._engine.run(
                dataset,
                run.request,
                expected_recipe=run.recipe,
                progress_callback=on_progress,
                should_cancel=should_cancel,
            )

            with self._lock:
                live = self._live_runs[evaluation_id]
                live.results = list(outcome.results)
                live.summary = outcome.summary
                live.progress = _progress(live.progress.total, len(outcome.results))
                live.finished_at = _utc_now()

                if self._stop_event.is_set():
                    live.status = EvaluationStatus.FAILED
                    live.failure = EvaluationFailureInfo(
                        code="application_shutdown",
                        message="Application shut down while evaluation was running.",
                    )
                elif outcome.cancelled or cancel_event.is_set():
                    live.status = EvaluationStatus.CANCELLED
                    live.failure = None
                else:
                    live.status = EvaluationStatus.COMPLETED
                    live.progress = _progress(live.progress.total, live.progress.total)
                    live.failure = None
                final = live.model_copy(deep=True)
            self._store.save(final)
        except Exception as exc:
            self._mark_failed(evaluation_id, exc)
        finally:
            with self._lock:
                self._live_runs.pop(evaluation_id, None)
                self._cancel_events.pop(evaluation_id, None)

    def _mark_failed(self, evaluation_id: str, exc: Exception) -> None:
        with self._lock:
            run = self._live_runs.get(evaluation_id)
            if run is None:
                run = self._store.load(evaluation_id)
            if run is None:
                return
            run.status = EvaluationStatus.FAILED
            run.failure = EvaluationFailureInfo(
                code=(
                    "evaluation_validation_error"
                    if isinstance(exc, EvaluationValidationError)
                    else "evaluation_execution_error"
                ),
                message=str(exc) or type(exc).__name__,
            )
            run.finished_at = _utc_now()
            snapshot = run.model_copy(deep=True)
        self._store.save(snapshot)
