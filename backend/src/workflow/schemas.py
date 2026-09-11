from __future__ import annotations

import re
from enum import StrEnum
from typing import Annotated, Any, Literal, TypeAlias

from pydantic import Field, field_validator, model_validator

from src.schemas.base import BaseSchema
from src.schemas.parameter import ParameterSpec
from src.schemas.result import ExecutionMetadata, OperationError, OperationOutput


_NAME_PATTERN = r"^[a-z][a-z0-9_]*$"


class WorkflowDataKind(StrEnum):
    IMAGE = "image"
    MASK = "mask"
    TEMPLATE = "template"
    ARRAY = "array"
    CONTOURS = "contours"
    METRICS = "metrics"
    SCALAR = "scalar"
    PROFILE = "profile"
    ROI = "roi"
    ROI_SET = "roi_set"
    BOOLEAN = "boolean"
    DECISION = "decision"


class WorkflowNodeType(StrEnum):
    OPERATION = "operation"
    FEATURE = "feature"
    SCALAR_OPERATOR = "scalar_operator"
    ROI_CROP = "roi_crop"
    ROI_COMPOSE = "roi_compose"
    DECISION = "decision"
    SUBRECIPE = "subrecipe"


class WorkflowPortSpec(BaseSchema):
    name: str = Field(pattern=_NAME_PATTERN)
    kind: WorkflowDataKind
    required: bool = True
    description: str | None = None


class GraphInputReference(BaseSchema):
    type: Literal["graph_input"] = "graph_input"
    input_name: str = Field(pattern=_NAME_PATTERN)


class NodeOutputReference(BaseSchema):
    type: Literal["node_output"] = "node_output"
    node_id: str = Field(pattern=_NAME_PATTERN)
    output_name: str = Field(pattern=_NAME_PATTERN)


GraphValueReference: TypeAlias = Annotated[
    GraphInputReference | NodeOutputReference,
    Field(discriminator="type"),
]


class WorkflowNodeBase(BaseSchema):
    id: str = Field(pattern=_NAME_PATTERN)
    inputs: dict[str, GraphValueReference] = Field(default_factory=dict)
    params: dict[str, Any] = Field(default_factory=dict)

    @field_validator("inputs")
    @classmethod
    def validate_input_names(
        cls, value: dict[str, GraphValueReference]
    ) -> dict[str, GraphValueReference]:
        pattern = re.compile(_NAME_PATTERN)
        invalid = [name for name in value if not pattern.fullmatch(name)]
        if invalid:
            raise ValueError(f"invalid node input names: {invalid}")
        return value


class OperationNodeSpec(WorkflowNodeBase):
    node_type: Literal[WorkflowNodeType.OPERATION] = WorkflowNodeType.OPERATION
    operation: str = Field(pattern=_NAME_PATTERN)


class FeatureNodeSpec(WorkflowNodeBase):
    node_type: Literal[WorkflowNodeType.FEATURE] = WorkflowNodeType.FEATURE
    feature: str = Field(pattern=_NAME_PATTERN)


class ScalarOperatorNodeSpec(WorkflowNodeBase):
    node_type: Literal[WorkflowNodeType.SCALAR_OPERATOR] = (
        WorkflowNodeType.SCALAR_OPERATOR
    )
    operator: str = Field(pattern=_NAME_PATTERN)


class RoiCropNodeSpec(WorkflowNodeBase):
    node_type: Literal[WorkflowNodeType.ROI_CROP] = WorkflowNodeType.ROI_CROP


class RoiComposeNodeSpec(WorkflowNodeBase):
    node_type: Literal[WorkflowNodeType.ROI_COMPOSE] = WorkflowNodeType.ROI_COMPOSE


class DecisionNodeSpec(WorkflowNodeBase):
    node_type: Literal[WorkflowNodeType.DECISION] = WorkflowNodeType.DECISION


class SubRecipeNodeSpec(WorkflowNodeBase):
    node_type: Literal[WorkflowNodeType.SUBRECIPE] = WorkflowNodeType.SUBRECIPE
    recipe: str = Field(pattern=_NAME_PATTERN)
    recipe_kind: Literal["auto", "linear", "graph"] = "auto"
    recipe_version: str | None = None


WorkflowNodeSpec: TypeAlias = Annotated[
    OperationNodeSpec
    | FeatureNodeSpec
    | ScalarOperatorNodeSpec
    | RoiCropNodeSpec
    | RoiComposeNodeSpec
    | DecisionNodeSpec
    | SubRecipeNodeSpec,
    Field(discriminator="node_type"),
]


class GraphRecipeSpec(BaseSchema):
    name: str = Field(pattern=_NAME_PATTERN)
    display_name: str
    description: str | None = None
    version: str = "1.0.0"
    inputs: list[WorkflowPortSpec] = Field(default_factory=list)
    nodes: list[WorkflowNodeSpec] = Field(min_length=1, max_length=200)
    outputs: dict[str, GraphValueReference] = Field(default_factory=dict)

    @field_validator("outputs")
    @classmethod
    def validate_output_names(
        cls, value: dict[str, GraphValueReference]
    ) -> dict[str, GraphValueReference]:
        pattern = re.compile(_NAME_PATTERN)
        invalid = [name for name in value if not pattern.fullmatch(name)]
        if invalid:
            raise ValueError(f"invalid graph output names: {invalid}")
        return value

    @model_validator(mode="after")
    def validate_unique_names(self) -> "GraphRecipeSpec":
        input_names = [item.name for item in self.inputs]
        if len(input_names) != len(set(input_names)):
            raise ValueError("graph input names must be unique")
        node_ids = [item.id for item in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("graph node ids must be unique")
        return self


class FeatureSpec(BaseSchema):
    name: str = Field(pattern=_NAME_PATTERN)
    display_name: str
    category: str
    description: str | None = None
    version: str = "1.0.0"
    inputs: list[WorkflowPortSpec]
    parameters: dict[str, ParameterSpec] = Field(default_factory=dict)
    outputs: list[WorkflowPortSpec]


class ScalarOperatorSpec(BaseSchema):
    name: str = Field(pattern=_NAME_PATTERN)
    display_name: str
    description: str | None = None
    min_inputs: int = Field(ge=1)
    max_inputs: int | None = Field(default=None, ge=1)
    required_input_names: list[str] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)


class WorkflowNodeExecution(BaseSchema):
    node_id: str
    node_type: WorkflowNodeType
    target: str | None = None
    success: bool
    metadata: ExecutionMetadata
    error: OperationError | None = None


class WorkflowError(BaseSchema):
    code: str
    message: str
    node_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class WorkflowExecutionResult(BaseSchema):
    recipe: str
    success: bool
    output: OperationOutput = Field(default_factory=OperationOutput)
    nodes: list[WorkflowNodeExecution] = Field(default_factory=list)
    intermediates: dict[str, OperationOutput] = Field(default_factory=dict)
    metadata: ExecutionMetadata
    error: WorkflowError | None = None

    @model_validator(mode="after")
    def validate_success_error(self) -> "WorkflowExecutionResult":
        if self.success and self.error is not None:
            raise ValueError("successful workflow must not contain error")
        if not self.success and self.error is None:
            raise ValueError("failed workflow must contain error")
        return self


class WorkflowValidationIssue(BaseSchema):
    location: str
    code: str
    message: str
    value: Any | None = None


class WorkflowValidationResponse(BaseSchema):
    valid: bool
    recipe: str
    execution_order: list[str] = Field(default_factory=list)
    output_names: list[str] = Field(default_factory=list)
    error: dict[str, Any] | None = None
