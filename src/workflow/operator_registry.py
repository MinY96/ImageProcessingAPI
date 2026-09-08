from __future__ import annotations

from collections.abc import Mapping
from math import fsum
from threading import RLock
from typing import Any

from src.workflow.schemas import ScalarOperatorSpec


class ScalarOperatorRegistry:
    def __init__(self) -> None:
        self._specs: dict[str, ScalarOperatorSpec] = {}
        self._lock = RLock()

    def register(self, spec: ScalarOperatorSpec) -> None:
        with self._lock:
            if spec.name in self._specs:
                raise ValueError(f"scalar operator already registered: {spec.name}")
            self._specs[spec.name] = spec.model_copy(deep=True)

    def contains(self, name: str) -> bool:
        with self._lock:
            return name in self._specs

    def get_spec(self, name: str) -> ScalarOperatorSpec:
        with self._lock:
            spec = self._specs.get(name)
        if spec is None:
            raise KeyError(name)
        return spec.model_copy(deep=True)

    def list_specs(self) -> list[ScalarOperatorSpec]:
        with self._lock:
            return [self._specs[name].model_copy(deep=True) for name in sorted(self._specs)]

    def execute(self, *, name: str, inputs: Mapping[str, Any], params: Mapping[str, Any]) -> float:
        spec = self.get_spec(name)
        values = {key: _as_float(value, key) for key, value in inputs.items()}
        if len(values) < spec.min_inputs or (spec.max_inputs is not None and len(values) > spec.max_inputs):
            raise ValueError(f"operator {name} expects {spec.min_inputs}..{spec.max_inputs or 'N'} inputs")
        missing = sorted(set(spec.required_input_names) - set(values))
        if missing:
            raise ValueError(f"operator {name} missing inputs: {missing}")

        if name == "add":
            return values["a"] + values["b"]
        if name == "subtract":
            return values["a"] - values["b"]
        if name == "multiply":
            return values["a"] * values["b"]
        if name in {"divide", "ratio"}:
            denominator = values["b"]
            if denominator == 0:
                raise ValueError("division by zero")
            return values["a"] / denominator
        if name == "abs_diff":
            return abs(values["a"] - values["b"])
        if name == "sum":
            return fsum(values.values())
        if name == "mean":
            return fsum(values.values()) / len(values)
        if name == "min":
            return min(values.values())
        if name == "max":
            return max(values.values())
        if name == "weighted_sum":
            raw_weights = params.get("weights", {})
            if not isinstance(raw_weights, dict):
                raise ValueError("weighted_sum params.weights must be an object")
            unknown = sorted(set(raw_weights) - set(values))
            if unknown:
                raise ValueError(f"weights reference unknown inputs: {unknown}")
            weights = {key: float(raw_weights.get(key, 1.0)) for key in values}
            bias = float(params.get("bias", 0.0))
            return fsum(values[key] * weights[key] for key in values) + bias
        if name == "weighted_mean":
            raw_weights = params.get("weights", {})
            if not isinstance(raw_weights, dict):
                raise ValueError("weighted_mean params.weights must be an object")
            weights = {key: float(raw_weights.get(key, 1.0)) for key in values}
            total_weight = fsum(weights.values())
            if total_weight == 0:
                raise ValueError("sum of weights must not be zero")
            return fsum(values[key] * weights[key] for key in values) / total_weight
        if name == "normalize_range":
            value = values["value"]
            lower = float(params.get("lower", 0.0))
            upper = float(params.get("upper", 1.0))
            if upper <= lower:
                raise ValueError("normalize_range requires upper > lower")
            normalized = (value - lower) / (upper - lower)
            if bool(params.get("clip", True)):
                normalized = min(1.0, max(0.0, normalized))
            return normalized
        raise KeyError(name)


def _as_float(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"scalar input {name} must be numeric")
    return float(value)


def create_default_scalar_operator_registry() -> ScalarOperatorRegistry:
    registry = ScalarOperatorRegistry()
    for name, display, required in [
        ("add", "Add", ["a", "b"]),
        ("subtract", "Subtract", ["a", "b"]),
        ("multiply", "Multiply", ["a", "b"]),
        ("divide", "Divide", ["a", "b"]),
        ("ratio", "Ratio", ["a", "b"]),
        ("abs_diff", "Absolute Difference", ["a", "b"]),
    ]:
        registry.register(ScalarOperatorSpec(
            name=name, display_name=display, min_inputs=2, max_inputs=2,
            required_input_names=required,
        ))
    for name, display in [("sum", "Sum"), ("mean", "Mean"), ("min", "Minimum"), ("max", "Maximum")]:
        registry.register(ScalarOperatorSpec(name=name, display_name=display, min_inputs=1))
    registry.register(ScalarOperatorSpec(
        name="weighted_sum", display_name="Weighted Sum", min_inputs=1,
        parameters={"weights": {"type": "object", "description": "input-name -> weight"}, "bias": {"type": "number", "default": 0.0}},
    ))
    registry.register(ScalarOperatorSpec(
        name="weighted_mean", display_name="Weighted Mean", min_inputs=1,
        parameters={"weights": {"type": "object", "description": "input-name -> weight"}},
    ))
    registry.register(ScalarOperatorSpec(
        name="normalize_range", display_name="Normalize Range", min_inputs=1, max_inputs=1,
        required_input_names=["value"],
        parameters={"lower": {"type": "number", "default": 0.0}, "upper": {"type": "number", "default": 1.0}, "clip": {"type": "boolean", "default": True}},
    ))
    return registry
