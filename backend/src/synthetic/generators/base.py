from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

import numpy as np

from src.schemas import ImageData

from ..schemas import SyntheticGenerateRequest


@dataclass(slots=True)
class GenerationContext:
    source: ImageData
    target_mask: np.ndarray
    request: SyntheticGenerateRequest
    seed: int
    asset: ImageData | None = None
    asset_mask: ImageData | None = None


@dataclass(slots=True)
class GeneratorOutput:
    image: np.ndarray
    mask: np.ndarray
    metadata: dict[str, Any] = field(default_factory=dict)


class SyntheticGenerator(Protocol):
    def generate(self, context: GenerationContext) -> GeneratorOutput: ...
