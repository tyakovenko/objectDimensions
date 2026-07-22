# Object Dimensioning from Multi-View Smartphone Images

**Taisiia Yakovenko** · Digital Image Processing · 2026-05-05

---

## Abstract

A pipeline is presented that extracts 3D measurements (height, circumference, diameter) from four smartphone photographs of an object, using only the object's known height as a reference. The pipeline applies HSV segmentation, orthographic visual hull reconstruction, and two measurement strategies: cross-section perimeter from the 3D mesh (visual hull method) and per-view Hough circle detection. Accuracy is characterized across three input quality tiers on a single test object (n=1); the two methods are shown to have complementary strengths depending on how consistently the object was photographed. Under ideal capture conditions, height error is 0.3% and hull circumference error is +7.4%. Under inconsistent capture distances, the Hough method outperforms hull (9.7% vs. 20.8% absolute). A synthetic test isolates a geometric bias inherent to 4-view hull reconstruction: four orthographic silhouettes of a cylinder intersect to a square prism, producing a measured +27.0% circumference overestimate (theoretical $4/\pi - 1 = +27.32\%$) relative to the true circular perimeter, a bias that partially cancels with opposing errors under real-world conditions.

---

## 1  Introduction

Measuring physical objects accurately from photographs has applications in e-commerce, garment fitting, logistics, and medical imaging. The core difficulty is scale ambiguity: a camera produces a 2D projection that destroys depth information, making it impossible to recover metric size without a reference. With a single known dimension (height), all other measurements can be derived through back-projection.

Prior work on multi-view 3D reconstruction ranges from structure-from-motion approaches requiring feature correspondences across views to learning-based implicit representations. For constrained capture protocols (fixed object, 4 orthographic views), the visual hull is a geometrically principled baseline: it computes the maximal 3D shape consistent with all silhouettes. Its limitations (inability to represent concave regions, sensitivity to voxel resolution) are well-characterized and make it a useful diagnostic for understanding where more sophisticated methods add value.

The goals are: 
(1) build and validate a complete measurement pipeline on controlled inputs
(2) empirically characterize the sources and magnitude of error, with particular attention to the interaction between input quality and method choice.

---

## 2  Method

### 2.1  Pipeline Overview

![Pipeline overview](figures/pipeline.png)

The pipeline is a linear sequence with one feedback path (validation flagging low-quality input before reconstruction proceeds):

1. **Ingest**: load four labeled views (front, right, back, left) from a directory; parse ground-truth height from a command-line argument.
2. **Input Quality Scoring (IQS)**: compute per-view and cross-view metrics; emit warnings and a composite score.
3. **Segmentation**: extract binary foreground masks.
4. **Calibration**: compute a scale factor (px/in) from the known height and the median segmented pixel height across views.
5. **Reconstruction**: carve a 128³ voxel grid using all four silhouettes; extract surface mesh via marching cubes.
6. **Measurement**: extract height, circumference at three heights, and midpoint width/depth from the mesh (hull method); optionally detect circle diameter per view via Hough transform (Hough method).
7. **Output**: write `measurements.json` and `validation.json`.

### 2.2  Input Quality Scoring

The IQS composite score is the mean of six per-view metrics, weighted equally:

| Metric | Measure | Warning threshold |
|---|---|---|
| Sharpness | Laplacian variance, normalized | < 0.3 |
| Fourier sharpness | Log-ratio of high-band to low-band FFT power | (no warn; contributes to composite) |
| Frame coverage | Object bbox area / frame area, ideal range [0.15, 0.40] | < 0.3 |
| Mask solidity | Mask area / convex hull area | < 0.85 |
| Aspect ratio | Height / width ratio, ideal range [1.3, 3.5] | outside [1.3, 3.5] |
| Scale consistency | 1 − (std(pixel\_heights) / mean(pixel\_heights)) | < 0.9 |

The Fourier sharpness metric computes the 2D discrete Fourier transform of the masked object region and takes the log ratio of average power in the outer 50% of the frequency radius to the inner 10%. Sharp images have higher high-frequency content; the log ratio separates sharp from soft images more reliably than Laplacian variance for distance-induced blur.

