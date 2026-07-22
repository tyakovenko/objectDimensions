"""Orthographic scale calibration from known object height.

Assumes the object is upright in every view (top of mask = object top, bottom = base).
Height in pixels per view → inches per pixel via user-provided true height.
"""

from __future__ import annotations

import numpy as np

from .types import CalibrationResult, CameraModel, PoseEstimate, SegmentationResult


def _mask_pixel_height(mask: np.ndarray) -> int:
    rows = np.any(mask, axis=1)
    if not rows.any():
        return 0
    idx = np.where(rows)[0]
    return int(idx[-1] - idx[0] + 1)


class OrthographicCalibrator:
    def calibrate(
        self,
        segmentation: SegmentationResult,
        pose: PoseEstimate,
        reference_dimension: float,
        reference_unit: str = "in",
    ) -> CalibrationResult:
        cameras: list[CameraModel] = []
        for seg in segmentation.segmented:
            ph = _mask_pixel_height(seg.mask)
            if ph == 0:
                raise ValueError(f"Empty mask for view {seg.source.view} — segmentation failed")
            # Inches per pixel — inverse of conventional "pixels per unit" for visual hull math.
            scale = reference_dimension / ph
            cameras.append(
                CameraModel(
                    view=seg.source.view,
                    pose_id=seg.source.pose_id,
                    projection_type="orthographic",
                    pixels_per_unit=1.0 / scale,
                )
            )
        return CalibrationResult(
            cameras=cameras,
            reference_dimension=reference_dimension,
            reference_unit=reference_unit,
        )
