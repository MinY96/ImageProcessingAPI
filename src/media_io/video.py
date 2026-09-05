from __future__ import annotations

from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

from src.schemas import ColorSpace, ImageData


def iter_video_frames(
    source: str | Path | int,
    *,
    max_frames: int | None = None,
    max_pixels_per_frame: int = 16_000_000,
) -> Iterator[ImageData]:
    """비디오 파일 또는 카메라를 frame-by-frame으로 읽어 메모리 누적을 피한다."""
    import cv2

    capture = cv2.VideoCapture(str(source) if isinstance(source, Path) else source)
    if not capture.isOpened():
        capture.release()
        raise ValueError(f"could not open video source: {source}")
    index = 0
    try:
        while max_frames is None or index < max_frames:
            received, frame = capture.read()
            if not received:
                break
            pixels = int(frame.shape[0]) * int(frame.shape[1])
            if pixels > max_pixels_per_frame:
                raise ValueError(
                    f"video frame exceeds pixel limit: {pixels} > {max_pixels_per_frame}"
                )
            yield ImageData(
                data=frame,
                color_space=ColorSpace.BGR,
                name=f"frame_{index:08d}",
            )
            index += 1
    finally:
        capture.release()


def write_video(
    path: str | Path,
    frames: Iterable[ImageData],
    *,
    fps: float,
    fourcc: str = "mp4v",
) -> Path:
    """Iterable을 순회하며 즉시 기록하므로 전체 영상을 메모리에 올리지 않는다."""
    import cv2

    if fps <= 0:
        raise ValueError("fps must be positive")
    if len(fourcc) != 4:
        raise ValueError("fourcc must contain exactly four characters")
    target = Path(path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    iterator = iter(frames)
    try:
        first = next(iterator)
    except StopIteration as exc:
        raise ValueError("frames must not be empty") from exc
    expected = (first.width, first.height)
    writer = cv2.VideoWriter(
        str(target), cv2.VideoWriter_fourcc(*fourcc), float(fps), expected, True
    )
    if not writer.isOpened():
        writer.release()
        raise ValueError(f"could not open video writer: {target}")

    def bgr(image: ImageData):
        from src.image_processing.common import to_bgr

        if (image.width, image.height) != expected:
            raise ValueError("all video frames must have the same dimensions")
        return to_bgr(image)

    try:
        writer.write(bgr(first))
        for frame in iterator:
            writer.write(bgr(frame))
    finally:
        writer.release()
    return target