### 2.3  Segmentation

The primary segmenter applies HSV color thresholding to isolate distinctly colored objects: a user-configured hue range is combined with morphological closing (to fill gaps) and opening (to remove small blobs), followed by largest-connected-component selection to discard background fragments. Mask solidity (mask area / convex hull area) serves as the confidence signal.

GrabCut is retained as a fallback for objects that do not have a distinctive hue. As discussed in Section 5, GrabCut fails when object and background colors are similar.

### 2.4  Calibration

An orthographic scale factor $s_v$ (pixels per inch) is computed per view from the segmented pixel height and the known true height:

$$s_v = \frac{h_{\text{px},v}}{h_{\text{true}}}$$

A `CameraModel` is emitted per view with its own scale. The visual hull pipeline currently consumes only the front view's scale (`cameras[0]`) to convert voxels to world units, a known limitation discussed in Section 5 and Section 6. The Hough pipeline uses each view's own scale independently. In both cases, single-reference calibration propagates height input error linearly to all downstream measurements: a $k$% error in the height input produces a $k$% error in every extracted dimension (Section 5.4).

### 2.5  Visual Hull Reconstruction

Each binary mask defines a prismatic (generalized cylindrical) volume in 3D: the set of all voxels that project onto the white region of that view. The visual hull is the intersection of all four such volumes. At 128³ voxels, the grid side length is 1.1× the reference height (5% padding per side); the same extent is used for all three axes, so the X/Y axes have generous slack relative to the object's diameter. Marching cubes extracts a triangle mesh from the binary voxel occupancy grid.

