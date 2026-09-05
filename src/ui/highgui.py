from __future__ import annotations

import os
import sys
from collections.abc import Callable
from pathlib import Path

import numpy as np

from src.schemas import ImageData


def is_gui_available() -> bool:
    if sys.platform.startswith(("win", "darwin")):
        return True
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def _require_gui() -> None:
    if not is_gui_available():
        raise RuntimeError(
            "OpenCV HighGUI is unavailable in this headless environment; "
            "use the FastAPI response or Notebook visualization instead"
        )


def show_image(
    image: ImageData,
    *,
    title: str = "image",
    delay_ms: int = 0,
    destroy: bool = True,
) -> int:
    """로컬 개발 환경 전용 HighGUI preview. Registry에는 등록하지 않는다."""
    import cv2

    _require_gui()
    cv2.namedWindow(title, cv2.WINDOW_NORMAL)
    cv2.imshow(title, image.data)
    key = int(cv2.waitKey(delay_ms))
    if destroy:
        cv2.destroyWindow(title)
    return key


def select_rectangle(
    image: ImageData,
    *,
    title: str = "Select ROI",
) -> tuple[int, int, int, int]:
    """마우스로 ROI를 선택한다. 서버가 아닌 로컬 도구에서만 사용한다."""
    import cv2

    from src.image_processing.common import to_bgr

    _require_gui()
    rectangle = cv2.selectROI(title, to_bgr(image), showCrosshair=True)
    cv2.destroyWindow(title)
    return tuple(int(value) for value in rectangle)


def paint_image(
    image: ImageData,
    *,
    title: str = "Paint",
    brush_radius: int = 5,
    color: tuple[int, int, int] = (0, 0, 255),
) -> ImageData:
    """마우스 왼쪽 버튼으로 그린 복사본을 반환한다. ESC 또는 q로 종료한다."""
    import cv2

    from src.image_processing.common import as_image, to_bgr
    from src.schemas import ColorSpace

    _require_gui()
    if brush_radius < 1:
        raise ValueError("brush_radius must be >= 1")
    if len(color) != 3 or any(value < 0 or value > 255 for value in color):
        raise ValueError("color must be a BGR triplet in [0, 255]")

    canvas = to_bgr(image)
    drawing = False

    def on_mouse(event, x, y, flags, userdata):
        nonlocal drawing
        if event == cv2.EVENT_LBUTTONDOWN:
            drawing = True
        elif event == cv2.EVENT_LBUTTONUP:
            drawing = False
        if drawing or event == cv2.EVENT_LBUTTONDOWN:
            cv2.circle(canvas, (x, y), brush_radius, color, -1, cv2.LINE_AA)

    cv2.namedWindow(title, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(title, on_mouse)
    while True:
        cv2.imshow(title, canvas)
        key = cv2.waitKey(20) & 0xFF
        if key in {27, ord("q")}:
            break
    cv2.destroyWindow(title)
    return as_image(canvas, source=image, color_space=ColorSpace.BGR)


def color_palette(
    *,
    title: str = "Color Palette",
    width: int = 512,
    height: int = 320,
) -> tuple[int, int, int]:
    """B/G/R trackbar를 제공하고 종료 시 선택한 BGR 색을 반환한다."""
    import cv2

    _require_gui()
    if width < 1 or height < 1:
        raise ValueError("palette dimensions must be positive")
    canvas = np.zeros((height, width, 3), dtype=np.uint8)
    cv2.namedWindow(title, cv2.WINDOW_NORMAL)
    for channel in ("B", "G", "R"):
        cv2.createTrackbar(channel, title, 0, 255, lambda value: None)
    while True:
        selected = tuple(cv2.getTrackbarPos(channel, title) for channel in ("B", "G", "R"))
        canvas[:] = selected
        cv2.imshow(title, canvas)
        key = cv2.waitKey(20) & 0xFF
        if key in {27, ord("q")}:
            break
    cv2.destroyWindow(title)
    return selected


def play_video(
    source: str | Path | int,
    *,
    title: str = "Video",
    delay_ms: int = 30,
    transform: Callable[[ImageData], ImageData] | None = None,
) -> int:
    """파일/카메라 영상을 재생하며 q 또는 ESC까지 표시한 frame 수를 반환한다."""
    import cv2

    from src.media_io import iter_video_frames

    _require_gui()
    if delay_ms < 1:
        raise ValueError("delay_ms must be >= 1")
    shown = 0
    try:
        for frame in iter_video_frames(source):
            rendered = transform(frame) if transform is not None else frame
            if not isinstance(rendered, ImageData):
                raise TypeError("transform must return ImageData")
            cv2.imshow(title, rendered.data)
            shown += 1
            if cv2.waitKey(delay_ms) & 0xFF in {27, ord("q")}:
                break
    finally:
        cv2.destroyWindow(title)
    return shown
