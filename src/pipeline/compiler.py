from __future__ import annotations

from dataclasses import dataclass

from src.registry import OperationRegistry
from src.schemas import (
    ExecutionRequest,
    InputKind,
    OperationSpec,
    OutputKind,
    PipelineInputReference,
    PipelineSpec,
    PipelineValidationIssue,
    PipelineValueReference,
    StepOutputReference,
)
from src.validators import (
    ParameterValidationError,
    ParameterValidator,
)

from .errors import PipelineValidationError


@dataclass(frozen=True, slots=True)
class CompiledPipeline:
    spec: PipelineSpec
    operation_specs: dict[str, OperationSpec]
    output_bindings: dict[str, PipelineValueReference]
    registry_revision: int


class PipelineCompiler:
    """Pipeline 전체를 실행 전에 Registry 기준으로 사전 검증한다."""

    def __init__(self, registry: OperationRegistry) -> None:
        self._registry = registry

    def compile(self, pipeline: PipelineSpec) -> CompiledPipeline:
        pipeline_copy = PipelineSpec.model_validate(
            pipeline.model_dump(mode="python")
        )
        issues: list[PipelineValidationIssue] = []
        operation_specs: dict[str, OperationSpec] = {}
        registry_revision, registry_specs = (
            self._registry.snapshot_specs(
                step.operation
                for step in pipeline_copy.steps
            )
        )
        pipeline_inputs = {
            item.name: item
            for item in pipeline_copy.inputs
        }

        for step in pipeline_copy.steps:
            if step.operation not in registry_specs:
                issues.append(
                    PipelineValidationIssue(
                        location=f"step.{step.id}",
                        code="operation_not_found",
                        message=(
                            "operation is not registered: "
                            f"{step.operation}"
                        ),
                        value=step.operation,
                    )
                )
                continue

            operation_spec = registry_specs[
                step.operation
            ].model_copy(deep=True)
            operation_specs[step.id] = operation_spec

            issues.extend(
                self._validate_step_inputs(
                    step_id=step.id,
                    bindings=step.inputs,
                    operation_spec=operation_spec,
                    operation_specs=operation_specs,
                    pipeline_inputs=pipeline_inputs,
                )
            )
            issues.extend(
                self._validate_step_params(
                    step_id=step.id,
                    operation=step.operation,
                    params=step.params,
                    operation_spec=operation_spec,
                )
            )

        output_bindings = self._resolve_output_bindings(
            pipeline=pipeline_copy,
            operation_specs=operation_specs,
            issues=issues,
        )

        if issues:
            raise PipelineValidationError(issues)

        return CompiledPipeline(
            spec=pipeline_copy,
            operation_specs=operation_specs,
            output_bindings=output_bindings,
            registry_revision=registry_revision,
        )

    @classmethod
    def _validate_step_inputs(
        cls,
        *,
        step_id: str,
        bindings: dict[str, PipelineValueReference],
        operation_spec: OperationSpec,
        operation_specs: dict[str, OperationSpec],
        pipeline_inputs: dict,
    ) -> list[PipelineValidationIssue]:
        issues: list[PipelineValidationIssue] = []
        target_slots = {
            slot.name: slot
            for slot in operation_spec.inputs
        }

        for name in sorted(set(bindings) - set(target_slots)):
            issues.append(
                PipelineValidationIssue(
                    location=f"step.{step_id}.inputs.{name}",
                    code="unknown_input_binding",
                    message="operation has no such input slot",
                    value=name,
                )
            )

        for name, slot in target_slots.items():
            if name not in bindings:
                if slot.required:
                    issues.append(
                        PipelineValidationIssue(
                            location=f"step.{step_id}.inputs.{name}",
                            code="missing_input_binding",
                            message="required input binding is missing",
                        )
                    )
                continue

            reference = bindings[name]
            source_kind = cls._resolve_source_kind(
                reference=reference,
                operation_specs=operation_specs,
                pipeline_inputs=pipeline_inputs,
                issues=issues,
                location=f"step.{step_id}.inputs.{name}",
            )

            if source_kind is None:
                continue

            if not cls._kinds_compatible(
                source_kind=source_kind,
                target_kind=slot.kind,
            ):
                issues.append(
                    PipelineValidationIssue(
                        location=f"step.{step_id}.inputs.{name}",
                        code="incompatible_input_kind",
                        message=(
                            f"cannot connect {source_kind.value} "
                            f"to {slot.kind.value}"
                        ),
                        value={
                            "source": source_kind.value,
                            "target": slot.kind.value,
                        },
                    )
                )

        return issues

    @staticmethod
    def _validate_step_params(
        *,
        step_id: str,
        operation: str,
        params: dict,
        operation_spec: OperationSpec,
    ) -> list[PipelineValidationIssue]:
        try:
            ParameterValidator.validate_request(
                request=ExecutionRequest(
                    operation=operation,
                    params=params,
                ),
                operation_spec=operation_spec,
            )
        except ParameterValidationError as exc:
            return [
                PipelineValidationIssue(
                    location=(
                        f"step.{step_id}.params.{issue.parameter}"
                    ),
                    code=issue.code,
                    message=issue.message,
                    value=issue.value,
                )
                for issue in exc.issues
            ]

        return []

    @classmethod
    def _resolve_source_kind(
        cls,
        *,
        reference: PipelineValueReference,
        operation_specs: dict[str, OperationSpec],
        pipeline_inputs: dict,
        issues: list[PipelineValidationIssue],
        location: str,
    ) -> InputKind | OutputKind | None:
        if isinstance(reference, PipelineInputReference):
            pipeline_input = pipeline_inputs[reference.input_name]

            if not pipeline_input.required:
                issues.append(
                    PipelineValidationIssue(
                        location=location,
                        code="optional_reference_not_supported",
                        message=(
                            "referenced pipeline inputs must be required "
                            "in a linear pipeline"
                        ),
                        value=reference.input_name,
                    )
                )

            return pipeline_input.kind

        source_spec = operation_specs.get(reference.step_id)
        if source_spec is None:
            return None

        outputs = {
            item.name: item
            for item in source_spec.outputs
        }
        output = outputs.get(reference.output_name)

        if output is None:
            issues.append(
                PipelineValidationIssue(
                    location=location,
                    code="unknown_step_output",
                    message=(
                        f"step {reference.step_id} has no output "
                        f"named {reference.output_name}"
                    ),
                    value=reference.output_name,
                )
            )
            return None

        return output.kind

    @staticmethod
    def _kinds_compatible(
        *,
        source_kind: InputKind | OutputKind,
        target_kind: InputKind,
    ) -> bool:
        source = source_kind.value
        target = target_kind.value

        if source == target:
            return True

        image_compatibility = {
            "image": {"image", "template"},
            "mask": {"image", "mask", "template"},
            "template": {"image", "template"},
        }
        if source in image_compatibility:
            return target in image_compatibility[source]

        if source == "array":
            return target in {"array", "markers", "points"}

        return False

    @classmethod
    def _resolve_output_bindings(
        cls,
        *,
        pipeline: PipelineSpec,
        operation_specs: dict[str, OperationSpec],
        issues: list[PipelineValidationIssue],
    ) -> dict[str, PipelineValueReference]:
        if pipeline.outputs:
            bindings = dict(pipeline.outputs)
        else:
            final_step = pipeline.steps[-1]
            final_spec = operation_specs.get(final_step.id)
            if final_spec is None:
                return {}

            bindings = {
                output.name: StepOutputReference(
                    step_id=final_step.id,
                    output_name=output.name,
                )
                for output in final_spec.outputs
            }

        pipeline_inputs = {
            item.name: item
            for item in pipeline.inputs
        }

        for name, reference in bindings.items():
            cls._resolve_source_kind(
                reference=reference,
                operation_specs=operation_specs,
                pipeline_inputs=pipeline_inputs,
                issues=issues,
                location=f"pipeline.outputs.{name}",
            )

        return bindings
