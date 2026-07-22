# MVP Technical Implementation Plan
**Scope:** School assignment deliverable.
**Date:** 2026-04-21
**Branch:** `phase-1/object-prototype`
**Architecture:** Follows `docs/decisions/20260404-pipeline-architecture.md` (unchanged).
**Relationship to other docs:** `phase-1-plan.md` and `execution-plan.md` describe the full product vision. This doc strips that to the minimum viable school deliverable — what ships vs. what's deferred.

---

## Success Definition

A working end-to-end pipeline that:

1. Takes 4 photos of a cylindrical object + its true height as input.
2. Produces a 3D mesh and a measurements JSON (height, diameter, circumference at top/mid/bottom).
3. Compares extracted measurements to tape/caliper ground truth.
4. Passes a quality gate: **median relative error < 10% on a "good" photo set of a soup can**.

If #4 holds, the pipeline is proven. Error analysis + report become the intellectual contribution.

**Not a success criterion:** ±0.25in or ±0.5in production accuracy. The school goal is to demonstrate the pipeline works and understand where error comes from — not to ship a product.

---

## What Ships (MVP Core)

| Component | MVP implementation | Deferred (extension) |
|---|---|---|
| Ingest | Load 4 JPG/PNG from a directory, parse filename → view label | HEIC support, EXIF auto-orient, multi-pose |
| Segmentation | SAM 2 (local GPU) OR GrabCut fallback (CPU) — decide Day 3 after hardware check | Cloud API path, prompt-tuning, human-body prompts |
| Validation | 3 metrics: sharpness, frame coverage, scale consistency. Flag pass/warn — no auto-recovery | Full IQS (8 metrics), weight fitting, Tier 2 user-interactive recovery |
| Pose | `NullPoseEstimator` passthrough | MediaPipe (Phase 2) |
| Calibrate | Orthographic, single scale factor from height, per view | Per-view pinhole, intrinsics from EXIF |
| Reconstruct | Visual hull at 128³ voxels, marching cubes → trimesh | 256³ resolution study, feature-matched camera poses |
| Measure | Height (bbox) + circumference at 3 heights + width/depth at mid | 10-slice profile, least-squares circle fit |
| Report | JSON measurements + 3 figures (mask overlay, mesh render, cross-section) | HTML dashboard, side-by-side comparison gallery |

**Total MVP surface: ~600–800 lines of Python.** The architecture doc allows each row to be swapped later without rewriting the pipeline.

---

## Data Scope for MVP

**Minimum:** 1 object × 1 quality tier × 4 views = **4 photos.**
**Recommended:** 1 object × 3 quality tiers × 4 views = **12 photos.** Needed to show IQS validation works (good scores high, bad scores low).
**Stretch:** 3 objects × 3 tiers × 4 views = 36 photos (the full `phase-1-plan.md` spec).

Start with the minimum. Capture extra only if Week 1 finishes ahead of schedule.

---

## Compressed Timeline

Assume **10 working days** (2 school weeks). Adjust once you give me the real deadline.

### Week 1: Pipeline End-to-End (5 days)
| Day | Task | Deliverable |
|---|---|---|
| 1 | Project scaffold, venv, data directory, collect `soup_can/good/` photos + ground truth | Photos on disk, `ground-truth.json` populated |
| 2 | Ingest module + SAM 2 or GrabCut segmentation working on 4 photos | Masks saved to `output/` |
| 3 | Calibrate (orthographic scale) + visual hull at 128³ | First mesh produced |
| 4 | Measurement extraction + CLI entry point `run.py` | JSON measurements produced for soup_can/good |
| 5 | 3 basic IQS metrics + pass/warn labels | Validation report in output bundle |

**End of Week 1 gate:** `python run.py data/soup_can/good --height 4.25` produces measurements. Commit, tag, write report intro.

### Week 2: Accuracy Analysis + Report (5 days)
| Day | Task | Deliverable |
|---|---|---|
| 6 | Capture medium + bad tier if time. Run pipeline on all tiers | Measurement JSON per tier |
| 7 | Accuracy analysis vs. ground truth — error per measurement, per tier | Tables + plots |
| 8 | Error budget: segmentation, voxelization, scale — trace error to source | Error-source analysis |
| 9 | Visualization polish (mask overlay, mesh render, cross-section) + report draft | Report Sections 1–5 |
| 10 | Report Sections 6–8 + discussion + cleanup + `pytest` passes | Submittable report + clean repo |

---

## Extension Order (if time permits)

When you finish each of these, the work slots cleanly into the existing architecture. Pick off in order — each is independent.

1. **2nd object (box).** Rectangular cross-section tests that the measurement code isn't accidentally cylinder-specific. ~1 day.
2. **3rd object (bottle with taper).** Varying cross-section tests height-profile measurement. ~1 day.
3. **Height sensitivity experiment.** 7 runs at ±5/10/20% on one object. Produces the "how wrong does height input make everything" plot — excellent report material. ~0.5 day.
4. **Full IQS (remaining 5 metrics + cross-view).** ~1 day.
5. **Voxel resolution sweep.** 64³ / 128³ / 256³ on one object. Shows voxelization bias convergence. ~0.5 day.

**Order reflects value per effort for the report.** #3 and #5 produce the most striking plots.

---

## Component Specs (What I Actually Need to Build)

### `src/ingest.py`
```python
def ingest(directory: Path) -> ImageSet:
    # Load all .jpg/.png, parse front/right/back/left from filename
    # Return ImageSet with CaptureImage per view
```
Filename convention: `front.jpg`, `right.jpg`, `back.jpg`, `left.jpg`. Reject anything else with a clear error.

