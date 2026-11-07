from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import cv2

from mechanical_control.config import CAPTURE_HEIGHT, CAPTURE_WIDTH, CAPTURES_DIR

_INTEGRATED_NAME_HINTS = (
    "integrated",
    "built-in",
    "built in",
    "facetime",
    "hp wide vision",
    "truevision",
    "lenovo easy",
    "laptop",
    "cyberlink",
    "virtual camera",
    "obs virtual",
)


def _list_dshow_camera_names() -> list[str] | None:
    if sys.platform != "win32":
        return None
    try:
        from pygrabber.dshow_graph import FilterGraph
    except ImportError:
        return None
    try:
        names = FilterGraph().get_input_devices()
    except Exception:
        return None
    if not isinstance(names, list) or not names:
        return None
    return [str(n) for n in names]


def _pick_usb_preferred_index(names: list[str]) -> tuple[int, str]:
    lowered = [n.lower() for n in names]
    for i, n in enumerate(lowered):
        if "usb" in n or "uvc" in n:
            return i, names[i]
    for i, n in enumerate(lowered):
        if not any(h in n for h in _INTEGRATED_NAME_HINTS):
            return i, names[i]
    return 0, names[0]


def resolve_camera_index(explicit_index: int | None) -> tuple[int, str | None]:
    if explicit_index is not None:
        return explicit_index, None
    names = _list_dshow_camera_names()
    if not names:
        return 0, None
    idx, label = _pick_usb_preferred_index(names)
    return idx, label


def open_capture(index: int, backend: str) -> cv2.VideoCapture:
    if sys.platform == "win32":
        if backend == "dshow":
            return cv2.VideoCapture(index, cv2.CAP_DSHOW)
        if backend == "msmf":
            return cv2.VideoCapture(index, cv2.CAP_MSMF)
    return cv2.VideoCapture(index)


def capture_one(
    output_dir: Path | None = None,
    camera_index: int | None = None,
    backend: str = "dshow",
    warmup: int = 25,
    width: int = CAPTURE_WIDTH,
    height: int = CAPTURE_HEIGHT,
) -> Path:
    out_dir = output_dir or CAPTURES_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    cam_index, cam_label = resolve_camera_index(camera_index)
    if camera_index is None and cam_label:
        print(f"[INFO] camera: index={cam_index} ({cam_label})")

    cap = open_capture(cam_index, backend)
    if not cap.isOpened():
        raise RuntimeError(f"cannot open camera index={cam_index}, backend={backend}")

    if width > 0 and height > 0:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, float(width))
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, float(height))

    for _ in range(max(0, warmup)):
        cap.read()

    ok, frame = cap.read()
    cap.release()

    if not ok or frame is None:
        raise RuntimeError("failed to read frame from camera")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"capture_{ts}.jpg"
    if not cv2.imwrite(str(out_path), frame):
        raise RuntimeError(f"failed to write {out_path}")

    h, w = frame.shape[:2]
    print(f"[INFO] saved capture -> {out_path} ({w}x{h})")
    return out_path
