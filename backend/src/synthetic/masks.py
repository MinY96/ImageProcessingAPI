from __future__ import annotations

import cv2
import numpy as np

from src.schemas import ImageData

from .common import to_gray_mask
from .errors import SyntheticValidationError
from .schemas import SyntheticMaskSpec, SyntheticMaskType


def resolve_target_mask(
    *,
    source: ImageData,
    uploaded_mask: ImageData | None,
    spec: SyntheticMaskSpec | None,
    seed: int,
) -> tuple[np.ndarray, SyntheticMaskSpec]:
    resolved = spec or SyntheticMaskSpec()
    if uploaded_mask is not None:
        return (
            to_gray_mask(uploaded_mask, width=source.width, height=source.height, name="target_mask"),
            resolved,
        )
    if resolved.type == SyntheticMaskType.MANUAL:
        raise SyntheticValidationError("manual mask type requires target_mask upload")
    return generate_mask(source.width, source.height, resolved, seed=seed), resolved


def generate_mask(width: int, height: int, spec: SyntheticMaskSpec, *, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    mask = np.zeros((height, width), dtype=np.uint8)
    cx = int(round(spec.center_x * (width - 1)))
    cy = int(round(spec.center_y * (height - 1)))
    rw = max(2, int(round(spec.width_ratio * width)))
    rh = max(2, int(round(spec.height_ratio * height)))

    if spec.type == SyntheticMaskType.RECTANGLE:
        rect = ((float(cx), float(cy)), (float(rw), float(rh)), float(spec.rotation_deg))
        points = np.rint(cv2.boxPoints(rect)).astype(np.int32)
        cv2.fillConvexPoly(mask, points, 255)

    elif spec.type == SyntheticMaskType.ELLIPSE:
        cv2.ellipse(mask, (cx, cy), (rw // 2, rh // 2), spec.rotation_deg, 0, 360, 255, -1)

    elif spec.type == SyntheticMaskType.POLYGON:
        points = np.array(
            [[int(round(x * (width - 1))), int(round(y * (height - 1)))] for x, y in spec.polygon],
            dtype=np.int32,
        )
        cv2.fillPoly(mask, [points], 255)

    elif spec.type == SyntheticMaskType.RANDOM_BLOB:
        point_count = int(spec.parameters.get("points", 14))
        point_count = int(np.clip(point_count, 6, 64))
        irregularity = float(np.clip(spec.parameters.get("irregularity", 0.35), 0.0, 0.9))
        angles = np.sort(rng.uniform(0.0, 2.0 * np.pi, size=point_count))
        points = []
        for angle in angles:
            radius_scale = 1.0 + rng.uniform(-irregularity, irregularity)
            x = cx + np.cos(angle) * rw * 0.5 * radius_scale
            y = cy + np.sin(angle) * rh * 0.5 * radius_scale
            points.append([int(round(x)), int(round(y))])
        points_array = np.asarray(points, dtype=np.int32)
        cv2.fillPoly(mask, [points_array], 255)
        smooth = int(spec.parameters.get("smooth", 7))
        smooth = max(0, smooth)
        if smooth > 0:
            k = smooth if smooth % 2 == 1 else smooth + 1
            blurred = cv2.GaussianBlur(mask, (k, k), 0)
            _, mask = cv2.threshold(blurred, 96, 255, cv2.THRESH_BINARY)

    elif spec.type == SyntheticMaskType.PERLIN:
        # Lightweight dependency-free pseudo-Perlin mask: low-resolution random field + cubic upsample.
        grid = int(spec.parameters.get("grid", 12))
        grid = int(np.clip(grid, 3, 64))
        threshold = float(np.clip(spec.parameters.get("threshold", 0.58), 0.05, 0.95))
        small = rng.random((grid, grid), dtype=np.float32)
        field = cv2.resize(small, (rw, rh), interpolation=cv2.INTER_CUBIC)
        field = cv2.GaussianBlur(field, (0, 0), max(1.0, min(rw, rh) / 30.0))
        local = np.where(field >= threshold, 255, 0).astype(np.uint8)
        x1 = max(0, cx - rw // 2)
        y1 = max(0, cy - rh // 2)
        x2 = min(width, x1 + rw)
        y2 = min(height, y1 + rh)
        mask[y1:y2, x1:x2] = local[: y2 - y1, : x2 - x1]

    elif spec.type == SyntheticMaskType.CRACK:
        segments = int(np.clip(spec.parameters.get("segments", 7), 2, 64))
        thickness = int(np.clip(spec.parameters.get("thickness", max(1, int(min(width, height) * 0.003))), 1, 64))
        length = max(4, rw)
        angle = np.deg2rad(spec.rotation_deg)
        points = [(float(cx - np.cos(angle) * length / 2), float(cy - np.sin(angle) * length / 2))]
        step = length / segments
        for index in range(1, segments + 1):
            jitter_x = rng.normal(0.0, rh * 0.12)
            jitter_y = rng.normal(0.0, rh * 0.12)
            x = points[0][0] + np.cos(angle) * step * index + jitter_x
            y = points[0][1] + np.sin(angle) * step * index + jitter_y
            points.append((x, y))
        pts = np.rint(points).astype(np.int32)
        cv2.polylines(mask, [pts], False, 255, thickness=thickness, lineType=cv2.LINE_AA)
        if bool(spec.parameters.get("branches", True)):
            for branch_index in range(max(1, segments // 3)):
                anchor = pts[int(rng.integers(1, len(pts) - 1))]
                theta = angle + rng.choice([-1, 1]) * rng.uniform(0.45, 1.0)
                branch_len = length * rng.uniform(0.12, 0.28)
                end = np.array([
                    anchor[0] + np.cos(theta) * branch_len,
                    anchor[1] + np.sin(theta) * branch_len,
                ])
                cv2.line(mask, tuple(anchor), tuple(np.rint(end).astype(int)), 255, max(1, thickness // 2), cv2.LINE_AA)
        _, mask = cv2.threshold(mask, 1, 255, cv2.THRESH_BINARY)

    else:
        raise SyntheticValidationError(f"unsupported mask type: {spec.type.value}")

    if not np.any(mask):
        raise SyntheticValidationError("generated target mask is empty; adjust mask parameters")
    return mask