### `src/segmentation/sam2.py` and `src/segmentation/grabcut.py`
Both conform to `Segmenter` protocol (from architecture doc). SAM 2 uses automatic mask generation with largest-mask-by-area heuristic (the object is the biggest thing in frame). GrabCut uses a bounding box at 10% inset from edges as the foreground hint.

**Day 3 decision gate:** Run SAM 2 on one photo. If it returns in <30s and produces a clean mask, use SAM 2. Else use GrabCut. Document the choice in project-log. No fighting tooling — this is a school project, not a hardware benchmark.

### `src/validation.py` (MVP minimal)
Three metrics, all on the mask region:
- `sharpness` = Laplacian variance of masked pixels. Score = clamp((var - 50) / 450, 0, 1).
- `frame_coverage` = mask bbox area / image area. Score = 1.0 if in [0.15, 0.40], drop linearly outside.
- `scale_consistency` (cross-view) = 1 - std(pixel_heights) / mean(pixel_heights). Score already in [0,1] for reasonable inputs.

Composite: simple mean. Label: good (>0.8) / warn (>0.5) / bad (<0.5). No auto-correction. No user prompts. Just print warnings and continue.

### `src/calibration.py`
```python
def calibrate(masks: list[SegmentedImage], height_inches: float) -> CalibrationResult:
    # For each mask: height_px = bbox height. Scale = height_inches / height_px.
    # If scale_consistency < 0.95, average but warn.
    # Return per-view CameraModel with orthographic projection + pixels_per_unit.
```

### `src/reconstruction/visual_hull.py`
```python
def reconstruct(masks, calibration) -> Reconstruction:
    # 1. Define voxel grid 128x128x128 centered at origin, extent = 1.2x object height.
    # 2. For each view: compute 2D projection of voxel centers.
    # 3. Look up mask value at projected pixel. Mark voxel "occupied" only if inside ALL 4 masks.
    # 4. Marching cubes (trimesh.voxel or skimage.measure.marching_cubes) → mesh.
    # 5. Scale mesh vertices by calibration.scale_factor.
```

Assumed camera positions for the 4 views: `front` looks along +Y, `right` along +X, `back` along -Y, `left` along -X. Object centered at origin, base at Z=0. This is an assumption; document it as a known simplification.

### `src/measurement/cross_section.py`
- `bbox_extent(mesh, axis="z")` → height
- `cross_section_circumference(mesh, height_fraction)`:
  - Slice mesh at `z = z_min + f * (z_max - z_min)` using `trimesh.intersections.mesh_plane`.
  - Largest closed contour. Sum edge lengths → perimeter.
- `cross_section_bbox(mesh, height_fraction, axis)`: same slice, bbox extent along axis.

No circle fitting for MVP (keep it general — works for box too).

### `run.py`
```python
# CLI: python run.py <image_dir> --height <inches> [--object-type cylinder|box]
# Output: ./output/<timestamp>_<dirname>/
#   masks/, mesh.ply, measurements.json, validation.json, figures/
```

---

## What's Explicitly Out of Scope for MVP

- HEIC image format (convert manually if your phone shoots HEIC)
- Multi-pose captures (Phase 2 thing)
- Pose estimation (null passthrough)
- Perspective / pinhole camera model
- Feature-matched camera pose (assumed-position is fine at this scope)
- Circle fitting for cylinders (bbox is good enough)
- Real-time capture guidance
- Mobile/web UI — this is a CLI-only school project
- Three-tier recovery beyond Tier 3 text warnings
- Cross-view IQS metrics beyond `scale_consistency`
- Tests beyond one smoke test per module
- Docker / packaging — just a venv and a `pyproject.toml`

---

## Risk Register (MVP-Scoped)

| Risk | Likelihood | Impact on MVP | Mitigation |
|---|---|---|---|
| SAM 2 won't run locally | Medium | Blocks Day 2 | GrabCut fallback ready — same day |
| Visual hull too blocky at 128³ | Low | Circumference error ~10% | Document as known voxelization bias in report |
| Orthographic assumption fails on phone close-ups | Medium | Systematic size bias | Capture from 3ft+, caught by ground-truth error analysis |
| Base/table bleed in mask | High | Height overestimated | Morphological erosion at bottom 2% of mask; document |
| Object tilt undetected | Low (for a can) | Cross-sections at wrong angle | Note limitation in report; principal-axis alignment is a Phase 2 thing |
| Week 1 overruns | Medium | Compresses analysis | Drop medium+bad tiers; stick to single tier for the core result |

---

## Report Structure (MVP — keep tight)

Target: 10–15 pages + appendix. Revise once you tell me the expected length.

1. Introduction (1 page) — problem, approach, scope
2. Background (2 pages) — projection, segmentation, visual hull in 1 paragraph each
3. Method (3–4 pages) — pipeline walkthrough with one figure per step
4. Results (3 pages) — measurement tables, error budget plot, mask/mesh figures
5. Discussion (1–2 pages) — error sources, visual hull limits, why Phase 2 needs SMPL
6. Future work (0.5 page) — human body, depth fusion, capture guidance
7. References (0.5 page)
8. Appendix — data collection guide, full measurement tables

Drop appendix sections if the rubric caps length.

---

## Commit Cadence

One commit at the end of each day with a `Why:` line. Tag after Week 1 gate passes (`v0.1-pipeline-smoke`) and at submission (`v1.0-submission`). Work stays on `phase-1/object-prototype`; merge to `main` at submission with a PR for final audit.
