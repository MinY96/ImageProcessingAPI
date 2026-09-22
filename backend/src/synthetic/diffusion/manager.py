from __future__ import annotations

import importlib.util
from pathlib import Path

from ..errors import SyntheticValidationError
from ..schemas import DiffusionModelStatus
from .flux import FluxFillProvider
from .sdxl import SDXLInpaintProvider


class DiffusionManager:
    def __init__(
        self,
        *,
        cache_dir: Path,
        local_files_only: bool,
        device: str,
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self.local_files_only = bool(local_files_only)
        self.device = device
        self._providers = {
            "sdxl_inpaint": SDXLInpaintProvider(
                cache_dir=self.cache_dir / "sdxl_inpaint",
                local_files_only=self.local_files_only,
                device=self.device,
            ),
            "flux_fill": FluxFillProvider(
                cache_dir=self.cache_dir / "flux_fill",
                local_files_only=self.local_files_only,
                device=self.device,
            ),
        }

    @staticmethod
    def dependency_available() -> bool:
        return all(
            importlib.util.find_spec(name) is not None
            for name in ("torch", "diffusers", "transformers", "accelerate")
        )

    def get(self, model: str):
        try:
            return self._providers[model]
        except KeyError as exc:
            raise SyntheticValidationError(
                f"unknown diffusion model '{model}'; choose one of {sorted(self._providers)}"
            ) from exc

    def statuses(self) -> list[DiffusionModelStatus]:
        dependency = self.dependency_available()
        return [
            DiffusionModelStatus(
                model="sdxl_inpaint",
                display_name="SDXL Inpainting",
                provider="diffusers.AutoPipelineForInpainting",
                model_id=SDXLInpaintProvider.default_model_id,
                dependency_available=dependency,
                loaded=self._providers["sdxl_inpaint"].loaded,
                local_files_only=self.local_files_only,
                cache_dir=str(self.cache_dir / "sdxl_inpaint"),
                device=self.device,
                notes="Default local diffusion provider; recommended starting point for 24 GB-class GPUs.",
            ),
            DiffusionModelStatus(
                model="flux_fill",
                display_name="FLUX.1 Fill dev",
                provider="diffusers.FluxFillPipeline",
                model_id=FluxFillProvider.default_model_id,
                dependency_available=dependency,
                loaded=self._providers["flux_fill"].loaded,
                local_files_only=self.local_files_only,
                cache_dir=str(self.cache_dir / "flux_fill"),
                device=self.device,
                notes="Experimental high-quality provider; uses CPU offload by default on CUDA.",
            ),
        ]

    def unload(self, model: str | None = None) -> None:
        if model is None:
            for provider in self._providers.values():
                provider.unload()
            return
        self.get(model).unload()
