"""CPU-only fallback segmenter. Always available — no torch, no GPU, no model download."""

from __future__ import annotations

import cv2
import numpy as np

from ..types import ImageSet, SegmentationResult, SegmentedImage
from .base import clean_mask, solidity


class GrabCutSegmenter:
    def __init__(self, bbox_inset: float = 0.1, iterations: int = 5):
        self.bbox_inset = bbox_inset
        self.iterations = iterations

    def segment(self, image_set: ImageSet) -> SegmentationResult:
        segmented: list[SegmentedImage] = []
        for img in image_set.images:
            mask = self._segment_one(img.raw)
            # Confidence = solidity — same signal HSV uses, so downstream code
            # (validation, reporting) can treat both segmenters uniformly.
            conf = solidity(mask) if mask.any() else 0.0
            segmented.append(
                SegmentedImage(source=img, mask=mask, confidence=float(conf))
            )
        return SegmentationResult(segmented=segmented)

    def _segment_one(self, rgb: np.ndarray) -> np.ndarray:
        h, w = rgb.shape[:2]
        inset_x, inset_y = int(w * self.bbox_inset), int(h * self.bbox_inset)
        rect = (inset_x, inset_y, w - 2 * inset_x, h - 2 * inset_y)

        mask = np.zeros((h, w), dtype=np.uint8)
        bgd = np.zeros((1, 65), dtype=np.float64)
        fgd = np.zeros((1, 65), dtype=np.float64)
        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        cv2.grabCut(bgr, mask, rect, bgd, fgd, self.iterations, cv2.GC_INIT_WITH_RECT)
        binary = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 1, 0).astype(np.uint8)
        return clean_mask(binary)
