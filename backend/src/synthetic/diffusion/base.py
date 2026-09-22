from __future__ import annotations

from typing import Protocol

import numpy as np


class DiffusionProvider(Protocol):
    model_key: str

    @property
    def loaded(self) -> bool: ...

    def generate(
        self,
        *,
        image_bgr: np.ndarray,
        mask: np.ndarray,
        prompt: str,
        negative_prompt: str | None,
        seed: int,
        parameters: dict,
    ) -> np.ndarray: ...

    def unload(self) -> None: ...
