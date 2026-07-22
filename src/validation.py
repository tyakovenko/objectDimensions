"""Minimal IQS for MVP: three metrics, no auto-recovery.

Extends to the full 8-metric IQS (see phase-1-plan.md) post-MVP.
"""

from __future__ import annotations

import cv2
import numpy as np

from .segmentation.base import solidity as _solidity
from .types import ImageSet, SegmentationResult, ValidationReport

# ----- IQS calibration constants -----
# Tuned empirically on Pixel 8 captures (see docs/followups-code-review.md §E
# for the note on replacing these with fitted weights).

# Laplacian sharpness: var<50 → 0, var>500 → 1, linear between.
SHARPNESS_VAR_FLOOR = 50.0
SHARPNESS_VAR_RANGE = 450.0

# Fourier sharpness: log10(high/low) −4.8 → 0, −4.0 → 1. Pixel 8 calibration:
# sharp (good tier) ≈ −4.0 to −3.9; blurry (bad tier) ≈ −4.8 to −4.4.
FOURIER_LOG_RATIO_FLOOR = -4.8
FOURIER_LOG_RATIO_RANGE = 0.8

# Frame coverage: ideal band is 15–40% of image area.
FRAME_COVERAGE_IDEAL_LO = 0.15
FRAME_COVERAGE_IDEAL_HI = 0.40

# Solidity: mask-area / convex-hull-area. <0.80 → 0, >0.95 → 1.
SOLIDITY_SCORE_FLOOR = 0.80
SOLIDITY_SCORE_RANGE = 0.15

# Aspect ratio (h/w): expected cylinder silhouette ratio ~1.3–3.5.
ASPECT_IDEAL_LO = 1.3
ASPECT_IDEAL_HI = 3.5
ASPECT_LOW_FLOOR = 1.0    # below 1.0 → 0
ASPECT_HIGH_CEILING = 4.5  # above 4.5 → 0

# Per-view warning thresholds (fire a warning when below).
WARN_SHARPNESS = 0.3
WARN_COVERAGE = 0.3
WARN_SOLIDITY = 0.85

# Cross-view scale consistency warning.
WARN_SCALE_CONSISTENCY = 0.9


def _sharpness_score(gray: np.ndarray, mask: np.ndarray) -> float:
    lap = cv2.Laplacian(gray, cv2.CV_64F)
    if mask.sum() == 0:
        return 0.0
    var = float(lap[mask].var())
    return float(np.clip((var - SHARPNESS_VAR_FLOOR) / SHARPNESS_VAR_RANGE, 0.0, 1.0))


def _fourier_sharpness_score(gray: np.ndarray, mask: np.ndarray) -> float:
    """High-band / low-band power ratio via 2D FFT over the masked object region.
    Natural images follow 1/f² power law so raw ratios are tiny; log-ratio linearizes.
    Kept separate from composite IQS so it can be compared against Laplacian variance."""
    if mask.sum() == 0:
        return 0.0
    rows = np.any(mask, axis=1)
    cols = np.any(mask, axis=0)
    r_idx = np.where(rows)[0]
    c_idx = np.where(cols)[0]
    r0, r1 = int(r_idx[0]), int(r_idx[-1])
    c0, c1 = int(c_idx[0]), int(c_idx[-1])
    region = gray[r0:r1 + 1, c0:c1 + 1].astype(np.float64)
    region = region * mask[r0:r1 + 1, c0:c1 + 1].astype(np.float64)

    fshift = np.fft.fftshift(np.fft.fft2(region))
    power = np.abs(fshift) ** 2

    h, w = power.shape
    cy, cx = h / 2.0, w / 2.0
    y, x = np.ogrid[:h, :w]
    radius = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
    max_r = min(cx, cy)

    high_mean = float(power[radius > 0.5 * max_r].mean())
    low_mean = float(power[radius < 0.1 * max_r].mean())
    if low_mean == 0:
        return 0.0

    log_ratio = np.log10(high_mean / low_mean)
    return float(np.clip(
        (log_ratio - FOURIER_LOG_RATIO_FLOOR) / FOURIER_LOG_RATIO_RANGE, 0.0, 1.0
    ))


def _frame_coverage_score(mask: np.ndarray) -> float:
    area = float(mask.sum())
    total = float(mask.size)
    frac = area / total if total else 0.0
    if FRAME_COVERAGE_IDEAL_LO <= frac <= FRAME_COVERAGE_IDEAL_HI:
        return 1.0
    if frac < FRAME_COVERAGE_IDEAL_LO:
        return float(np.clip(frac / FRAME_COVERAGE_IDEAL_LO, 0.0, 1.0))
    return float(np.clip((1.0 - frac) / (1.0 - FRAME_COVERAGE_IDEAL_HI), 0.0, 1.0))


