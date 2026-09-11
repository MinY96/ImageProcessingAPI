from __future__ import annotations

from pathlib import Path

import numpy as np

from src.schemas import ColorSpace, ImageData


def read_image(
    path: str | Path,
    *,
    color_space: ColorSpace | None = None,
    max_pixels: int = 64_000_000,
) -> ImageData:
    """Unicode 경로를 포함한 이미지를 ImageData로 읽는다."""
    import cv2

    resolved = Path(path).expanduser().resolve()
    if not resolved.is_file():
        raise FileNotFoundError(resolved)
    encoded = np.frombuffer(resolved.read_bytes(), dtype=np.uint8)
    image = cv2.imdecode(encoded, cv2.IMREAD_UNCHANGED)
    if image is None:
        raise ValueError(f"OpenCV could not decode image: {resolved}")
    pixels = int(image.shape[0]) * int(image.shape[1])
    if pixels > max_pixels:
        raise ValueError(f"image exceeds pixel limit: {pixels} > {max_pixels}")
    if image.ndim == 2:
        inferred = ColorSpace.GRAY
    elif image.shape[2] == 3:
        inferred = ColorSpace.BGR
    elif image.shape[2] == 4:
        inferred = ColorSpace.BGRA
    else:
        raise ValueError(f"unsupported image shape: {image.shape}")
    requested = color_space or inferred
    compatible = {
        ColorSpace.GRAY: {ColorSpace.GRAY, ColorSpace.BINARY},
        ColorSpace.BGR: {ColorSpace.BGR},
        ColorSpace.BGRA: {ColorSpace.BGRA},
    }[inferred]
    if requested not in compatible:
        raise ValueError(
            f"color_space={requested.value} is incompatible with decoded {inferred.value}"
        )
    return ImageData(data=image, color_space=requested, name=resolved.name)


def write_image(
    path: str | Path,
    image: ImageData,
    *,
    parameters: list[int] | None = None,
) -> Path:
    """ImageData를 Unicode 경로에 저장한다."""
    import cv2

    target = Path(path).expanduser().resolve()
    if not target.suffix:
        raise ValueError("output path must include an image extension")
    target.parent.mkdir(parents=True, exist_ok=True)
    array = image.data
    if image.color_space == ColorSpace.RGB:
        array = cv2.cvtColor(array, cv2.COLOR_RGB2BGR)
    elif image.color_space == ColorSpace.RGBA:
        array = cv2.cvtColor(array, cv2.COLOR_RGBA2BGRA)
    success, encoded = cv2.imencode(target.suffix, array, parameters or [])
    if not success:
        raise ValueError(f"OpenCV could not encode image as {target.suffix}")
    target.write_bytes(encoded.tobytes())
    return target
