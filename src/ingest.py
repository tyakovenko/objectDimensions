"""Load 4 photos from a directory, parse view labels from filenames."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ExifTags

from .types import CaptureImage, ImageSet

EXPECTED_VIEWS = ("front", "right", "back", "left")


def _read_exif(path: Path) -> dict:
    try:
        img = Image.open(path)
        raw = img._getexif() or {}
        return {ExifTags.TAGS.get(k, k): v for k, v in raw.items()}
    except Exception:
        return {}


def ingest(directory: Path, pose_id: str = "default") -> ImageSet:
    directory = Path(directory)
    if not directory.is_dir():
        raise FileNotFoundError(f"Not a directory: {directory}")

    images: list[CaptureImage] = []
    for view in EXPECTED_VIEWS:
        matches = list(directory.glob(f"{view}.*"))
        matches = [p for p in matches if p.suffix.lower() in {".jpg", ".jpeg", ".png"}]
        if not matches:
            raise FileNotFoundError(
                f"Missing view '{view}' in {directory}. "
                f"Expected {view}.jpg / {view}.png."
            )
        path = matches[0]
        raw = cv2.imread(str(path))
        if raw is None:
            raise ValueError(f"Could not decode image: {path}")
        raw = cv2.cvtColor(raw, cv2.COLOR_BGR2RGB)
        images.append(
            CaptureImage(
                path=path,
                view=view,
                pose_id=pose_id,
                raw=raw,
                exif=_read_exif(path),
            )
        )
    return ImageSet(images=images)