def _mask_pixel_height(mask: np.ndarray) -> int:
    rows = np.any(mask, axis=1)
    if not rows.any():
        return 0
    idx = np.where(rows)[0]
    return int(idx[-1] - idx[0] + 1)


def _mask_bbox(mask: np.ndarray) -> tuple[int, int, int, int] | None:
    rows = np.any(mask, axis=1)
    cols = np.any(mask, axis=0)
    if not rows.any() or not cols.any():
        return None
    r = np.where(rows)[0]
    c = np.where(cols)[0]
    return int(r[0]), int(r[-1]), int(c[0]), int(c[-1])


def _solidity_score(solidity: float) -> float:
    return float(np.clip(
        (solidity - SOLIDITY_SCORE_FLOOR) / SOLIDITY_SCORE_RANGE, 0.0, 1.0
    ))


def _aspect_ratio(mask: np.ndarray) -> float:
    bbox = _mask_bbox(mask)
    if bbox is None:
        return 0.0
    r0, r1, c0, c1 = bbox
    w = max(c1 - c0 + 1, 1)
    h = r1 - r0 + 1
    return float(h / w)


def _aspect_ratio_score(ratio: float) -> float:
    if ASPECT_IDEAL_LO <= ratio <= ASPECT_IDEAL_HI:
        return 1.0
    if ratio < ASPECT_IDEAL_LO:
        return float(np.clip(
            (ratio - ASPECT_LOW_FLOOR) / (ASPECT_IDEAL_LO - ASPECT_LOW_FLOOR),
            0.0, 1.0,
        ))
    return float(np.clip(
        (ASPECT_HIGH_CEILING - ratio) / (ASPECT_HIGH_CEILING - ASPECT_IDEAL_HI),
        0.0, 1.0,
    ))


def _scale_consistency_score(heights: list[int]) -> float:
    arr = np.array(heights, dtype=float)
    if arr.mean() == 0:
        return 0.0
    cv = arr.std() / arr.mean()
    return float(np.clip(1.0 - cv, 0.0, 1.0))


class InputValidator:
    QUALITY_GOOD = 0.8
    QUALITY_WARN = 0.5

    def validate(self, images: ImageSet, segmentation: SegmentationResult) -> ValidationReport:
        per_image: dict = {}
        heights: list[int] = []
        warnings: list[str] = []

        for seg in segmentation.segmented:
            gray = cv2.cvtColor(seg.source.raw, cv2.COLOR_RGB2GRAY)
            sharp = _sharpness_score(gray, seg.mask)
            fourier_sharp = _fourier_sharpness_score(gray, seg.mask)
            cov = _frame_coverage_score(seg.mask)
            solidity = _solidity(seg.mask)
            sol_score = _solidity_score(solidity)
            aspect = _aspect_ratio(seg.mask)
            asp_score = _aspect_ratio_score(aspect)
            ph = _mask_pixel_height(seg.mask)
            heights.append(ph)
            per_image[seg.source.view] = {
                "sharpness": sharp,
                "fourier_sharpness": fourier_sharp,
                "frame_coverage": cov,
                "solidity": solidity,
                "solidity_score": sol_score,
                "aspect_ratio": aspect,
                "aspect_ratio_score": asp_score,
                "pixel_height": ph,
            }
            if sharp < WARN_SHARPNESS:
                warnings.append(f"{seg.source.view}: blurry (sharpness={sharp:.2f})")
            if cov < WARN_COVERAGE:
                warnings.append(f"{seg.source.view}: frame coverage low ({cov:.2f})")
            if solidity < WARN_SOLIDITY:
                warnings.append(
                    f"{seg.source.view}: mask not solid (solidity={solidity:.2f}) "
                    "— segmentation may be grabbing background."
                )
            if not (ASPECT_IDEAL_LO <= aspect <= ASPECT_IDEAL_HI):
                warnings.append(
                    f"{seg.source.view}: unusual aspect ratio (h/w={aspect:.2f}) "
                    "— mask shape inconsistent with cylindrical object."
                )

        scale = _scale_consistency_score(heights)
        cross_view = {"scale_consistency": scale, "heights_px": heights}
        if scale < WARN_SCALE_CONSISTENCY:
            warnings.append(
                f"Scale inconsistent across views (score={scale:.2f}). "
                "Distance likely varied — measurements will be biased."
            )

        per_image_mean = float(
            np.mean([
                np.mean([
                    m["sharpness"],
                    m["frame_coverage"],
                    m["solidity_score"],
                    m["aspect_ratio_score"],
                ])
                for m in per_image.values()
            ])
        )
        composite = float(np.mean([per_image_mean, scale]))

        if composite >= self.QUALITY_GOOD:
            label = "good"
        elif composite >= self.QUALITY_WARN:
            label = "warn"
        else:
            label = "bad"

        return ValidationReport(
            composite_iqs=composite,
            quality_label=label,
            per_image=per_image,
            cross_view=cross_view,
            warnings=warnings,
        )
