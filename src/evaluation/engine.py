from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import mean, median, pstdev
from typing import Any, Callable

from src.media_io import read_image
from src.pipeline import PipelineCatalog, PipelineExecutor
from src.recipe import RecipeKind, RecipeService
from src.workflow import DecisionNodeSpec, WorkflowCatalog, WorkflowExecutor

from .errors import EvaluationValidationError
from .schemas import (
    ClassificationMetrics,
    ConfusionMatrix,
    DatasetSnapshot,
    EvaluationErrorInfo,
    EvaluationItemResult,
    EvaluationPrediction,
    EvaluationRequest,
    EvaluationSummary,
    GroundTruthLabel,
    LatencySummary,
    RecipeSnapshot,
    ScoreGroupSummary,
    TestDatasetRecord,
)


ProgressCallback = Callable[[int, int, list[EvaluationItemResult]], None]
CancelCallback = Callable[[], bool]


@dataclass(frozen=True, slots=True)
class EvaluationPreparation:
    dataset: DatasetSnapshot
    recipe: RecipeSnapshot
    labeled_images: int


@dataclass(frozen=True, slots=True)
class EvaluationExecutionResult:
    summary: EvaluationSummary
    results: list[EvaluationItemResult]
    cancelled: bool


def _safe_div(numerator: float, denominator: float) -> float | None:
    return numerator / denominator if denominator else None


def _percentile_nearest(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(q * len(ordered)) - 1))
    return float(ordered[index])


