from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.schemas import ImageData

from .schemas import SyntheticCandidateMetadata


@dataclass(slots=True)
class SyntheticCandidate:
    image: ImageData
    mask: ImageData
    difference: ImageData
    metadata: SyntheticCandidateMetadata


@dataclass(slots=True)
class SyntheticGenerationResult:
    candidates: list[SyntheticCandidate]
    request_metadata: dict[str, Any] = field(default_factory=dict)
