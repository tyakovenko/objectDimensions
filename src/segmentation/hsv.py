"""HSV color-threshold segmenter.

Primary MVP segmenter for distinctly-colored objects (yellow corn can on
gray/neutral background). Deterministic, fast, no iterative fitting, no
GPU. Ties directly to the course's histogram / color-space material.

Not suitable for achromatic or low-saturation objects — use GrabCut or SAM
for those.
"""

from __future__ import annotations

import cv2
import numpy as np

from ..types import ImageSet, SegmentationResult, SegmentedImage
from .base import largest_component as _largest_component, solidity as _solidity


class HSVSegmenter:
    def __init__(
        self,
        hsv_lower: tuple[int, int, int] = (15, 100, 100),
        hsv_upper: tuple[int, int, int] = (40, 255, 255),
        close_kernel_px: int = 25,
        open_kernel_px: int = 5,
    ):
        self.hsv_lower = np.array(hsv_lower, dtype=np.uint8)
        self.hsv_upper = np.array(hsv_upper, dtype=np.uint8)
        self.close_kernel_px = close_kernel_px
        self.open_kernel_px = open_kernel_px

    def segment(self, image_set: ImageSet) -> SegmentationResult:
        segmented: list[SegmentedImage] = []
        for img in image_set.images:
            mask, conf = self._segment_one(img.raw)
            segmented.append(SegmentedImage(source=img, mask=mask, confidence=conf))
        return SegmentationResult(segmented=segmented)

    def _segment_one(self, rgb: np.ndarray) -> tuple[np.ndarray, float]:
        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
        raw = cv2.inRange(hsv, self.hsv_lower, self.hsv_upper)

        # Close fills rim gaps (silver can top/bottom, dark label print).
        close_k = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (self.close_kernel_px, self.close_kernel_px)
        )
        closed = cv2.morphologyEx(raw, cv2.MORPH_CLOSE, close_k)

        # Open removes speckle (stray yellow pixels in background).
        open_k = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (self.open_kernel_px, self.open_kernel_px)
        )
        opened = cv2.morphologyEx(closed, cv2.MORPH_OPEN, open_k)

        largest = _largest_component(opened)
        if largest.sum() == 0:
            return largest.astype(bool), 0.0

        # Confidence = solidity (area / convex-hull area). A clean cylindrical
        # silhouette is ~0.95+; a noisy blob or partial mask is lower.
        conf = _solidity(largest)
        return largest.astype(bool), float(conf)
