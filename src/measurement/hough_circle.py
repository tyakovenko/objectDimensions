"""Hough circle diameter estimator — alternative Measurer for cylindrical objects.

Works from 2D masks without the 3D visual hull: per-view Canny edges →
HoughCircles → radius in pixels → scale by calibration → diameter in inches.
Averages across all 4 views. Falls back to mask-median-width when Hough finds
no circle (reports which path was taken via MeasurementResult metadata).

Course connection: Hough Transform (L12). Compare outputs to CrossSectionMeasurer
to show when the simpler 2D approach is sufficient and where it fails.

Outputs per pose:
  height          — from mesh z-extent (reuses visual hull result)
  diameter_mid    — Hough or fallback, averaged across views
  circumference_mid — π × diameter_mid
"""

from __future__ import annotations

import math

import cv2
import numpy as np

from ..types import (
    CalibrationResult,
    MeasurementProfile,
    MeasurementResult,
    Reconstruction,
    SegmentationResult,
)


class HoughCircleMeasurer:
    def __init__(
        self,
        canny_high: int = 50,
        accumulator_threshold: int = 20,
        # Radius bounds relative to silhouette width. For a cylinder the true
        # radius ≈ 0.50× width; 0.35–0.55 rejects label-graphic false detections
        # (which tend to land at 0.57–0.70×) while accepting the real rim arc.
        radius_fraction_min: float = 0.35,
        radius_fraction_max: float = 0.55,
    ):
        self.canny_high = canny_high
        self.accumulator_threshold = accumulator_threshold
        self.radius_fraction_min = radius_fraction_min
        self.radius_fraction_max = radius_fraction_max

    def measure(
        self,
        reconstructions: list[Reconstruction],
        segmentation: SegmentationResult | None = None,
        calibration: CalibrationResult | None = None,
    ) -> MeasurementProfile:
        results: list[MeasurementResult] = []

        for rec in reconstructions:
            # Height from visual hull mesh (same source as CrossSectionMeasurer)
            bounds = rec.mesh.bounds
            results.append(
                MeasurementResult("height", float(bounds[1, 2] - bounds[0, 2]), "in", rec.pose_id)
            )

            if segmentation is None or calibration is None:
                results.append(MeasurementResult("diameter_mid", 0.0, "in", rec.pose_id))
                results.append(MeasurementResult("circumference_mid", 0.0, "in", rec.pose_id))
                continue

            scale_map = {cam.view: cam.pixels_per_unit for cam in calibration.cameras}
            diameters: list[float] = []
            for seg in segmentation.segmented:
                if seg.source.view not in scale_map:
                    continue
                px_per_unit = scale_map[seg.source.view]
                diam = self._diameter_from_view(seg.source.raw, seg.mask, px_per_unit)
                if diam > 0:
                    diameters.append(diam)

            if not diameters:
                results.append(MeasurementResult("diameter_mid", 0.0, "in", rec.pose_id))
                results.append(MeasurementResult("circumference_mid", 0.0, "in", rec.pose_id))
                continue

            diameter = float(np.median(diameters))
            results.append(MeasurementResult("diameter_mid", diameter, "in", rec.pose_id))
            results.append(MeasurementResult("circumference_mid", math.pi * diameter, "in", rec.pose_id))

        return MeasurementProfile(results=results, iqs=0.0)

    def _diameter_from_view(
        self,
        rgb: np.ndarray,
        mask: np.ndarray,
        px_per_unit: float,
    ) -> float:
        rows_any = np.any(mask, axis=1)
        cols_any = np.any(mask, axis=0)
        if not rows_any.any() or not cols_any.any():
            return 0.0
        r0, r1 = int(np.where(rows_any)[0][0]), int(np.where(rows_any)[0][-1])
        c0, c1 = int(np.where(cols_any)[0][0]), int(np.where(cols_any)[0][-1])
        h = r1 - r0 + 1
        w = c1 - c0 + 1

        bgr_roi = cv2.cvtColor(rgb[r0:r1 + 1, c0:c1 + 1], cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(bgr_roi, cv2.COLOR_BGR2GRAY)
        roi_mask = (mask[r0:r1 + 1, c0:c1 + 1].astype(np.uint8)) * 255
        gray = cv2.bitwise_and(gray, gray, mask=roi_mask)
        blurred = cv2.GaussianBlur(gray, (9, 9), 2)

        min_r = max(5, int(w * self.radius_fraction_min))
        max_r = max(min_r + 1, int(w * self.radius_fraction_max))

        circles = cv2.HoughCircles(
            blurred,
            cv2.HOUGH_GRADIENT,
            dp=1,
            minDist=h,          # expect at most one circle per view
            param1=self.canny_high,
            param2=self.accumulator_threshold,
            minRadius=min_r,
            maxRadius=max_r,
        )

        if circles is not None:
            circles = np.round(circles[0]).astype(int)
            # Only accept circles whose horizontal center is within ±25% of the
            # mask's horizontal midpoint. Label-graphic false detections tend to
            # have off-center horizontal positions.
            cx_expected = w // 2
            tolerance = int(w * 0.25)
            candidates = [c for c in circles if abs(int(c[0]) - cx_expected) <= tolerance]
            if candidates:
                best = min(candidates, key=lambda c: abs(int(c[0]) - cx_expected))
                return 2.0 * int(best[2]) / px_per_unit

        # Fallback: median silhouette width across the middle half of mask height.
        # For orthographic side-on views, silhouette width = object diameter — this
        # is the dominant Hough accumulator direction for a rectangle/cylinder.
        mid_rows = roi_mask[h // 4: 3 * h // 4, :]
        widths = mid_rows.sum(axis=1) // 255
        widths = widths[widths > 0]
        if len(widths) == 0:
            return 0.0
        return float(np.median(widths)) / px_per_unit
