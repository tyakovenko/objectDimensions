# Object Dimensioning from Phone Photos

Recover a rigid object's real-world dimensions (height, circumference, diameter) from four phone photos, using a single known measurement as the scale anchor. No reference marker in the shot, no depth sensor.

The harder problem here isn't producing a number, it's knowing when that number can't be trusted. Every run is scored for input quality, and the pipeline is built to fail loudly on captures it can't measure reliably instead of returning a confident wrong answer.

## How it works

Four labeled views (front, right, back, left) go in with one known dimension, the object's true height. From there:

1. **Segment** the object (HSV color thresholding, GrabCut fallback).
2. **Score input quality (IQS)** from per-view sharpness, mask solidity, aspect ratio, and cross-view scale consistency. Each metric raises a warning when it leaves its safe range.
3. **Calibrate** scale from the known height, so nothing extra has to be in frame.
4. **Reconstruct** a visual hull and measure circumference from cross-section slices, and separately estimate diameter per view with Hough circle detection.

## How it performs

Measured on a corn can against tape-measure ground truth, across three capture-quality tiers:

| Capture quality | Height error | Circumference error (best method) |
|---|---|---|
| Good (consistent distances) | 0.3% | 7.4% (visual hull) |
| Medium (~25% distance variation) | low single digits | 9.7% (Hough) |
| Bad (blur, bad angles, extreme distance) | 9.8% | 17.5%, flagged by IQS as untrustworthy |

Two results worth pulling out:

**Which method wins depends on how the object was shot.** On consistent input the visual hull is more accurate; when shooting distance varies across views, the hull's single-reference scale breaks down and per-view Hough detection wins by roughly 2x. Both methods are exposed, so the failure mode is visible rather than hidden inside one number.

**The quality score catches bad input, and I know where it doesn't.** IQS cleanly separates the bad tier (0.59 vs ~0.90 for the others) and fired all four correct warnings on it. It does not yet separate "good" from "medium" near the 0.9 boundary, even though their measurement error differs by ~3x. That's a threshold-calibration limit I can name and would close with more test objects, not a silent failure.

I also pinned down a geometric bias analytically: four orthographic silhouettes of a cylinder intersect to a square prism, a +27.3% circumference overshoot (4/π), confirmed to +27.0% by a synthetic test that bypasses segmentation entirely. More views shrink it (8 views: +5.5%). And because scale comes from one reference, a k% error in the input height propagates to a k% error in every measurement, verified with a perturbation sweep.

## Honest limits

Single test object (n=1), rigid and roughly convex, assumed upright. The IQS good/medium threshold and the hull's reliance on a single view's scale are documented weak points, not surprises. This is a characterized baseline, not a shipped product.

## Stack

Python, OpenCV, trimesh, NumPy, scikit-image. HSV/GrabCut segmentation, orthographic visual hull, Hough circle detection.

## Run

```bash
uv sync
uv run python run.py <image_dir> --height <true_height_in> --measurer hull   # or: hough
uv run pytest
```
