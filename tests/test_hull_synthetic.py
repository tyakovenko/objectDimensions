"""Synthetic-cylinder regression test.

Bypasses segmentation: injects rectangular masks representing a perfect
cylinder's silhouette from 4 orthographic views, runs the pipeline
(calibration → hull → cross-section measurer), and asserts on outputs.

Purpose:
  1. Regression guard — algorithmic correctness, independent of real data.
  2. Documents the 4-view visual hull's geometric limit on round objects:
     4 rectangular silhouettes carve a SQUARE prism, not a cylinder.
     Circumference via cross-section perimeter is therefore ≈ 4·d (square),
     not π·d (circle). This is a fundamental, not a bug.

If this test fails, the mechanism is in the hull/measurer, not segmentation.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np

from src.calibration import OrthographicCalibrator
from src.measurement.cross_section import CrossSectionMeasurer
from src.pose.null import NullPoseEstimator
from src.reconstruction.visual_hull import VisualHullReconstructor
from src.types import CaptureImage, ImageSet, SegmentationResult, SegmentedImage


def _cylinder_silhouette(img_h: int, img_w: int, px_h: int, px_d: int) -> np.ndarray:
    """Rectangular silhouette centered in the frame — a cylinder's projection
    under any orthographic side view."""
    m = np.zeros((img_h, img_w), dtype=bool)
    y0 = (img_h - px_h) // 2
    x0 = (img_w - px_d) // 2
    m[y0:y0 + px_h, x0:x0 + px_d] = True
    return m


def _synthetic_inputs(mask: np.ndarray) -> tuple[ImageSet, SegmentationResult]:
    h, w = mask.shape
    dummy_raw = np.zeros((h, w, 3), dtype=np.uint8)
    images: list[CaptureImage] = []
    segs: list[SegmentedImage] = []
    for view in ("front", "right", "back", "left"):
        img = CaptureImage(
            path=Path(f"/synthetic/{view}.png"),
            view=view,
            pose_id="synthetic",
            raw=dummy_raw,
            exif={},
        )
        images.append(img)
        segs.append(SegmentedImage(source=img, mask=mask.copy(), confidence=1.0))
    return ImageSet(images=images), SegmentationResult(segmented=segs)


def _run_pipeline(
    true_height_in: float, true_diameter_in: float, resolution: int = 128
) -> dict[str, float]:
    # Pick pixel dims preserving the height:diameter ratio.
    px_h = 400
    px_d = int(round(px_h * true_diameter_in / true_height_in))
    mask = _cylinder_silhouette(img_h=600, img_w=800, px_h=px_h, px_d=px_d)

    image_set, segmentation = _synthetic_inputs(mask)
    pose = NullPoseEstimator().estimate(segmentation)
    calibration = OrthographicCalibrator().calibrate(segmentation, pose, true_height_in)
    rec = VisualHullReconstructor(resolution=resolution).reconstruct(
        segmentation, calibration, pose, pose_id="synthetic"
    )
    profile = CrossSectionMeasurer().measure([rec])
    return {r.name: r.value for r in profile.results}


def test_synthetic_cylinder_height():
    """Height is preserved to voxel resolution."""
    m = _run_pipeline(true_height_in=4.25, true_diameter_in=2.625)
    rel = abs(m["height"] - 4.25) / 4.25
    assert rel < 0.02, f"height error {rel*100:.2f}% exceeds 2% voxelization tolerance"


def test_synthetic_cylinder_width_equals_diameter():
    """Midpoint width/depth = diameter (all 4 silhouettes have width = d)."""
    m = _run_pipeline(true_height_in=4.25, true_diameter_in=2.625)
    for key in ("width_mid", "depth_mid"):
        rel = abs(m[key] - 2.625) / 2.625
        assert rel < 0.03, f"{key} error {rel*100:.2f}% exceeds 3% tolerance"


def test_synthetic_cylinder_circumference_is_square_not_circle():
    """Cross-section perimeter of a 4-view hull on a cylinder ≈ 4·d (square prism),
    NOT π·d (circle). This is the 4-view hull's inherent geometric limit."""
    true_d = 2.625
    m = _run_pipeline(true_height_in=4.25, true_diameter_in=true_d)
    measured = m["circumference_mid"]

    square_perim = 4.0 * true_d       # 10.500 in — what the hull actually produces
    circle_perim = math.pi * true_d   # 8.247 in — what a true cylinder would measure

    rel_to_square = abs(measured - square_perim) / square_perim
    rel_to_circle = abs(measured - circle_perim) / circle_perim

    assert rel_to_square < 0.05, (
        f"Measured circumference {measured:.3f} is not within 5% of the expected "
        f"square-prism perimeter {square_perim:.3f} — hull geometry is broken."
    )
    assert rel_to_circle > 0.20, (
        f"Measured circumference {measured:.3f} is within 20% of a true circle "
        f"({circle_perim:.3f}) — that would contradict the 4-view hull limit; "
        f"check if the test setup or mesh output changed."
    )