class EvaluationEngine:
    def __init__(
        self,
        *,
        recipe_service: RecipeService,
        pipeline_executor: PipelineExecutor,
        pipeline_catalog: PipelineCatalog,
        workflow_executor: WorkflowExecutor,
        workflow_catalog: WorkflowCatalog,
        max_image_pixels: int,
    ) -> None:
        self._recipe_service = recipe_service
        self._pipeline_executor = pipeline_executor
        self._pipeline_catalog = pipeline_catalog
        self._workflow_executor = workflow_executor
        self._workflow_catalog = workflow_catalog
        self._max_image_pixels = max_image_pixels

    def prepare(self, dataset: TestDatasetRecord, request: EvaluationRequest) -> EvaluationPreparation:
        record = self._recipe_service.get(request.recipe_name)
        artifact = record.pipeline if record.kind == RecipeKind.LINEAR else record.graph
        assert artifact is not None
        self._validate_recipe(record, request)

        unlabeled = [item.image_id for item in dataset.images if item.ground_truth is None]
        if request.fail_on_unlabeled and unlabeled:
            raise EvaluationValidationError(
                f"test dataset contains {len(unlabeled)} unlabeled image(s); "
                "label them or set fail_on_unlabeled=false"
            )
        labeled_images = [item for item in dataset.images if item.ground_truth is not None]
        if not labeled_images:
            raise EvaluationValidationError("test dataset contains no labeled images")

        return EvaluationPreparation(
            dataset=DatasetSnapshot(
                dataset_id=dataset.dataset_id,
                name=dataset.name,
                revision=dataset.revision,
                image_count=len(dataset.images),
            ),
            recipe=RecipeSnapshot(
                name=record.name,
                kind=record.kind.value,
                version=artifact.version,
                revision=record.revision,
            ),
            labeled_images=len(labeled_images),
        )

    def run(
        self,
        dataset: TestDatasetRecord,
        request: EvaluationRequest,
        *,
        expected_recipe: RecipeSnapshot | None = None,
        progress_callback: ProgressCallback | None = None,
        should_cancel: CancelCallback | None = None,
    ) -> EvaluationExecutionResult:
        preparation = self.prepare(dataset, request)
        if expected_recipe is not None and preparation.recipe != expected_recipe:
            raise EvaluationValidationError(
                "recipe changed after evaluation was queued; submit a new evaluation "
                f"(queued revision={expected_recipe.revision}, current revision={preparation.recipe.revision})"
            )

        labeled_images = [item for item in dataset.images if item.ground_truth is not None]
        shared_images: dict[str, Any] = {}
        for input_name, path in request.shared_image_inputs.items():
            shared_images[input_name] = read_image(path, max_pixels=self._max_image_pixels)

        results: list[EvaluationItemResult] = []
        total = len(labeled_images)
        cancelled = False

        for item in labeled_images:
            if should_cancel is not None and should_cancel():
                cancelled = True
                break

            assert item.ground_truth is not None
            try:
                image = read_image(item.file_path, max_pixels=self._max_image_pixels)
                inputs = dict(request.constant_inputs)
                inputs.update(shared_images)
                inputs[request.image_input_name] = image
                result = self._execute_recipe(
                    preparation.recipe.kind,
                    request.recipe_name,
                    inputs,
                    retain_intermediates=request.capture_node_values,
                )
                if not result.success:
                    error = result.error
                    results.append(
                        EvaluationItemResult(
                            image_id=item.image_id,
                            file_path=item.file_path,
                            relative_path=item.relative_path,
                            ground_truth=item.ground_truth,
                            prediction=EvaluationPrediction.ERROR,
                            duration_ms=result.metadata.duration_ms,
                            feature_values=self._extract_feature_values(result.intermediates),
                            error=EvaluationErrorInfo(
                                code=getattr(error, "code", "recipe_execution_failed"),
                                message=getattr(error, "message", "recipe execution failed"),
                            ),
                        )
                    )
                else:
                    data = result.output.data
                    if request.decision_output not in data:
                        raise EvaluationValidationError(
                            f"recipe output does not contain decision output: {request.decision_output}"
                        )
                    raw_prediction = str(data[request.decision_output])
                    if raw_prediction == request.ok_label:
                        prediction = EvaluationPrediction.OK
                    elif raw_prediction == request.ng_label:
                        prediction = EvaluationPrediction.NG
                    else:
                        raise EvaluationValidationError(
                            f"decision output must be {request.ok_label!r} or {request.ng_label!r}; "
                            f"got {raw_prediction!r}"
                        )

                    score = None
                    if request.score_output is not None:
                        raw_score = data.get(request.score_output)
                        if raw_score is not None:
                            try:
                                score = float(raw_score)
                            except (TypeError, ValueError) as exc:
                                raise EvaluationValidationError(
                                    f"score output {request.score_output!r} is not numeric: {raw_score!r}"
                                ) from exc

                    results.append(
                        EvaluationItemResult(
                            image_id=item.image_id,
                            file_path=item.file_path,
                            relative_path=item.relative_path,
                            ground_truth=item.ground_truth,
                            prediction=prediction,
                            score=score,
                            correct=prediction.value == item.ground_truth.value,
                            duration_ms=result.metadata.duration_ms,
                            feature_values=self._extract_feature_values(result.intermediates),
                        )
                    )
            except EvaluationValidationError:
                raise
            except Exception as exc:
                results.append(
                    EvaluationItemResult(
                        image_id=item.image_id,
                        file_path=item.file_path,
                        relative_path=item.relative_path,
                        ground_truth=item.ground_truth,
                        prediction=EvaluationPrediction.ERROR,
                        duration_ms=0.0,
                        error=EvaluationErrorInfo(
                            code="image_or_recipe_error",
                            message=str(exc) or type(exc).__name__,
                        ),
                    )
                )

            if progress_callback is not None:
                progress_callback(len(results), total, results)

        summary = self.summarize(total_images=len(dataset.images), results=results)
        return EvaluationExecutionResult(summary=summary, results=results, cancelled=cancelled)

    def _validate_recipe(self, record, request: EvaluationRequest) -> None:
        artifact = record.pipeline if record.kind == RecipeKind.LINEAR else record.graph
        assert artifact is not None
        if request.decision_output not in artifact.outputs:
            raise EvaluationValidationError(
                f"recipe does not expose decision output {request.decision_output!r}"
            )
        if request.score_output is not None and request.score_output not in artifact.outputs:
            raise EvaluationValidationError(
                f"recipe does not expose score output {request.score_output!r}"
            )
        input_names = {item.name for item in artifact.inputs}
        supplied_names = {
            request.image_input_name,
            *request.shared_image_inputs.keys(),
            *request.constant_inputs.keys(),
        }
        unknown = sorted(supplied_names - input_names)
        if unknown:
            raise EvaluationValidationError(f"evaluation provides unknown recipe inputs: {unknown}")
        required = {item.name for item in artifact.inputs if getattr(item, "required", True)}
        missing = sorted(required - supplied_names)
        if missing:
            raise EvaluationValidationError(f"evaluation is missing required recipe inputs: {missing}")
        if record.kind == RecipeKind.GRAPH:
            assert record.graph is not None
            if not any(isinstance(node, DecisionNodeSpec) for node in record.graph.nodes):
                raise EvaluationValidationError(
                    "graph recipe must contain a Decision node for evaluation"
                )

    def _execute_recipe(
        self,
        kind: str,
        recipe_name: str,
        inputs: dict[str, Any],
        retain_intermediates: bool,
    ):
        if kind == RecipeKind.LINEAR.value:
            return self._pipeline_executor.execute(
                pipeline=self._pipeline_catalog.get(recipe_name),
                inputs=inputs,
                retain_intermediates=retain_intermediates,
            )
        return self._workflow_executor.execute(
            recipe=self._workflow_catalog.get(recipe_name),
            inputs=inputs,
            retain_intermediates=retain_intermediates,
        )

    @staticmethod
    def _extract_feature_values(intermediates: dict[str, Any]) -> dict[str, Any]:
        flattened: dict[str, Any] = {}
        for node_id, output in intermediates.items():
            for name, value in output.data.items():
                if isinstance(value, (str, bool, int, float)) or value is None:
                    flattened[f"{node_id}.{name}"] = value
        return flattened

    @classmethod
    def summarize(
        cls, *, total_images: int, results: list[EvaluationItemResult]
    ) -> EvaluationSummary:
        successful = [item for item in results if item.prediction != EvaluationPrediction.ERROR]
        errors = len(results) - len(successful)
        tp = sum(
            item.ground_truth == GroundTruthLabel.NG
            and item.prediction == EvaluationPrediction.NG
            for item in successful
        )
        tn = sum(
            item.ground_truth == GroundTruthLabel.OK
            and item.prediction == EvaluationPrediction.OK
            for item in successful
        )
        fp = sum(
            item.ground_truth == GroundTruthLabel.OK
            and item.prediction == EvaluationPrediction.NG
            for item in successful
        )
        fn = sum(
            item.ground_truth == GroundTruthLabel.NG
            and item.prediction == EvaluationPrediction.OK
            for item in successful
        )
        matrix = ConfusionMatrix(tp=tp, tn=tn, fp=fp, fn=fn)
        accuracy = _safe_div(tp + tn, len(successful))
        precision = _safe_div(tp, tp + fp)
        recall = _safe_div(tp, tp + fn)
        specificity = _safe_div(tn, tn + fp)
        f1 = None
        if precision is not None and recall is not None and precision + recall:
            f1 = 2 * precision * recall / (precision + recall)
        durations = [item.duration_ms for item in results]
        latency = LatencySummary(
            count=len(durations),
            total_ms=float(sum(durations)),
            mean_ms=float(mean(durations)) if durations else None,
            median_ms=float(median(durations)) if durations else None,
            p95_ms=_percentile_nearest(durations, 0.95),
            max_ms=float(max(durations)) if durations else None,
        )
        return EvaluationSummary(
            total_images=total_images,
            labeled_images=len(results),
            evaluated_images=len(successful),
            error_images=errors,
            execution_success_rate=_safe_div(len(successful), len(results)),
            confusion_matrix=matrix,
            metrics=ClassificationMetrics(
                accuracy=accuracy,
                precision=precision,
                recall=recall,
                specificity=specificity,
                f1=f1,
            ),
            latency=latency,
            ok_scores=cls._score_group(results, GroundTruthLabel.OK),
            ng_scores=cls._score_group(results, GroundTruthLabel.NG),
        )

    @staticmethod
    def _score_group(
        results: list[EvaluationItemResult], label: GroundTruthLabel
    ) -> ScoreGroupSummary:
        values = [
            item.score
            for item in results
            if item.ground_truth == label and item.score is not None
        ]
        if not values:
            return ScoreGroupSummary(count=0)
        numeric = [float(value) for value in values]
        return ScoreGroupSummary(
            count=len(numeric),
            minimum=min(numeric),
            maximum=max(numeric),
            mean=float(mean(numeric)),
            median=float(median(numeric)),
            std=float(pstdev(numeric)) if len(numeric) > 1 else 0.0,
        )
