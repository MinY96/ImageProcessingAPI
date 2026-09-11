from __future__ import annotations

import time
from collections import Counter
from collections.abc import Mapping
from typing import Any

import numpy as np

from src.pipeline import PipelineCatalog, PipelineExecutor
from src.registry import OperationRegistry
from src.schemas import ColorSpace, ExecutionMetadata, ImageData, OperationError, OperationOutput
from src.workflow.compiler import CompiledWorkflow, WorkflowCompiler
from src.workflow.errors import WorkflowValidationError
from src.workflow.feature_registry import FeatureRegistry
from src.workflow.operator_registry import ScalarOperatorRegistry
from src.workflow.schemas import (
    DecisionNodeSpec,
    FeatureNodeSpec,
    GraphInputReference,
    GraphRecipeSpec,
    GraphValueReference,
    NodeOutputReference,
    OperationNodeSpec,
    RoiComposeNodeSpec,
    RoiCropNodeSpec,
    ScalarOperatorNodeSpec,
    SubRecipeNodeSpec,
    WorkflowDataKind,
    WorkflowError,
    WorkflowExecutionResult,
    WorkflowNodeExecution,
    WorkflowNodeSpec,
)


ReferenceKey = tuple[str, str, str]


class WorkflowExecutor:
    def __init__(
        self,
        *,
        registry: OperationRegistry,
        feature_registry: FeatureRegistry,
        operator_registry: ScalarOperatorRegistry,
        pipeline_executor: PipelineExecutor,
        pipeline_catalog: PipelineCatalog,
    ) -> None:
        self._registry = registry
        self._features = feature_registry
        self._operators = operator_registry
        self._pipeline_executor = pipeline_executor
        self._pipeline_catalog = pipeline_catalog
        self._workflow_catalog = None
        self._compiler = WorkflowCompiler(
            registry=registry,
            feature_registry=feature_registry,
            operator_registry=operator_registry,
            pipeline_executor=pipeline_executor,
            pipeline_catalog=pipeline_catalog,
        )

    def attach_workflow_catalog(self, catalog) -> None:
        self._workflow_catalog = catalog
        self._compiler.attach_workflow_catalog(catalog)

    def compile(self, recipe: GraphRecipeSpec) -> CompiledWorkflow:
        return self._compiler.compile(recipe)

    def execute(
        self,
        *,
        recipe: GraphRecipeSpec | CompiledWorkflow,
        inputs: Mapping[str, Any] | None = None,
        retain_intermediates: bool = False,
    ) -> WorkflowExecutionResult:
        return self._execute(
            recipe=recipe,
            inputs=dict(inputs or {}),
            retain_intermediates=retain_intermediates,
            recipe_stack=(),
        )

    def _execute(
        self,
        *,
        recipe: GraphRecipeSpec | CompiledWorkflow,
        inputs: dict[str, Any],
        retain_intermediates: bool,
        recipe_stack: tuple[str, ...],
    ) -> WorkflowExecutionResult:
        started_at = time.perf_counter()
        try:
            compiled = recipe if isinstance(recipe, CompiledWorkflow) else self._compiler.compile(recipe, recipe_stack=recipe_stack)
        except WorkflowValidationError as exc:
            name = recipe.spec.name if isinstance(recipe, CompiledWorkflow) else recipe.name
            return self._failure(
                recipe=name,
                code="workflow_validation_error",
                message=str(exc),
                details=exc.to_dict(),
                started_at=started_at,
            )

        input_error = self._validate_graph_inputs(compiled, inputs)
        if input_error is not None:
            return self._failure(
                recipe=compiled.spec.name,
                code="workflow_input_validation_error",
                message=input_error,
                details={},
                started_at=started_at,
            )

        node_map = {node.id: node for node in compiled.spec.nodes}
        node_outputs: dict[str, OperationOutput] = {}
        intermediates: dict[str, OperationOutput] = {}
        executions: list[WorkflowNodeExecution] = []
        warnings: list[str] = []
        remaining_uses = self._count_reference_uses(compiled)
        stack = (*recipe_stack, compiled.spec.name)

        for node_id in compiled.execution_order:
            node = node_map[node_id]
            node_started = time.perf_counter()
            resolved_inputs = {
                name: self._resolve_reference(
                    reference=reference,
                    graph_inputs=inputs,
                    node_outputs=node_outputs,
                )[0]
                for name, reference in node.inputs.items()
            }
            try:
                output = self._execute_node(
                    node=node,
                    inputs=resolved_inputs,
                    retain_intermediates=retain_intermediates,
                    recipe_stack=stack,
                )
                execution = WorkflowNodeExecution(
                    node_id=node.id,
                    node_type=node.node_type,
                    target=self._node_target(node),
                    success=True,
                    metadata=ExecutionMetadata(duration_ms=self._elapsed_ms(node_started)),
                )
            except Exception as exc:
                error = OperationError(
                    code="workflow_node_failed",
                    message=str(exc) or "workflow node failed",
                    details={"exception_type": type(exc).__name__},
                )
                executions.append(WorkflowNodeExecution(
                    node_id=node.id,
                    node_type=node.node_type,
                    target=self._node_target(node),
                    success=False,
                    metadata=ExecutionMetadata(duration_ms=self._elapsed_ms(node_started)),
                    error=error,
                ))
                return self._failure(
                    recipe=compiled.spec.name,
                    code="workflow_node_failed",
                    message=f"workflow node failed: {node.id}",
                    node_id=node.id,
                    details={"cause": error.model_dump(mode="json")},
                    nodes=executions,
                    intermediates=intermediates,
                    warnings=warnings,
                    started_at=started_at,
                )

            executions.append(execution)
            if retain_intermediates:
                intermediates[node.id] = output
            self._store_needed_outputs(
                node_id=node.id,
                output=output,
                remaining_uses=remaining_uses,
                node_outputs=node_outputs,
                retain_intermediates=retain_intermediates,
            )
            self._consume_references(
                references=node.inputs.values(),
                remaining_uses=remaining_uses,
                node_outputs=node_outputs,
                retain_intermediates=retain_intermediates,
            )

        final_output = self._build_output(
            bindings=compiled.output_bindings,
            graph_inputs=inputs,
            node_outputs=node_outputs,
        )
        return WorkflowExecutionResult(
            recipe=compiled.spec.name,
            success=True,
            output=final_output,
            nodes=executions,
            intermediates=intermediates,
            metadata=ExecutionMetadata(
                duration_ms=self._elapsed_ms(started_at), warnings=warnings
            ),
        )

    def _execute_node(
        self,
        *,
        node: WorkflowNodeSpec,
        inputs: dict[str, Any],
        retain_intermediates: bool,
        recipe_stack: tuple[str, ...],
    ) -> OperationOutput:
        if isinstance(node, OperationNodeSpec):
            result = self._registry.execute(
                operation=node.operation, inputs=inputs, params=node.params
            )
            if not result.success:
                assert result.error is not None
                raise RuntimeError(f"{result.error.code}: {result.error.message}")
            return result.output
        if isinstance(node, FeatureNodeSpec):
            return self._features.execute(name=node.feature, inputs=inputs, params=node.params)
        if isinstance(node, ScalarOperatorNodeSpec):
            value = self._operators.execute(name=node.operator, inputs=inputs, params=node.params)
            return OperationOutput(data={"value": value})
        if isinstance(node, RoiCropNodeSpec):
            return self._execute_roi_crop(inputs, node.params)
        if isinstance(node, RoiComposeNodeSpec):
            return self._execute_roi_compose(inputs)
        if isinstance(node, DecisionNodeSpec):
            return self._execute_decision(inputs, node.params)
        if isinstance(node, SubRecipeNodeSpec):
            return self._execute_subrecipe(
                node=node,
                inputs=inputs,
                retain_intermediates=retain_intermediates,
                recipe_stack=recipe_stack,
            )
        raise TypeError(type(node).__name__)

    def _execute_subrecipe(
        self,
        *,
        node: SubRecipeNodeSpec,
        inputs: dict[str, Any],
        retain_intermediates: bool,
        recipe_stack: tuple[str, ...],
    ) -> OperationOutput:
        if node.recipe in recipe_stack:
            raise RuntimeError(f"recursive subrecipe dependency: {' -> '.join((*recipe_stack, node.recipe))}")
        graph_available = self._workflow_catalog is not None and self._workflow_catalog.contains(node.recipe)
        linear_available = self._pipeline_catalog.contains(node.recipe)
        use_graph = node.recipe_kind == "graph" or (node.recipe_kind == "auto" and graph_available)
        if use_graph:
            if not graph_available:
                raise RuntimeError(f"graph recipe is not registered: {node.recipe}")
            spec = self._workflow_catalog.get_spec(node.recipe)
            if node.recipe_version is not None and spec.version != node.recipe_version:
                raise RuntimeError(
                    f"subrecipe version mismatch: requested {node.recipe_version}, current {spec.version}"
                )
            result = self._execute(
                recipe=spec,
                inputs=inputs,
                retain_intermediates=False,
                recipe_stack=recipe_stack,
            )
            if not result.success:
                assert result.error is not None
                raise RuntimeError(f"subrecipe failed: {result.error.message}")
            return result.output
        if node.recipe_kind == "linear" or (node.recipe_kind == "auto" and linear_available):
            if not linear_available:
                raise RuntimeError(f"linear recipe is not registered: {node.recipe}")
            compiled = self._pipeline_catalog.get(node.recipe)
            if node.recipe_version is not None and compiled.spec.version != node.recipe_version:
                raise RuntimeError(
                    f"subrecipe version mismatch: requested {node.recipe_version}, current {compiled.spec.version}"
                )
            result = self._pipeline_executor.execute(
                pipeline=compiled,
                inputs=inputs,
                retain_intermediates=False,
            )
            if not result.success:
                assert result.error is not None
                raise RuntimeError(f"subrecipe failed: {result.error.message}")
            return result.output
        raise RuntimeError(f"recipe is not registered: {node.recipe}")

    @staticmethod
    def _execute_roi_crop(inputs: dict[str, Any], params: dict[str, Any]) -> OperationOutput:
        image: ImageData = inputs["image"]
        mode = params.get("coordinate_mode", "pixels")
        if mode == "relative":
            rx = float(params["x"])
            ry = float(params["y"])
            rw = float(params["width"])
            rh = float(params["height"])
            x = int(round(rx * image.width))
            y = int(round(ry * image.height))
            x2 = int(round((rx + rw) * image.width))
            y2 = int(round((ry + rh) * image.height))
            width = x2 - x
            height = y2 - y
        else:
            x, y, width, height = (
                int(params["x"]), int(params["y"]), int(params["width"]), int(params["height"])
            )
        clamp = bool(params.get("clamp", False))
        if clamp:
            x = min(max(x, 0), image.width - 1)
            y = min(max(y, 0), image.height - 1)
            width = min(width, image.width - x)
            height = min(height, image.height - y)
        if x < 0 or y < 0 or width <= 0 or height <= 0 or x + width > image.width or y + height > image.height:
            raise ValueError(
                f"ROI ({x}, {y}, {width}, {height}) is outside image {image.width}x{image.height}"
            )
        patch = image.data[y:y + height, x:x + width].copy()
        roi = ImageData(
            data=patch,
            color_space=image.color_space,
            name=f"{image.name or 'image'}_roi_{x}_{y}_{width}_{height}",
        )
        return OperationOutput(
            images={"image": roi},
            data={
                "region": {
                    "x": x,
                    "y": y,
                    "width": width,
                    "height": height,
                    "source_width": image.width,
                    "source_height": image.height,
                }
            },
        )

    @staticmethod
    def _execute_roi_compose(inputs: dict[str, Any]) -> OperationOutput:
        base: ImageData = inputs["base"]
        patch: ImageData = inputs["patch"]
        region = inputs["region"]
        if not isinstance(region, dict):
            raise ValueError("region must be ROI metadata")
        x, y, width, height = (int(region[key]) for key in ("x", "y", "width", "height"))
        if patch.width != width or patch.height != height:
            raise ValueError(
                f"patch size {patch.width}x{patch.height} does not match ROI {width}x{height}"
            )
        if patch.data.dtype != base.data.dtype or patch.channels != base.channels:
            raise ValueError("patch and base must have the same dtype and channel count")
        if x < 0 or y < 0 or x + width > base.width or y + height > base.height:
            raise ValueError("ROI region is outside base image")
        composed = base.data.copy()
        composed[y:y + height, x:x + width] = patch.data
        return OperationOutput(images={
            "image": ImageData(
                data=composed,
                color_space=base.color_space,
                name=base.name,
            )
        })

    @staticmethod
    def _execute_decision(inputs: dict[str, Any], params: dict[str, Any]) -> OperationOutput:
        value = float(inputs["value"])
        operator = params.get("operator", "gt")
        if operator == "gt":
            passed = value > float(params["threshold"])
        elif operator == "gte":
            passed = value >= float(params["threshold"])
        elif operator == "lt":
            passed = value < float(params["threshold"])
        elif operator == "lte":
            passed = value <= float(params["threshold"])
        elif operator == "inside_range":
            passed = float(params["lower"]) <= value <= float(params["upper"])
        elif operator == "outside_range":
            passed = value < float(params["lower"]) or value > float(params["upper"])
        else:
            raise ValueError(f"unsupported decision operator: {operator}")
        pass_label = str(params.get("pass_label", "OK"))
        fail_label = str(params.get("fail_label", "NG"))
        return OperationOutput(data={
            "value": value,
            "passed": bool(passed),
            "label": pass_label if passed else fail_label,
        })

    @staticmethod
    def _validate_graph_inputs(compiled: CompiledWorkflow, inputs: dict[str, Any]) -> str | None:
        expected = {item.name: item for item in compiled.spec.inputs}
        unknown = sorted(set(inputs) - set(expected))
        if unknown:
            return f"unknown graph inputs: {unknown}"
        missing = sorted(name for name, port in expected.items() if port.required and name not in inputs)
        if missing:
            return f"missing graph inputs: {missing}"
        for name, value in inputs.items():
            if not _runtime_kind_compatible(value, expected[name].kind):
                return f"graph input {name} is incompatible with kind {expected[name].kind.value}"
        return None

    @staticmethod
    def _node_target(node: WorkflowNodeSpec) -> str | None:
        if isinstance(node, OperationNodeSpec):
            return node.operation
        if isinstance(node, FeatureNodeSpec):
            return node.feature
        if isinstance(node, ScalarOperatorNodeSpec):
            return node.operator
        if isinstance(node, SubRecipeNodeSpec):
            return node.recipe
        return None

    @classmethod
    def _count_reference_uses(cls, compiled: CompiledWorkflow) -> Counter[ReferenceKey]:
        references = [ref for node in compiled.spec.nodes for ref in node.inputs.values()]
        references.extend(compiled.output_bindings.values())
        return Counter(cls._reference_key(ref) for ref in references)

    @staticmethod
    def _reference_key(reference: GraphValueReference) -> ReferenceKey:
        if isinstance(reference, GraphInputReference):
            return ("graph_input", reference.input_name, "")
        return ("node_output", reference.node_id, reference.output_name)

    @staticmethod
    def _resolve_reference(*, reference, graph_inputs, node_outputs) -> tuple[Any, bool]:
        if isinstance(reference, GraphInputReference):
            value = graph_inputs[reference.input_name]
            return value, isinstance(value, ImageData)
        output = node_outputs[reference.node_id]
        if reference.output_name in output.images:
            return output.images[reference.output_name], True
        return output.data[reference.output_name], False

    @classmethod
    def _store_needed_outputs(cls, *, node_id, output, remaining_uses, node_outputs, retain_intermediates):
        if retain_intermediates:
            node_outputs[node_id] = output
            return
        images = {name: value for name, value in output.images.items() if remaining_uses[("node_output", node_id, name)] > 0}
        data = {name: value for name, value in output.data.items() if remaining_uses[("node_output", node_id, name)] > 0}
        if images or data:
            node_outputs[node_id] = OperationOutput(images=images, data=data)

    @classmethod
    def _consume_references(cls, *, references, remaining_uses, node_outputs, retain_intermediates):
        for reference in references:
            key = cls._reference_key(reference)
            remaining_uses[key] -= 1
            if retain_intermediates or key[0] != "node_output" or remaining_uses[key] > 0:
                continue
            node_id, output_name = key[1], key[2]
            output = node_outputs.get(node_id)
            if output is None:
                continue
            output.images.pop(output_name, None)
            output.data.pop(output_name, None)
            if not output.images and not output.data:
                node_outputs.pop(node_id, None)

    @classmethod
    def _build_output(cls, *, bindings, graph_inputs, node_outputs) -> OperationOutput:
        images: dict[str, ImageData] = {}
        data: dict[str, Any] = {}
        for name, reference in bindings.items():
            value, is_image = cls._resolve_reference(
                reference=reference, graph_inputs=graph_inputs, node_outputs=node_outputs
            )
            if is_image:
                images[name] = value
            else:
                data[name] = value
        return OperationOutput(images=images, data=data)

    @classmethod
    def _failure(
        cls,
        *,
        recipe: str,
        code: str,
        message: str,
        details: dict[str, Any],
        started_at: float,
        node_id: str | None = None,
        nodes: list[WorkflowNodeExecution] | None = None,
        intermediates: dict[str, OperationOutput] | None = None,
        warnings: list[str] | None = None,
    ) -> WorkflowExecutionResult:
        return WorkflowExecutionResult(
            recipe=recipe,
            success=False,
            nodes=nodes or [],
            intermediates=intermediates or {},
            metadata=ExecutionMetadata(
                duration_ms=cls._elapsed_ms(started_at), warnings=warnings or []
            ),
            error=WorkflowError(
                code=code, message=message, node_id=node_id, details=details
            ),
        )

    @staticmethod
    def _elapsed_ms(started_at: float) -> float:
        return max(0.0, (time.perf_counter() - started_at) * 1000.0)


def _runtime_kind_compatible(value: Any, expected: WorkflowDataKind) -> bool:
    if expected in {WorkflowDataKind.IMAGE, WorkflowDataKind.MASK, WorkflowDataKind.TEMPLATE}:
        return isinstance(value, ImageData)
    if expected == WorkflowDataKind.SCALAR:
        return not isinstance(value, bool) and isinstance(value, (int, float, np.number))
    if expected == WorkflowDataKind.BOOLEAN:
        return isinstance(value, bool)
    if expected in {WorkflowDataKind.ARRAY, WorkflowDataKind.PROFILE, WorkflowDataKind.CONTOURS, WorkflowDataKind.ROI_SET}:
        return isinstance(value, (list, tuple, np.ndarray))
    if expected in {WorkflowDataKind.METRICS, WorkflowDataKind.ROI}:
        return isinstance(value, dict)
    if expected == WorkflowDataKind.DECISION:
        return isinstance(value, (str, dict))
    return True
