from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any

from src.pipeline import PipelineCatalog, PipelineExecutor
from src.registry import OperationRegistry
from src.schemas import ExecutionRequest, InputKind, OutputKind
from src.validators import ParameterValidationError, ParameterValidator
from src.workflow.errors import WorkflowNotFoundError, WorkflowValidationError
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
    WorkflowNodeSpec,
    WorkflowPortSpec,
    WorkflowValidationIssue,
)


@dataclass(frozen=True, slots=True)
class CompiledWorkflow:
    spec: GraphRecipeSpec
    execution_order: tuple[str, ...]
    node_output_kinds: dict[str, dict[str, WorkflowDataKind]]
    output_bindings: dict[str, GraphValueReference]


class WorkflowCompiler:
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

    def attach_workflow_catalog(self, catalog) -> None:
        self._workflow_catalog = catalog

    def compile(
        self,
        recipe: GraphRecipeSpec,
        *,
        recipe_stack: tuple[str, ...] = (),
    ) -> CompiledWorkflow:
        spec = GraphRecipeSpec.model_validate(recipe.model_dump(mode="python"))
        issues: list[WorkflowValidationIssue] = []
        input_kinds = {item.name: item.kind for item in spec.inputs}
        nodes = {node.id: node for node in spec.nodes}

        if spec.name in recipe_stack:
            issues.append(WorkflowValidationIssue(
                location="recipe",
                code="subrecipe_cycle",
                message=f"recursive subrecipe dependency detected: {' -> '.join((*recipe_stack, spec.name))}",
            ))
            raise WorkflowValidationError(issues)

        order = self._topological_order(spec, nodes, issues)
        node_output_kinds: dict[str, dict[str, WorkflowDataKind]] = {}
        stack = (*recipe_stack, spec.name)

        for node_id in order:
            node = nodes[node_id]
            output_kinds = self._validate_node(
                node=node,
                input_kinds=input_kinds,
                node_output_kinds=node_output_kinds,
                issues=issues,
                recipe_stack=stack,
            )
            node_output_kinds[node_id] = output_kinds

        for output_name, reference in spec.outputs.items():
            self._resolve_reference_kind(
                reference=reference,
                input_kinds=input_kinds,
                node_output_kinds=node_output_kinds,
                issues=issues,
                location=f"outputs.{output_name}",
            )

        if issues:
            raise WorkflowValidationError(issues)

        return CompiledWorkflow(
            spec=spec,
            execution_order=tuple(order),
            node_output_kinds=node_output_kinds,
            output_bindings=dict(spec.outputs),
        )

    def _topological_order(
        self,
        spec: GraphRecipeSpec,
        nodes: dict[str, WorkflowNodeSpec],
        issues: list[WorkflowValidationIssue],
    ) -> list[str]:
        dependencies: dict[str, set[str]] = {node_id: set() for node_id in nodes}
        followers: dict[str, set[str]] = defaultdict(set)
        known_inputs = {item.name for item in spec.inputs}

        for node in spec.nodes:
            for input_name, ref in node.inputs.items():
                if isinstance(ref, GraphInputReference):
                    if ref.input_name not in known_inputs:
                        issues.append(WorkflowValidationIssue(
                            location=f"nodes.{node.id}.inputs.{input_name}",
                            code="unknown_graph_input",
                            message=f"unknown graph input: {ref.input_name}",
                            value=ref.input_name,
                        ))
                    continue
                if ref.node_id not in nodes:
                    issues.append(WorkflowValidationIssue(
                        location=f"nodes.{node.id}.inputs.{input_name}",
                        code="unknown_node",
                        message=f"unknown source node: {ref.node_id}",
                        value=ref.node_id,
                    ))
                    continue
                dependencies[node.id].add(ref.node_id)
                followers[ref.node_id].add(node.id)

        indegree = {node_id: len(deps) for node_id, deps in dependencies.items()}
        ready = deque(sorted(node_id for node_id, degree in indegree.items() if degree == 0))
        order: list[str] = []
        while ready:
            node_id = ready.popleft()
            order.append(node_id)
            for follower in sorted(followers[node_id]):
                indegree[follower] -= 1
                if indegree[follower] == 0:
                    ready.append(follower)

        if len(order) != len(nodes):
            cyclic = sorted(node_id for node_id, degree in indegree.items() if degree > 0)
            issues.append(WorkflowValidationIssue(
                location="nodes",
                code="graph_cycle",
                message="workflow graph must be acyclic",
                value=cyclic,
            ))
            # Return a deterministic partial+remaining order so validation can report more issues.
            order.extend(node_id for node_id in sorted(nodes) if node_id not in order)
        return order

    def _validate_node(
        self,
        *,
        node: WorkflowNodeSpec,
        input_kinds: dict[str, WorkflowDataKind],
        node_output_kinds: dict[str, dict[str, WorkflowDataKind]],
        issues: list[WorkflowValidationIssue],
        recipe_stack: tuple[str, ...],
    ) -> dict[str, WorkflowDataKind]:
        if isinstance(node, OperationNodeSpec):
            return self._validate_operation(node, input_kinds, node_output_kinds, issues)
        if isinstance(node, FeatureNodeSpec):
            return self._validate_feature(node, input_kinds, node_output_kinds, issues)
        if isinstance(node, ScalarOperatorNodeSpec):
            return self._validate_scalar_operator(node, input_kinds, node_output_kinds, issues)
        if isinstance(node, RoiCropNodeSpec):
            self._validate_bindings(
                node=node,
                expected=[WorkflowPortSpec(name="image", kind=WorkflowDataKind.IMAGE)],
                input_kinds=input_kinds,
                node_output_kinds=node_output_kinds,
                issues=issues,
            )
            self._validate_roi_params(node, issues)
            source_kind = self._binding_kind(node.inputs.get("image"), input_kinds, node_output_kinds)
            image_kind = source_kind if source_kind in _IMAGE_KINDS else WorkflowDataKind.IMAGE
            return {"image": image_kind, "region": WorkflowDataKind.ROI}
        if isinstance(node, RoiComposeNodeSpec):
            self._validate_bindings(
                node=node,
                expected=[
                    WorkflowPortSpec(name="base", kind=WorkflowDataKind.IMAGE),
                    WorkflowPortSpec(name="patch", kind=WorkflowDataKind.IMAGE),
                    WorkflowPortSpec(name="region", kind=WorkflowDataKind.ROI),
                ],
                input_kinds=input_kinds,
                node_output_kinds=node_output_kinds,
                issues=issues,
            )
            base_kind = self._binding_kind(node.inputs.get("base"), input_kinds, node_output_kinds)
            return {"image": base_kind if base_kind in _IMAGE_KINDS else WorkflowDataKind.IMAGE}
        if isinstance(node, DecisionNodeSpec):
            self._validate_bindings(
                node=node,
                expected=[WorkflowPortSpec(name="value", kind=WorkflowDataKind.SCALAR)],
                input_kinds=input_kinds,
                node_output_kinds=node_output_kinds,
                issues=issues,
            )
            self._validate_decision_params(node, issues)
            return {
                "value": WorkflowDataKind.SCALAR,
                "passed": WorkflowDataKind.BOOLEAN,
                "label": WorkflowDataKind.DECISION,
            }
        if isinstance(node, SubRecipeNodeSpec):
            return self._validate_subrecipe(
                node, input_kinds, node_output_kinds, issues, recipe_stack
            )
        raise TypeError(type(node).__name__)

    def _validate_operation(self, node, input_kinds, node_output_kinds, issues):
        try:
            spec = self._registry.get_spec(node.operation)
        except Exception:
            issues.append(WorkflowValidationIssue(
                location=f"nodes.{node.id}", code="operation_not_found",
                message=f"operation is not registered: {node.operation}", value=node.operation,
            ))
            return {}
        expected = [
            WorkflowPortSpec(name=slot.name, kind=_from_input_kind(slot.kind), required=slot.required)
            for slot in spec.inputs
        ]
        self._validate_bindings(
            node=node, expected=expected, input_kinds=input_kinds,
            node_output_kinds=node_output_kinds, issues=issues,
        )
        try:
            ParameterValidator.validate_request(
                request=ExecutionRequest(operation=node.operation, params=node.params),
                operation_spec=spec,
            )
        except ParameterValidationError as exc:
            for issue in exc.issues:
                issues.append(WorkflowValidationIssue(
                    location=f"nodes.{node.id}.params.{issue.parameter}",
                    code=issue.code, message=issue.message, value=issue.value,
                ))
        return {slot.name: _from_output_kind(slot.kind) for slot in spec.outputs}

    def _validate_feature(self, node, input_kinds, node_output_kinds, issues):
        try:
            spec = self._features.get_spec(node.feature)
        except KeyError:
            issues.append(WorkflowValidationIssue(
                location=f"nodes.{node.id}", code="feature_not_found",
                message=f"feature is not registered: {node.feature}", value=node.feature,
            ))
            return {}
        self._validate_bindings(
            node=node, expected=spec.inputs, input_kinds=input_kinds,
            node_output_kinds=node_output_kinds, issues=issues,
        )
        try:
            self._features.validate_params(node.feature, node.params)
        except ParameterValidationError as exc:
            for issue in exc.issues:
                issues.append(WorkflowValidationIssue(
                    location=f"nodes.{node.id}.params.{issue.parameter}",
                    code=issue.code, message=issue.message, value=issue.value,
                ))
        return {slot.name: slot.kind for slot in spec.outputs}

    def _validate_scalar_operator(self, node, input_kinds, node_output_kinds, issues):
        try:
            spec = self._operators.get_spec(node.operator)
        except KeyError:
            issues.append(WorkflowValidationIssue(
                location=f"nodes.{node.id}", code="scalar_operator_not_found",
                message=f"scalar operator is not registered: {node.operator}", value=node.operator,
            ))
            return {"value": WorkflowDataKind.SCALAR}
        count = len(node.inputs)
        if count < spec.min_inputs or (spec.max_inputs is not None and count > spec.max_inputs):
            issues.append(WorkflowValidationIssue(
                location=f"nodes.{node.id}.inputs", code="invalid_input_count",
                message=f"operator {node.operator} expects {spec.min_inputs}..{spec.max_inputs or 'N'} inputs",
                value=count,
            ))
        missing = sorted(set(spec.required_input_names) - set(node.inputs))
        if missing:
            issues.append(WorkflowValidationIssue(
                location=f"nodes.{node.id}.inputs", code="missing_input_binding",
                message=f"missing operator inputs: {missing}", value=missing,
            ))
        for name, reference in node.inputs.items():
            kind = self._resolve_reference_kind(
                reference=reference, input_kinds=input_kinds, node_output_kinds=node_output_kinds,
                issues=issues, location=f"nodes.{node.id}.inputs.{name}",
            )
            if kind is not None and kind != WorkflowDataKind.SCALAR:
                issues.append(WorkflowValidationIssue(
                    location=f"nodes.{node.id}.inputs.{name}", code="incompatible_input_kind",
                    message=f"scalar operator input requires scalar, got {kind.value}", value=kind.value,
                ))
        if node.operator == "normalize_range":
            lower = float(node.params.get("lower", 0.0))
            upper = float(node.params.get("upper", 1.0))
            if upper <= lower:
                issues.append(WorkflowValidationIssue(
                    location=f"nodes.{node.id}.params", code="invalid_range",
                    message="normalize_range requires upper > lower",
                ))
        return {"value": WorkflowDataKind.SCALAR}

    def _validate_subrecipe(self, node, input_kinds, node_output_kinds, issues, recipe_stack):
        try:
            kind, target_inputs, target_outputs, target_version = self._subrecipe_interface(
                node.recipe, node.recipe_kind, recipe_stack
            )
        except WorkflowValidationError as exc:
            issues.extend(exc.issues)
            return {}
        except WorkflowNotFoundError as exc:
            issues.append(WorkflowValidationIssue(
                location=f"nodes.{node.id}", code="subrecipe_not_found", message=str(exc), value=node.recipe,
            ))
            return {}
        if node.recipe_version is not None and node.recipe_version != target_version:
            issues.append(WorkflowValidationIssue(
                location=f"nodes.{node.id}.recipe_version", code="subrecipe_version_mismatch",
                message=f"requested {node.recipe_version}, current {target_version}", value=node.recipe_version,
            ))
        self._validate_bindings(
            node=node, expected=target_inputs, input_kinds=input_kinds,
            node_output_kinds=node_output_kinds, issues=issues,
        )
        return target_outputs

    def _subrecipe_interface(self, name: str, requested_kind: str, recipe_stack: tuple[str, ...]):
        if name in recipe_stack:
            raise WorkflowValidationError([WorkflowValidationIssue(
                location="subrecipe", code="subrecipe_cycle",
                message=f"recursive subrecipe dependency detected: {' -> '.join((*recipe_stack, name))}", value=name,
            )])
        graph_available = self._workflow_catalog is not None and self._workflow_catalog.contains(name)
        linear_available = self._pipeline_catalog.contains(name)
        if requested_kind == "graph" or (requested_kind == "auto" and graph_available):
            if not graph_available:
                raise WorkflowNotFoundError(f"graph recipe is not registered: {name}")
            graph = self._workflow_catalog.get_spec(name)
            compiled = self.compile(graph, recipe_stack=recipe_stack)
            return (
                "graph",
                graph.inputs,
                {
                    output_name: self._resolve_reference_kind(
                        reference=reference,
                        input_kinds={item.name: item.kind for item in graph.inputs},
                        node_output_kinds=compiled.node_output_kinds,
                        issues=[],
                        location=f"subrecipe.{name}.outputs.{output_name}",
                    )
                    for output_name, reference in graph.outputs.items()
                },
                graph.version,
            )
        if requested_kind == "linear" or (requested_kind == "auto" and linear_available):
            if not linear_available:
                raise WorkflowNotFoundError(f"linear recipe is not registered: {name}")
            compiled = self._pipeline_executor.compile(self._pipeline_catalog.get_spec(name))
            inputs = [
                WorkflowPortSpec(name=item.name, kind=_from_input_kind(item.kind), required=item.required)
                for item in compiled.spec.inputs
            ]
            outputs: dict[str, WorkflowDataKind] = {}
            input_map = {item.name: item.kind for item in compiled.spec.inputs}
            for output_name, reference in compiled.output_bindings.items():
                if hasattr(reference, "input_name"):
                    outputs[output_name] = _from_input_kind(input_map[reference.input_name])
                else:
                    op_spec = compiled.operation_specs[reference.step_id]
                    slot = next(item for item in op_spec.outputs if item.name == reference.output_name)
                    outputs[output_name] = _from_output_kind(slot.kind)
            return "linear", inputs, outputs, compiled.spec.version
        raise WorkflowNotFoundError(f"recipe is not registered: {name}")

    def _validate_bindings(self, *, node, expected, input_kinds, node_output_kinds, issues):
        expected_map = {item.name: item for item in expected}
        for unknown in sorted(set(node.inputs) - set(expected_map)):
            issues.append(WorkflowValidationIssue(
                location=f"nodes.{node.id}.inputs.{unknown}", code="unknown_input_binding",
                message="node has no such input port", value=unknown,
            ))
        for name, port in expected_map.items():
            if name not in node.inputs:
                if port.required:
                    issues.append(WorkflowValidationIssue(
                        location=f"nodes.{node.id}.inputs.{name}", code="missing_input_binding",
                        message="required input binding is missing",
                    ))
                continue
            kind = self._resolve_reference_kind(
                reference=node.inputs[name], input_kinds=input_kinds,
                node_output_kinds=node_output_kinds, issues=issues,
                location=f"nodes.{node.id}.inputs.{name}",
            )
            if kind is not None and not _kinds_compatible(kind, port.kind):
                issues.append(WorkflowValidationIssue(
                    location=f"nodes.{node.id}.inputs.{name}", code="incompatible_input_kind",
                    message=f"cannot connect {kind.value} to {port.kind.value}",
                    value={"source": kind.value, "target": port.kind.value},
                ))

    def _resolve_reference_kind(self, *, reference, input_kinds, node_output_kinds, issues, location):
        if isinstance(reference, GraphInputReference):
            kind = input_kinds.get(reference.input_name)
            if kind is None:
                issues.append(WorkflowValidationIssue(
                    location=location, code="unknown_graph_input",
                    message=f"unknown graph input: {reference.input_name}", value=reference.input_name,
                ))
            return kind
        outputs = node_output_kinds.get(reference.node_id)
        if outputs is None:
            issues.append(WorkflowValidationIssue(
                location=location, code="unavailable_node_output",
                message=f"source node is not available: {reference.node_id}", value=reference.node_id,
            ))
            return None
        kind = outputs.get(reference.output_name)
        if kind is None:
            issues.append(WorkflowValidationIssue(
                location=location, code="unknown_node_output",
                message=f"node {reference.node_id} has no output named {reference.output_name}", value=reference.output_name,
            ))
        return kind

    @staticmethod
    def _binding_kind(reference, input_kinds, node_output_kinds):
        if reference is None:
            return None
        if isinstance(reference, GraphInputReference):
            return input_kinds.get(reference.input_name)
        return node_output_kinds.get(reference.node_id, {}).get(reference.output_name)

    @staticmethod
    def _validate_roi_params(node: RoiCropNodeSpec, issues):
        mode = node.params.get("coordinate_mode", "pixels")
        if mode not in {"pixels", "relative"}:
            issues.append(WorkflowValidationIssue(
                location=f"nodes.{node.id}.params.coordinate_mode", code="invalid_choice",
                message="coordinate_mode must be pixels or relative", value=mode,
            ))
            return
        values = [node.params.get(key) for key in ("x", "y", "width", "height")]
        if any(value is None for value in values):
            issues.append(WorkflowValidationIssue(
                location=f"nodes.{node.id}.params", code="missing_roi_parameter",
                message="ROI requires x, y, width, and height",
            ))
            return
        x, y, width, height = values
        try:
            x, y, width, height = float(x), float(y), float(width), float(height)
        except (TypeError, ValueError):
            issues.append(WorkflowValidationIssue(
                location=f"nodes.{node.id}.params", code="invalid_roi_parameter",
                message="ROI coordinates must be numeric",
            ))
            return
        if width <= 0 or height <= 0 or x < 0 or y < 0:
            issues.append(WorkflowValidationIssue(
                location=f"nodes.{node.id}.params", code="invalid_roi_rectangle",
                message="ROI x/y must be >= 0 and width/height must be > 0",
            ))
        if mode == "relative" and (x > 1 or y > 1 or width > 1 or height > 1 or x + width > 1.000001 or y + height > 1.000001):
            issues.append(WorkflowValidationIssue(
                location=f"nodes.{node.id}.params", code="invalid_relative_roi",
                message="relative ROI values must stay inside [0, 1]",
            ))

    @staticmethod
    def _validate_decision_params(node: DecisionNodeSpec, issues):
        operator = node.params.get("operator", "gt")
        allowed = {"gt", "gte", "lt", "lte", "inside_range", "outside_range"}
        if operator not in allowed:
            issues.append(WorkflowValidationIssue(
                location=f"nodes.{node.id}.params.operator", code="invalid_choice",
                message=f"decision operator must be one of {sorted(allowed)}", value=operator,
            ))
        if operator in {"gt", "gte", "lt", "lte"} and "threshold" not in node.params:
            issues.append(WorkflowValidationIssue(
                location=f"nodes.{node.id}.params.threshold", code="missing_required",
                message="threshold is required for scalar comparison",
            ))
        if operator in {"inside_range", "outside_range"}:
            if "lower" not in node.params or "upper" not in node.params:
                issues.append(WorkflowValidationIssue(
                    location=f"nodes.{node.id}.params", code="missing_required",
                    message="lower and upper are required for range comparison",
                ))
            elif float(node.params["upper"]) < float(node.params["lower"]):
                issues.append(WorkflowValidationIssue(
                    location=f"nodes.{node.id}.params", code="invalid_range",
                    message="upper must be >= lower",
                ))


