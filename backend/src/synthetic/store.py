from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from uuid import uuid4

import cv2
import numpy as np

from src.media_io.image import read_image, write_image
from src.schemas import ColorSpace, ImageData

from .errors import SyntheticAssetNotFoundError, SyntheticAssetStoreError, SyntheticValidationError
from .schemas import SyntheticAssetCreateRequest, SyntheticAssetSummary


@dataclass(slots=True)
class SyntheticAssetData:
    summary: SyntheticAssetSummary
    image: ImageData
    mask: ImageData | None


class SyntheticAssetStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self._lock = RLock()

    def _asset_dir(self, asset_id: str) -> Path:
        return self.root / asset_id

    def list(self) -> list[SyntheticAssetSummary]:
        if not self.root.exists():
            return []
        result: list[SyntheticAssetSummary] = []
        for path in sorted(self.root.iterdir()):
            if not path.is_dir():
                continue
            meta_path = path / "metadata.json"
            if not meta_path.is_file():
                continue
            try:
                result.append(SyntheticAssetSummary.model_validate_json(meta_path.read_text(encoding="utf-8")))
            except Exception as exc:
                raise SyntheticAssetStoreError(f"could not read synthetic asset metadata: {meta_path}") from exc
        result.sort(key=lambda item: (item.created_at, item.asset_id), reverse=True)
        return result

    def save(
        self,
        request: SyntheticAssetCreateRequest,
        *,
        image: ImageData,
        mask: ImageData | None,
    ) -> SyntheticAssetSummary:
        asset_id = request.asset_id or uuid4().hex
        target = self._asset_dir(asset_id)
        with self._lock:
            if target.exists():
                raise SyntheticValidationError(f"synthetic asset already exists: {asset_id}")
            try:
                target.mkdir(parents=True, exist_ok=False)
                write_image(target / "image.png", image)
                if mask is not None:
                    write_image(target / "mask.png", mask)
                summary = SyntheticAssetSummary(
                    asset_id=asset_id,
                    name=request.name,
                    category=request.category,
                    description=request.description,
                    tags=request.tags,
                    has_mask=mask is not None,
                    width=image.width,
                    height=image.height,
                    created_at=datetime.now(timezone.utc),
                    metadata=request.metadata,
                )
                (target / "metadata.json").write_text(
                    summary.model_dump_json(indent=2),
                    encoding="utf-8",
                )
                return summary
            except Exception:
                if target.exists():
                    shutil.rmtree(target, ignore_errors=True)
                raise

    def get(self, asset_id: str) -> SyntheticAssetData:
        target = self._asset_dir(asset_id)
        meta_path = target / "metadata.json"
        image_path = target / "image.png"
        if not meta_path.is_file() or not image_path.is_file():
            raise SyntheticAssetNotFoundError(f"synthetic asset does not exist: {asset_id}")
        try:
            summary = SyntheticAssetSummary.model_validate_json(meta_path.read_text(encoding="utf-8"))
            image = read_image(image_path)
            mask_path = target / "mask.png"
            mask = None
            if mask_path.is_file():
                raw = cv2.imdecode(np.frombuffer(mask_path.read_bytes(), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
                if raw is None:
                    raise ValueError("invalid asset mask")
                mask = ImageData(data=raw, color_space=ColorSpace.BINARY, name=mask_path.name)
            return SyntheticAssetData(summary=summary, image=image, mask=mask)
        except SyntheticAssetNotFoundError:
            raise
        except Exception as exc:
            raise SyntheticAssetStoreError(f"could not load synthetic asset: {asset_id}") from exc

    def delete(self, asset_id: str) -> None:
        target = self._asset_dir(asset_id)
        if not target.exists():
            raise SyntheticAssetNotFoundError(f"synthetic asset does not exist: {asset_id}")
        with self._lock:
            try:
                shutil.rmtree(target)
            except Exception as exc:
                raise SyntheticAssetStoreError(f"could not delete synthetic asset: {asset_id}") from exc
