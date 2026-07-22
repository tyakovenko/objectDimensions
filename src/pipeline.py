"""Pipeline runner — composes the 8 steps from the architecture doc."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from .calibration import OrthographicCalibrator
from .ingest import ingest
from .measurement.cross_section import CrossSectionMeasurer
from .measurement.hough_circle import HoughCircleMeasurer
from .pose.null import NullPoseEstimator
from .reconstruction.visual_hull import VisualHullReconstructor
from .segmentation.grabcut import GrabCutSegmenter
from .segmentation.hsv import HSVSegmenter
from .types import OutputBundle
from .validation import InputValidator


def _build_segmenter(name: str):
    if name == "hsv":
        return HSVSegmenter()
    if name == "grabcut":
        return GrabCutSegmenter()
    raise ValueError(f"Unknown segmenter: {name!r}. Use 'hsv' or 'grabcut'.")


def _build_measurer(name: str):
    if name == "hull":
        return CrossSectionMeasurer()
    if name == "hough":
        return HoughCircleMeasurer()
    raise ValueError(f"Unknown measurer: {name!r}. Use 'hull' or 'hough'.")


def run_pipeline(
    image_dir: Path,
    reference_dimension: float,
    output_root: Path = Path("output"),
    voxel_resolution: int = 128,
    segmenter_name: str = "hsv",
    measurer_name: str = "hull",
) -> OutputBundle:
    image_dir = Path(image_dir)
    run_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{image_dir.name}"
    output_dir = Path(output_root) / run_id
    output_dir.mkdir(parents=True, exist_ok=True)

    images = ingest(image_dir)
    segmenter = _build_segmenter(segmenter_name)
    validator = InputValidator()
    pose_estimator = NullPoseEstimator()
    calibrator = OrthographicCalibrator()
    reconstructor = VisualHullReconstructor(resolution=voxel_resolution)
    measurer = _build_measurer(measurer_name)

    segmentation = segmenter.segment(images)
    validation = validator.validate(images, segmentation)
    pose = pose_estimator.estimate(segmentation)
    calibration = calibrator.calibrate(segmentation, pose, reference_dimension)

    reconstructions = [
        reconstructor.reconstruct(segmentation, calibration, pose, pose_id)
        for pose_id in images.unique_pose_ids()
    ]
    profile = measurer.measure(reconstructions, segmentation=segmentation, calibration=calibration)
    profile.iqs = validation.composite_iqs

    # Persist outputs
    _save_masks(segmentation, output_dir / "masks")
    for rec in reconstructions:
        rec.mesh.export(output_dir / f"mesh_{rec.pose_id}.ply")
    (output_dir / "measurements.json").write_text(
        json.dumps([asdict(r) for r in profile.results], indent=2)
    )
    (output_dir / "validation.json").write_text(
        json.dumps(
            {
                "composite_iqs": validation.composite_iqs,
                "quality_label": validation.quality_label,
                "per_image": validation.per_image,
                "cross_view": validation.cross_view,
                "warnings": validation.warnings,
            },
            indent=2,
        )
    )
    return OutputBundle(measurements=profile, validation=validation, output_dir=output_dir)


def _save_masks(segmentation, dir: Path):
    import cv2

    dir.mkdir(parents=True, exist_ok=True)
    for seg in segmentation.segmented:
        out = (seg.mask.astype("uint8") * 255)
        cv2.imwrite(str(dir / f"{seg.source.view}.png"), out)