Circumference is measured as the perimeter of the 2D cross-section polygon at three normalized heights (0.1, 0.5, 0.9 of the object's bounding box). Height is the distance between the topmost and bottommost occupied voxel layers. Width and depth are the bounding box extents of the mid-height cross-section.

### 2.6  Hough Circle Detection

For cylindrical objects, each view provides a side profile from which the circular cross-section diameter can be estimated directly. `cv2.HoughCircles` is applied with a radius search range constrained to 35–55% of the mask pixel width and a center-y constraint to the mask center ± 20% of mask height. Empirically, unconstrained `HoughCircles` on labeled cans latched onto label graphics rather than the can outline; the 35–55% window was set after inspecting candidate detections to exclude that failure mode. When no circle is found within constraints, the method falls back to the mask's pixel width converted to inches via the scale factor.

The per-view diameter estimates are averaged across the four views to yield a single midpoint diameter; circumference is derived as $\pi d$.

---

## 3  Experimental Setup

**Object.** A standard 15oz corn can (Trader Joe's). Ground truth: height = 4.41 in, circumference\_mid = 9.13 in, diameter\_mid = 2.83 in (tape measure).

**Quality tiers.** Three capture conditions were designed to exercise the IQS and stress the pipeline:

| Tier | Protocol |
|---|---|
| Good | Consistent distance (~30cm), level angle, neutral background, front-facing label |
| Medium | Slightly inconsistent distances across the four views (~25% variation), no deliberate degradation |
| Bad | Deliberate defects: low angle + harsh light (front), too far (right), motion blur (back), high angle + too close (left) |

**Runs.** Each tier was run with both the hull and Hough measurers. Results reported below use the canonical run per tier (the run used to generate the ground-truth comparison tables in `analysis/`).

---

## 4  Results

### 4.1  Accuracy by Tier and Method

![Accuracy comparison](figures/accuracy_comparison.png)

| Tier | IQS | Hull circ. error | Hough circ. error | Gate (<10%) |
|---|---|---|---|---|
| Good   | 0.905 | **+7.4%** | +10.1% | Hull ✓ |
| Medium | 0.896 | −20.8% | **+9.7%** | Hough ✓ |
| Bad    | 0.59 | −17.5% | ~−15% | Both ✗ |

Signs are reported because they carry the geometric story: hull on good tier overshoots (square-prism bias, §5.1), while hull on medium and bad tiers undershoots (front-view scale error dominates the +27% bias and flips the sign). Height error follows the pattern: good tier 0.3%, bad tier 9.8% (dominated by the extremely inconsistent pixel heights across views, [295, 126, 324, 697] px, which corrupt the front-view-driven scale).

**Naive baseline.** A no-reconstruction baseline (multiply the front-view mask width in inches by $\pi$) gives circumference error of −8.7% on the good tier (computed: $\pi \cdot 2.65\text{ in} = 8.33\text{ in}$ vs. true 9.13 in). This is in the same ballpark as Hough (+10.1%) and slightly worse than hull (+7.4%). The hull and Hough methods are not dramatically beating this baseline on a single isolated dimension, but they produce a 3D mesh and per-view diameter agreement check respectively, outputs the naive baseline cannot supply.

The reversal between good and medium tier (where the hull outperforms Hough on consistent input but Hough outperforms hull on inconsistent input) is the central empirical finding of this work.

**Explanation.** The visual hull pipeline derives its world scale from the front view's pixel height alone (`cameras[0]`). When all four views are shot at the same distance, the front view's pixel height is representative and the hull cross-section faithfully reflects the object's true diameter (modulo the +27% square-prism bias). When the front view is shot at a different distance than the others, its pixel height is no longer representative; every dimension extracted from the hull is scaled by the front view's $s_0$, even though the silhouettes from the other views are mutually inconsistent in voxel space. The Hough method estimates diameter independently per view (each with its own scale) and averages, so distance inconsistency introduces noise rather than systematic scale error. On good-tier input where all views agree, hull wins; on medium-tier input with ~25% distance variation (pixel heights: 393, 365, 316, 323), hull loses by ~2.1×.

### 4.2  IQS Discrimination

![IQS vs. error](figures/iqs_vs_error.png)

IQS correctly discriminates the bad tier (0.59) from good (0.905) and medium (0.896), and fires four correct warnings on the bad tier (frame coverage, blur, aspect ratio, scale consistency). However, IQS fails to distinguish good from medium: their composite scores differ by less than 0.01 despite a ~2.8× difference in hull circumference error. The medium scale\_consistency score (0.910) clears the warning threshold (0.9) used by the system, so no warning fires, correctly per spec, but the threshold is clearly too loose to catch moderate distance variation that destroys the hull pipeline's accuracy.

### 4.3  Height Sensitivity

All measurements scale linearly with the height input. A controlled perturbation experiment (±10%, ±20% height) confirmed that circumference error shifts by exactly the input perturbation magnitude to within ±1% across all levels. This is a consequence of orthographic single-reference calibration: the scale factor is proportional to the input height, so every downstream measurement inherits height input error proportionally.

![Height sensitivity](figures/height_sensitivity.png)

---

## 5  Analysis

### 5.1  Geometric Bias of 4-View Hull

![Geometric bias](figures/hull_bias.png)

A synthetic validation test (see `tests/test_hull_synthetic.py`) injects rectangular masks for a known-dimension cylinder, bypassing segmentation entirely, to isolate algorithmic error from input error. Results on a 4.25 × 2.625 in cylinder:

| Measurement | Error |
|---|---|
| Height | 0.31% |
| Width / Depth | 0.18% |
| Circumference\_mid | +27.0% vs. $\pi d$ |

The source of the +27% is geometric. Four orthographic silhouettes of a cylinder are rectangles. The intersection of four rectangular extrusions oriented at 0°, 90°, 180°, 270° is a square prism, not a cylinder. The cross-section is a square with side $d$, whose perimeter is $4d$, not $\pi d$. The theoretical ratio is $4/\pi \approx 1.2732$, i.e., +27.32%; the synthetic test measures +27.0%, with the 0.3 pp gap attributable to 128³ voxelization at the boundary.

More generally, for $N$ equally-spaced views (with $N$ even, so the hull is a regular polygon circumscribed around the cylinder), the cross-section is a regular $N$-gon. Its perimeter is $N \cdot d \cdot \tan(\pi/N)$, which approaches $\pi d$ only as $N \to \infty$:

| N views | Hull perimeter / True perimeter |
|---|---|
| 4  | 127.3% |
| 8  | 105.5% |
| 16 | 101.3% |
| 32 | 100.3% |

The real-world hull circumference error on the good tier is +7.4%, far below the +27.3% geometric prediction. This is because voxelization at 128³ underestimates voxel occupancy at boundaries, and partial mask coverage shrinks each silhouette prism slightly; these effects collectively cancel approximately 20 percentage points of the geometric overshoot. This cancellation is fragile and not a reliable correction mechanism; increasing voxel resolution or correcting for the $N$-gon bias analytically would improve accuracy without relying on error cancellation.

### 5.2  IQS Boundary Failure

The good/medium IQS boundary failure is a threshold calibration problem. The system's scale\_consistency warning fires at < 0.9; medium tier scores 0.910 and good tier scores 0.928, both clearing the threshold. The measurement error difference between tiers (+7.4% vs. −20.8% hull) is dramatic, but the composite IQS score difference (0.905 vs. 0.896) is well within noise, and the scale\_consistency gap (0.018) is too narrow to be a discriminator at the current threshold setting. IQS is not yet a reliable predictor of measurement error magnitude; it reliably flags the bad tier but cannot distinguish "acceptable" from "good" near IQS ≈ 0.9. Tightening the scale\_consistency threshold to ~0.93 would have caught the medium tier on this object, but with n=1 the threshold cannot be set robustly.

### 5.3  Segmentation Failure Cases

GrabCut failed on two additional objects:
- **Shampoo bottle (white on gray background, run `output/20260423_103551_shampoo`):** GrabCut classified the background wall as foreground. Measurement not possible.
- **Fabric box (gray on gray surface, run `output/20260423_104522_box`):** GrabCut partially clipped object edges; extracted width was 61% of ground truth and depth was 25% of ground truth.

These failures demonstrate that color-statistics-based segmentation requires a contrast boundary between object and background. HSV thresholding is limited by the same constraint. Both approaches require a distinctly colored object on a neutral background, a practical constraint that rules out many real-world capture scenarios.

### 5.4  Error Budget Summary

| Error source | Mechanism | Tier affected | Approximate magnitude |
|---|---|---|---|
| Height input error | Linear propagation to all measurements | All | Proportional (1:1) |
| Cross-view distance variation | Scale factor corrupted → hull collapses | Medium, Bad | 10–15 pp on hull |
| 4-view hull geometric bias | Square prism vs. cylinder | All (hull) | +27.3% geometric; partially cancelled |
| Voxel resolution | Staircase approximation underestimates boundary occupancy | All (hull) | Partially offsets geometric bias |
| Segmentation boundary error | Mask bleeds into background or clips edges | All | Per-view, ~2–5% on good masks |
| Hough false detection | Label graphics trigger wrong circles | Good (Hough) | Mitigated by tight radius range |

The dominant error source for the hull method on medium and bad tiers is cross-view scale inconsistency. For the Hough method on good-tier input, the constraint that four side-view profiles should all agree is not enforced, making Hough more sensitive to label-induced false detections. The error sources are largely orthogonal, suggesting a combined estimator could improve robustness.

---

## 6  Discussion

The reversal result (hull better on consistent input, Hough better on inconsistent input) suggests a principled combination: use IQS scale\_consistency to select the measurement method at runtime. Below a scale\_consistency threshold, switch to Hough; above it, use hull. This was not implemented for two reasons. First, the threshold cannot be reliably calibrated from a single object: the good/medium scale\_consistency gap is only 0.018 (0.928 vs. 0.910), too narrow to set a robust boundary without data from additional objects and capture conditions. Second, the hull pipeline currently consumes only `cameras[0]`'s scale (front view), so the medium-tier failure is partly an artifact of single-view calibration rather than the visual hull algorithm itself. Fixing auto-selection without first fixing the calibration consumption would shift error between methods without resolving the root cause.

### 6.1  Future Work, Ranked by Leverage

**Tier 1: required to make any other improvement interpretable.**

1. **Multi-object dataset (n > 1).** Every quantitative claim in this report is from one corn can. IQS thresholds, the hull/Hough crossover point, and the magnitude of the cancellation effect cannot be calibrated from n=1. The minimum useful dataset is ~5 cylindrical objects across each tier with multiple capture trials per tier.

**Tier 2: capability gains.**

2. **Neural segmentation (SAM 2).** Removes the color-contrast requirement that breaks both HSV thresholding and GrabCut on shampoo and fabric box. Single highest-leverage practical upgrade. Blocked here on a hardware dependency: SAM 2 inference requires a GPU with ≥8 GB VRAM, unavailable in the evaluation environment.

3. **Increase view count.** 8 views drop the geometric bias to 5.5%; 16 views to 1.3%. Requires a capture-protocol change but no algorithm rework.

**Tier 3: only useful after Tier 1.**

4. **Analytical $N$-gon correction.** Multiply measured perimeter by $\pi / (N \cdot \tan(\pi/N))$ ($\approx 0.785$ for $N=4$). Inadvisable on the current system: the +27% geometric bias is partially cancelled by voxelization and mask-shrinkage (§5.1), so applying the correction on top would produce a ~15% underestimate on good-tier input. Becomes appropriate once voxel resolution and mask-coverage error are independently controlled.

5. **Auto-select hull vs. Hough by `scale_consistency`.** The reversal result (hull better on consistent input, Hough better on inconsistent input) suggests a runtime selector. Without the calibration fix, the selector's threshold reflects calibration brittleness rather than algorithm choice; without n>1, the threshold cannot be set robustly.

6. **IQS threshold re-calibration.** Current thresholds were set heuristically on one object. They should be fit to a labeled dataset (IQS features → measured error) once such a dataset exists.

7. **Hough-corrected hull circumference.** Substitute Hough diameter into the hull's circumference output as a hybrid measurement. Cheap to implement; only meaningful as a fallback once the broader pipeline is in shape.

---

## 7  Conclusion

A complete end-to-end pipeline for object dimensioning from four smartphone photographs was built and evaluated. On ideal input, height error is 0.3% and hull circumference error is +7.4%, passing a <10% accuracy gate. The Hough circle method is more robust to inconsistent capture distances, outperforming the visual hull ~2.1× on medium-quality input from this object. The 4-view visual hull has a deterministic +27.3% (theoretical) / +27.0% (measured) circumference bias rooted in the geometry of regular-polygon approximation of a circle, a finding confirmed by a synthetic regression test that isolates algorithmic error from measurement noise. The IQS successfully flags severely degraded input but does not discriminate moderate from ideal conditions, identifying a calibration gap that motivates future work.

### Limitations

- **n=1 object.** All quantitative results come from a single corn can across three capture tiers; "Hough beats hull 2.1×" is a finding for this object, not a population claim.
- **Single canonical run per tier.** No repeat trials; the reported numbers carry no measured variance.
- **Hand-tuned Hough constants.** The radius range (35–55%) and center-y window (±20%) are tuned to the corn can; generalization to other cylindrical objects is untested.
- **Hull uses single-view calibration.** The hull pipeline reads only `cameras[0]`'s scale, conflating "visual hull algorithm error" with "front-view calibration error"; disentangling these requires a per-view calibration fix.
- **Segmentation requires color contrast.** HSV thresholding and GrabCut both fail when object and background are similar in color (§5.3).

---

## Appendix: Reproduction

```bash
# Install
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Run hull measurer on a photo set
python run.py data/corn_can/good --height 4.41 --measurer hull

# Run Hough measurer
python run.py data/corn_can/good --height 4.41 --measurer hough

# Hough vs. hull comparison table
python analysis/hough_vs_hull.py \
  --good-hull  output/20260423_105005_good \
  --good-hough output/20260422_212608_good \
  --medium-hull  output/20260422_211224_medium \
  --medium-hough output/20260422_212948_medium \
  --bad-hull  output/bad/20260423_095526_bad \
  --bad-hough output/20260423_105808_bad \
  --object corn_can

# Synthetic regression tests (bypasses segmentation)
pytest tests/test_hull_synthetic.py -v
```
