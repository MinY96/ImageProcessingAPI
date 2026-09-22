from __future__ import annotations

from typing import Any

import cv2
import numpy as np

from src.schemas import ColorSpace, ImageData

from .errors import SyntheticValidationError


def ensure_uint8_image(image: ImageData, *, name: str) -> None:
    if image.data.dtype != np.uint8:
        raise SyntheticValidationError(f"{name} must use uint8 pixels")
    if image.data.ndim not in {2, 3}:
        raise SyntheticValidationError(f"{name} must be a 2D or 3D image")


def to_bgr(image: ImageData, *, name: str = "image") -> np.ndarray:
    ensure_uint8_image(image, name=name)
    array = image.data
    if image.color_space == ColorSpace.BGR:
        return np.ascontiguousarray(array)
    if image.color_space == ColorSpace.RGB:
        return cv2.cvtColor(array, cv2.COLOR_RGB2BGR)
    if image.color_space in {ColorSpace.GRAY, ColorSpace.BINARY}:
        return cv2.cvtColor(array, cv2.COLOR_GRAY2BGR)
    if image.color_space == ColorSpace.BGRA:
        return cv2.cvtColor(array, cv2.COLOR_BGRA2BGR)
    if image.color_space == ColorSpace.RGBA:
        return cv2.cvtColor(array, cv2.COLOR_RGBA2BGR)
    raise SyntheticValidationError(
        f"{name} color_space={image.color_space.value} is not supported for synthetic generation"
    )


def to_gray_mask(mask: ImageData, *, width: int, height: int, name: str = "mask") -> np.ndarray:
    ensure_uint8_image(mask, name=name)
    if mask.width != width or mask.height != height:
        raise SyntheticValidationError(
            f"{name} size must match source image: expected {width}x{height}, "
            f"got {mask.width}x{mask.height}"
        )
    array = mask.data
    if array.ndim == 3:
        if array.shape[2] == 4:
            array = cv2.cvtColor(array, cv2.COLOR_BGRA2GRAY)
        else:
            array = cv2.cvtColor(array, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(array, 0, 255, cv2.THRESH_BINARY)
    if not np.any(binary):
        raise SyntheticValidationError(f"{name} must contain at least one non-zero pixel")
    return np.ascontiguousarray(binary)


def image_data_bgr(array: np.ndarray, *, name: str | None = None) -> ImageData:
    return ImageData(data=np.ascontiguousarray(array), color_space=ColorSpace.BGR, name=name)


def image_data_mask(array: np.ndarray, *, name: str | None = None) -> ImageData:
    binary = np.where(array > 0, 255, 0).astype(np.uint8)
    return ImageData(data=np.ascontiguousarray(binary), color_space=ColorSpace.BINARY, name=name)


def difference_image(original: np.ndarray, generated: np.ndarray) -> ImageData:
    diff = cv2.absdiff(original, generated)
    return image_data_bgr(diff, name="difference")


def mask_bbox(mask: np.ndarray) -> tuple[int, int, int, int]:
    ys, xs = np.where(mask > 0)
    if xs.size == 0 or ys.size == 0:
        raise SyntheticValidationError("target mask is empty")
    x1, x2 = int(xs.min()), int(xs.max()) + 1
    y1, y2 = int(ys.min()), int(ys.max()) + 1
    return x1, y1, x2, y2


def inside_feather_alpha(mask: np.ndarray, feather_px: int) -> np.ndarray:
    binary = (mask > 0).astype(np.uint8)
    if feather_px <= 0:
        return binary.astype(np.float32)[..., None]
    distance = cv2.distanceTransform(binary, cv2.DIST_L2, 5)
    alpha = np.clip(distance / max(float(feather_px), 1.0), 0.0, 1.0)
    alpha[binary == 0] = 0.0
    return alpha.astype(np.float32)[..., None]


def exact_mask_composite(
    original: np.ndarray,
    generated: np.ndarray,
    mask: np.ndarray,
    *,
    feather_px: int,
) -> np.ndarray:
    if generated.shape != original.shape:
        generated = cv2.resize(generated, (original.shape[1], original.shape[0]), interpolation=cv2.INTER_LINEAR)
    alpha = inside_feather_alpha(mask, feather_px)
    output = original.astype(np.float32) * (1.0 - alpha)
    output += generated.astype(np.float32) * alpha
    return np.rint(np.clip(output, 0, 255)).astype(np.uint8)


def local_color_match(asset: np.ndarray, background_patch: np.ndarray, *, strength: float = 0.65) -> np.ndarray:
    if asset.size == 0 or background_patch.size == 0:
        return asset
    strength = float(np.clip(strength, 0.0, 1.0))
    a = asset.astype(np.float32)
    b = background_patch.astype(np.float32)
    a_mean = a.reshape(-1, 3).mean(axis=0)
    b_mean = b.reshape(-1, 3).mean(axis=0)
    adjusted = a + (b_mean - a_mean) * strength
    return np.clip(adjusted, 0, 255).astype(np.uint8)


def apply_noise_match(asset: np.ndarray, background_patch: np.ndarray, *, strength: float = 0.35, rng: np.random.Generator | None = None) -> np.ndarray:
    if asset.size == 0 or background_patch.size == 0 or strength <= 0:
        return asset
    rng = rng or np.random.default_rng()
    gray = cv2.cvtColor(background_patch, cv2.COLOR_BGR2GRAY)
    sigma = float(np.std(gray - cv2.GaussianBlur(gray, (0, 0), 1.0)))
    if sigma <= 0:
        return asset
    noise = rng.normal(0.0, sigma * float(strength), size=asset.shape).astype(np.float32)
    return np.clip(asset.astype(np.float32) + noise, 0, 255).astype(np.uint8)


def parse_color(value: Any, *, default: tuple[int, int, int]) -> tuple[int, int, int]:
    if value is None:
        return default
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise SyntheticValidationError("color must be a 3-item BGR list")
    try:
        channels = tuple(int(np.clip(int(item), 0, 255)) for item in value)
    except Exception as exc:
        raise SyntheticValidationError("color must contain integer-compatible channel values") from exc
    return channels  # type: ignore[return-value]
