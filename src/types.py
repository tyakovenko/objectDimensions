"""Shared dataclasses for the pipeline. Mirrors docs/decisions/20260404-pipeline-architecture.md."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import numpy as np


@dataclass
class CaptureImage:
    path: Path
    view: str
    pose_id: str
    raw: np.ndarray
    exif: dict


@dataclass
class ImageSet:
    images: list[CaptureImage]

    def unique_pose_ids(self) -> list[str]:
        return sorted({img.pose_id for img in self.images})


@dataclass
class SegmentedImage:
    source: CaptureImage
    mask: np.ndarray
    confidence: float


@dataclass
class SegmentationResult:
    segmented: list[SegmentedImage]


class Segmenter(Protocol):
    def segment(self, image_set: ImageSet) -> SegmentationResult: ...


@dataclass
class ValidationReport:
    composite_iqs: float
    quality_label: str
    per_image: dict
    cross_view: dict
    warnings: list[str] = field(default_factory=list)


@dataclass
class PoseEstimate:
    keypoints: dict = field(default_factory=dict)
    confidence: dict = field(default_factory=dict)


class PoseEstimator(Protocol):
    def estimate(self, segmentation: SegmentationResult) -> PoseEstimate: ...


@dataclass
class CameraModel:
    view: str
    pose_id: str
    projection_type: str
    pixels_per_unit: float


@dataclass
class CalibrationResult:
    cameras: list[CameraModel]
    reference_dimension: float
    reference_unit: str


@dataclass
class Reconstruction:
    pose_id: str
    mesh: object  # trimesh.Trimesh — kept as object to avoid import at module load
    voxel_resolution: int
    method: str


class Reconstructor(Protocol):
    def reconstruct(
        self,
        segmentation: SegmentationResult,
        calibration: CalibrationResult,
        pose: PoseEstimate,
        pose_id: str,
    ) -> Reconstruction: ...


@dataclass
class MeasurementResult:
    name: str
    value: float
    unit: str
    pose_id: str


@dataclass
class MeasurementProfile:
    results: list[MeasurementResult]
    iqs: float


class Measurer(Protocol):
    def measure(
        self,
        reconstructions: list[Reconstruction],
        segmentation: SegmentationResult | None = None,
        calibration: CalibrationResult | None = None,
    ) -> MeasurementProfile: ...


@dataclass
class OutputBundle:
    measurements: MeasurementProfile
    validation: ValidationReport
    output_dir: Path
