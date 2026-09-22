from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import Field, field_validator, model_validator

from src.schemas.base import BaseSchema


_DATASET_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$"
_IMAGE_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$"


class GroundTruthLabel(StrEnum):
    OK = "OK"
    NG = "NG"


class EvaluationPrediction(StrEnum):
    OK = "OK"
    NG = "NG"
    ERROR = "ERROR"


class EvaluationStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELLED = "cancelled"


class TestDatasetImage(BaseSchema):
    image_id: str = Field(pattern=_IMAGE_ID_PATTERN)
    file_path: str = Field(min_length=1, max_length=4096)
    relative_path: str | None = Field(default=None, max_length=4096)
    ground_truth: GroundTruthLabel | None = None
    file_size_bytes: int | None = Field(default=None, ge=0)
    tags: list[str] = Field(default_factory=list, max_length=32)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})


class TestDatasetRecord(BaseSchema):
    dataset_id: str = Field(pattern=_DATASET_ID_PATTERN)
    name: str = Field(min_length=1, max_length=256)
    description: str | None = None
    root_path: str | None = Field(default=None, max_length=4096)
    images: list[TestDatasetImage] = Field(default_factory=list)
    revision: int = Field(default=1, ge=1)
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def validate_unique_images(self) -> "TestDatasetRecord":
        ids = [item.image_id for item in self.images]
        if len(ids) != len(set(ids)):
            raise ValueError("image_id values must be unique within a test dataset")
        paths = [item.file_path.casefold() for item in self.images]
        if len(paths) != len(set(paths)):
            raise ValueError("file_path values must be unique within a test dataset")
        return self


class TestDatasetCreateRequest(BaseSchema):
    dataset_id: str | None = Field(default=None, pattern=_DATASET_ID_PATTERN)
    name: str = Field(min_length=1, max_length=256)
    description: str | None = None
    root_path: str | None = Field(default=None, max_length=4096)


class TestDatasetUpdateRequest(BaseSchema):
    name: str = Field(min_length=1, max_length=256)
    description: str | None = None
    root_path: str | None = Field(default=None, max_length=4096)
    expected_revision: int | None = Field(default=None, ge=1)


class TestDatasetSummary(BaseSchema):
    dataset_id: str
    name: str
    description: str | None = None
    root_path: str | None = None
    image_count: int = Field(ge=0)
    ok_count: int = Field(ge=0)
    ng_count: int = Field(ge=0)
    unlabeled_count: int = Field(ge=0)
    revision: int = Field(ge=1)
    updated_at: datetime


class TestDatasetImagePage(BaseSchema):
    items: list[TestDatasetImage]
    total: int = Field(ge=0)
    offset: int = Field(ge=0)
    limit: int = Field(ge=1)


class FolderImportRequest(BaseSchema):
    folder_path: str = Field(min_length=1, max_length=4096)
    recursive: bool = True
    extensions: list[str] = Field(
        default_factory=lambda: [".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"],
        min_length=1,
        max_length=32,
    )
    auto_label_from_parent: bool = True
    label_mapping: dict[str, GroundTruthLabel] = Field(
        default_factory=lambda: {"ok": GroundTruthLabel.OK, "ng": GroundTruthLabel.NG}
    )
    replace_existing: bool = False
    expected_revision: int | None = Field(default=None, ge=1)

    @field_validator("extensions")
    @classmethod
    def normalize_extensions(cls, value: list[str]) -> list[str]:
        normalized = []
        for item in value:
            ext = item.strip().lower()
            if not ext:
                continue
            if not ext.startswith("."):
                ext = f".{ext}"
            normalized.append(ext)
        if not normalized:
            raise ValueError("at least one image extension is required")
        return sorted(set(normalized))

    @field_validator("label_mapping")
    @classmethod
    def normalize_label_mapping(
        cls, value: dict[str, GroundTruthLabel]
    ) -> dict[str, GroundTruthLabel]:
        return {key.strip().casefold(): label for key, label in value.items() if key.strip()}


class FolderImportResult(BaseSchema):
    dataset: TestDatasetSummary
    discovered: int = Field(ge=0)
    added: int = Field(ge=0)
    replaced: int = Field(ge=0)
    skipped_duplicates: int = Field(ge=0)
    auto_labeled: int = Field(ge=0)
    unlabeled: int = Field(ge=0)


class AddImagesRequest(BaseSchema):
    file_paths: list[str] = Field(min_length=1, max_length=10_000)
    ground_truth: GroundTruthLabel | None = None
    expected_revision: int | None = Field(default=None, ge=1)


class UpdateTestImageRequest(BaseSchema):
    ground_truth: GroundTruthLabel | None = None
    tags: list[str] = Field(default_factory=list, max_length=32)
    metadata: dict[str, Any] = Field(default_factory=dict)
    expected_revision: int | None = Field(default=None, ge=1)

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})


class BatchGroundTruthRequest(BaseSchema):
    image_ids: list[str] = Field(min_length=1, max_length=100_000)
    ground_truth: GroundTruthLabel | None
    expected_revision: int | None = Field(default=None, ge=1)