_IMAGE_KINDS = {WorkflowDataKind.IMAGE, WorkflowDataKind.MASK, WorkflowDataKind.TEMPLATE}


def _kinds_compatible(source: WorkflowDataKind, target: WorkflowDataKind) -> bool:
    if source == target:
        return True
    if source in _IMAGE_KINDS and target in _IMAGE_KINDS:
        # Generic IMAGE ports intentionally accept mask/template values as image-like data.
        if target == WorkflowDataKind.IMAGE:
            return True
        return source == target or source == WorkflowDataKind.MASK
    if source == WorkflowDataKind.PROFILE and target == WorkflowDataKind.ARRAY:
        return True
    return False


def _from_input_kind(kind: InputKind) -> WorkflowDataKind:
    mapping = {
        InputKind.IMAGE: WorkflowDataKind.IMAGE,
        InputKind.MASK: WorkflowDataKind.MASK,
        InputKind.TEMPLATE: WorkflowDataKind.TEMPLATE,
        InputKind.CONTOURS: WorkflowDataKind.CONTOURS,
        InputKind.ARRAY: WorkflowDataKind.ARRAY,
        InputKind.MARKERS: WorkflowDataKind.ARRAY,
        InputKind.POINTS: WorkflowDataKind.ARRAY,
        InputKind.MODEL: WorkflowDataKind.METRICS,
    }
    return mapping[kind]


def _from_output_kind(kind: OutputKind) -> WorkflowDataKind:
    mapping = {
        OutputKind.IMAGE: WorkflowDataKind.IMAGE,
        OutputKind.MASK: WorkflowDataKind.MASK,
        OutputKind.ARRAY: WorkflowDataKind.ARRAY,
        OutputKind.CONTOURS: WorkflowDataKind.CONTOURS,
        OutputKind.METRICS: WorkflowDataKind.METRICS,
        OutputKind.SCALAR: WorkflowDataKind.SCALAR,
    }
    return mapping[kind]
