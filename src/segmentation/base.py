"""Segmenter protocol lives in src/types.py. This module is a placeholder
for shared helpers (mask cleanup, contour extraction) used by every implementation."""

from __future__ import annotations

import cv2
import numpy as np


def clean_mask(mask: np.ndarray, erode_base_pct: float = 0.02) -> np.ndarray:
    """Close small holes, remove noise, keep largest blob, erode bottom strip."""
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    m = cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_CLOSE, kernel)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, kernel)

    m = largest_component(m)

    if erode_base_pct > 0:
        h = m.shape[0]
        base_rows = int(h * erode_base_pct)
        strip = m[-base_rows:, :]
        erode_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 5))
        m[-base_rows:, :] = cv2.erode(strip, erode_kernel)
    return m.astype(bool)


def largest_component(binary: np.ndarray) -> np.ndarray:
    num, labels, stats, _ = cv2.connectedComponentsWithStats(binary.astype(np.uint8), connectivity=8)
    if num <= 1:
        return np.zeros_like(binary, dtype=np.uint8)
    areas = stats[1:, cv2.CC_STAT_AREA]
    largest_label = 1 + int(np.argmax(areas))
    return (labels == largest_label).astype(np.uint8)


def solidity(mask: np.ndarray) -> float:
    """Mask area / convex-hull area. Clean cylinder silhouettes ≈ 0.95+;
    jagged/noisy masks drop. Shared by segmenters (as confidence) and
    validation (as structural sanity check)."""
    contours, _ = cv2.findContours(
        mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    if not contours:
        return 0.0
    cnt = max(contours, key=cv2.contourArea)
    area = cv2.contourArea(cnt)
    if area == 0:
        return 0.0
    hull = cv2.convexHull(cnt)
    hull_area = cv2.contourArea(hull)
    if hull_area == 0:
        return 0.0
    return float(area / hull_area)