class EvaluationRequest(BaseSchema):
    dataset_id: str = Field(pattern=_DATASET_ID_PATTERN)
    recipe_name: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    image_input_name: str = Field(default="image", pattern=r"^[a-z][a-z0-9_]*$")
    decision_output: str = Field(default="result", pattern=r"^[a-z][a-z0-9_]*$")
    score_output: str | None = Field(default="score", pattern=r"^[a-z][a-z0-9_]*$")
    ok_label: str = Field(default="OK", min_length=1, max_length=128)
    ng_label: str = Field(default="NG", min_length=1, max_length=128)
    shared_image_inputs: dict[str, str] = Field(default_factory=dict)
    constant_inputs: dict[str, Any] = Field(default_factory=dict)
    capture_node_values: bool = True
    fail_on_unlabeled: bool = True

    @model_validator(mode="after")
    def validate_labels_and_inputs(self) -> "EvaluationRequest":
        if self.ok_label == self.ng_label:
            raise ValueError("ok_label and ng_label must be different")
        if self.image_input_name in self.shared_image_inputs or self.image_input_name in self.constant_inputs:
            raise ValueError("image_input_name cannot also be a shared/constant input")
        conflicts = set(self.shared_image_inputs) & set(self.constant_inputs)
        if conflicts:
            raise ValueError(f"shared_image_inputs and constant_inputs conflict: {sorted(conflicts)}")
        return self


class EvaluationErrorInfo(BaseSchema):
    code: str
    message: str


class EvaluationItemResult(BaseSchema):
    image_id: str
    file_path: str
    relative_path: str | None = None
    ground_truth: GroundTruthLabel
    prediction: EvaluationPrediction
    score: float | None = None
    correct: bool | None = None
    duration_ms: float = Field(ge=0)
    feature_values: dict[str, Any] = Field(default_factory=dict)
    error: EvaluationErrorInfo | None = None


class ConfusionMatrix(BaseSchema):
    tp: int = Field(ge=0)
    tn: int = Field(ge=0)
    fp: int = Field(ge=0)
    fn: int = Field(ge=0)


class ClassificationMetrics(BaseSchema):
    accuracy: float | None = Field(default=None, ge=0, le=1)
    precision: float | None = Field(default=None, ge=0, le=1)
    recall: float | None = Field(default=None, ge=0, le=1)
    specificity: float | None = Field(default=None, ge=0, le=1)
    f1: float | None = Field(default=None, ge=0, le=1)


class LatencySummary(BaseSchema):
    count: int = Field(ge=0)
    total_ms: float = Field(ge=0)
    mean_ms: float | None = Field(default=None, ge=0)
    median_ms: float | None = Field(default=None, ge=0)
    p95_ms: float | None = Field(default=None, ge=0)
    max_ms: float | None = Field(default=None, ge=0)


class ScoreGroupSummary(BaseSchema):
    count: int = Field(ge=0)
    minimum: float | None = None
    maximum: float | None = None
    mean: float | None = None
    median: float | None = None
    std: float | None = Field(default=None, ge=0)


class EvaluationSummary(BaseSchema):
    total_images: int = Field(ge=0)
    labeled_images: int = Field(ge=0)
    evaluated_images: int = Field(ge=0)
    error_images: int = Field(ge=0)
    execution_success_rate: float | None = Field(default=None, ge=0, le=1)
    confusion_matrix: ConfusionMatrix
    metrics: ClassificationMetrics
    latency: LatencySummary
    ok_scores: ScoreGroupSummary
    ng_scores: ScoreGroupSummary


class RecipeSnapshot(BaseSchema):
    name: str
    kind: str
    version: str
    revision: int = Field(ge=1)


class DatasetSnapshot(BaseSchema):
    dataset_id: str
    name: str
    revision: int = Field(ge=1)
    image_count: int = Field(ge=0)


class EvaluationProgress(BaseSchema):
    total: int = Field(default=0, ge=0)
    processed: int = Field(default=0, ge=0)
    percent: float = Field(default=0.0, ge=0, le=100)

    @model_validator(mode="after")
    def validate_processed(self) -> "EvaluationProgress":
        if self.processed > self.total:
            raise ValueError("processed cannot exceed total")
        return self


class EvaluationFailureInfo(BaseSchema):
    code: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1)


class EvaluationRun(BaseSchema):
    evaluation_id: str
    status: EvaluationStatus = EvaluationStatus.COMPLETED
    progress: EvaluationProgress = Field(default_factory=EvaluationProgress)
    dataset: DatasetSnapshot
    recipe: RecipeSnapshot
    request: EvaluationRequest
    summary: EvaluationSummary | None = None
    results: list[EvaluationItemResult] = Field(default_factory=list)
    failure: EvaluationFailureInfo | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None

    @model_validator(mode="after")
    def normalize_legacy_completed_run(self) -> "EvaluationRun":
        # EvaluationRun files created before the job-queue migration did not
        # persist status/progress. Keep them readable as completed runs.
        if (
            self.status == EvaluationStatus.COMPLETED
            and self.progress.total == 0
            and self.summary is not None
        ):
            total = self.summary.labeled_images
            self.progress = EvaluationProgress(
                total=total,
                processed=total,
                percent=100.0 if total else 100.0,
            )
        return self


class EvaluationRunSummary(BaseSchema):
    evaluation_id: str
    status: EvaluationStatus
    progress: EvaluationProgress
    dataset: DatasetSnapshot
    recipe: RecipeSnapshot
    summary: EvaluationSummary | None = None
    failure: EvaluationFailureInfo | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class EvaluationJobAccepted(BaseSchema):
    evaluation_id: str
    status: EvaluationStatus
    progress: EvaluationProgress
    created_at: datetime


class EvaluationResultPage(BaseSchema):
    items: list[EvaluationItemResult]
    total: int = Field(ge=0)
    offset: int = Field(ge=0)
    limit: int = Field(ge=1)
