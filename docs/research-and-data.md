# Research & Data Collection Plan
**Scope:** Specific empirical research + data capture the MVP depends on.
**Date:** 2026-04-21

This doc is deliberately narrow. `open-questions.md` covers conceptual knowledge (what a voxel is, how projection works). This doc covers **things that must be verified or collected before or during code-writing**.

---

## Part 1: Pre-Code Technical Research

These are API/algorithmic facts the implementation depends on. Each has a concrete question and a way to resolve it. **Assigned:** Claude (me), unless flagged `TAYA`.

### R1. SAM 2 setup path on available hardware
**Question:** Can SAM 2 run on Taya's local machine fast enough (<30s per image), or do we fall back?
**How to resolve:**
1. Taya provides GPU details (see `docs/blockers.md`).
2. I install `segment-anything-2` in a throwaway venv, run on one photo, time it.
3. If it fails: GrabCut (OpenCV, CPU, zero deps) becomes the MVP segmenter.
**Owner:** Me, but blocked on Taya's GPU info.
**Decision deadline:** Day 3 of Week 1.

### R2. Camera intrinsics from phone EXIF
**Question:** Does Taya's phone embed focal length and sensor size in EXIF reliably? If yes, we can upgrade to pinhole projection later for free.
**How to resolve:** Read EXIF off the first captured photo. Look for `FocalLength`, `FocalLengthIn35mmFilm`, `LensModel`. Document what's present.
**Owner:** Me, after photos exist.
**Impact:** None for MVP (orthographic is fine). Determines how cheap the perspective upgrade is later.

### R3. trimesh mesh-plane slicing API
**Question:** What does `trimesh.intersections.mesh_plane(mesh, plane_origin, plane_normal)` return, and how do we get a clean 2D polygon out of it for perimeter computation?
**How to resolve:** Read trimesh docs + write a 10-line test on a unit cube. Document the output type (likely a `Path3D` or a list of line segments).
**Owner:** Me, during Day 3 of Week 1.

### R4. Marching cubes entry point
**Question:** Use `trimesh.voxel.ops.matrix_to_marching_cubes` or `skimage.measure.marching_cubes` + build trimesh from verts/faces?
**How to resolve:** Prototype both on a 32³ sphere voxel grid. Pick whichever returns a watertight mesh with less boilerplate.
**Owner:** Me, during Day 3.

### R5. Voxelization circumference bias correction
**Question:** For a circle of true radius `r` sampled into a voxel grid at resolution `n`, what is the expected ratio of staircase-perimeter to true-perimeter? Is there a closed-form or do we have to fit it empirically?
**How to resolve:**
1. Search "voxel perimeter bias circle staircase distance" + references in the digital geometry literature.
2. If no clean result: generate voxelized circles at n=32,64,128,256,512, measure perimeter, fit the curve. ~30 min of code.
**Owner:** Me, Week 2.
**Output:** A correction factor (or formula) applied to raw circumference measurements, documented in the report.

### R6. SAM 2 vs. GrabCut base-of-object behavior
**Question:** Empirically, how much of the table/surface beneath the object does each segmenter grab? This drives the height-error estimate.
**How to resolve:** Run both on the same photo. Overlay masks. Measure pixel-height difference. Document in report as a segmentation error source.
**Owner:** Me, Week 2 (part of error budget analysis).

---

## Part 2: Empirical Research That Informs Report Quality

These are "nice to have in the report" but not MVP-blocking.

### R7. SAM 2 interactive demo impression
**Question:** Does SAM 2 handle phone-captured photos with typical backgrounds robustly?
**How to resolve:** Taya uploads 2–3 of our captured photos to Meta's SAM demo (https://segment-anything.com — if still live) and eyeballs the mask quality. Informs whether local SAM is worth the setup pain.
**Owner:** TAYA. ~15 min. Do this *before* we commit to local SAM install.

### R8. Competitor accuracy baseline
**Question:** How well does 3DLOOK / Bodygram do on a known-dimension rigid object (not a body)? Establishes a "commercial baseline" for the report intro.
**How to resolve:** Skip for MVP. Relevant for Phase 2+. Noted here so we don't lose the thought.
**Owner:** Deferred.

---

## Part 3: Data Collection Protocol

### MVP Minimum (Week 1, Day 1)
1 object × 1 quality tier × 4 views = **4 photos**. This is the smallest set that proves the pipeline.

**Object:** Soup can or cardboard tube. Uniform cylinder, matte surface, non-reflective, opaque. Diameter 2.5–4in, height 4–6in.

**Why this object specifically:**
- Uniform cylinder = same diameter at every height → easy ground truth, easy failure detection.
- Matte surface = clean segmentation.
- Non-reflective/opaque = no weird AI segmentation edge cases.

**Avoid:**
- Labels with gloss or plastic wrap (reflections break segmentation).
- Very small objects (<2in — hard to fill frame with margin).
- Anything transparent, metallic, or mirror-finished.

### Equipment Checklist
- [ ] 1 cylindrical object fitting the criteria above
- [ ] Ruler or tape measure (±1/16 inch). Calipers better (±0.01 inch) but not required.
- [ ] Smartphone. One phone for the entire project — don't mix devices.
- [ ] Flat surface with a plain contrasting background (dark object on light surface, or vice versa).
- [ ] Good lighting — near a window on a bright day is ideal, no direct sun, no flash.
- [ ] Optional but useful: tripod or phone prop (stack of books). Hand-holding is acceptable but "good tier" should be propped.

### Photo Capture Protocol
1. Object on the flat surface, centered in an open space with margin all around.
2. Phone ~3 feet from the object. Lens at the object's midpoint height (not looking down, not looking up).
3. Object fills 30–50% of frame height with clear margin above/below.
4. Phone in portrait orientation. No zoom. Tap to focus on the object. Hold steady, exhale, tap shutter.
5. **Rotate around the object** (keep object stationary) to capture 0° / 90° / 180° / 270°. Don't rotate the object.
6. Save to `data/soup_can/good/` with exact filenames: `front.jpg`, `right.jpg`, `back.jpg`, `left.jpg`.

### Ground Truth Measurement Protocol
Measure with ruler/calipers. Record in `data/ground-truth.json`:
```json
{
  "soup_can": {
    "height_in": 4.25,
    "diameter_top_in": 2.625,
    "diameter_mid_in": 2.625,
    "diameter_bottom_in": 2.625,
    "circumference_mid_in": 8.25,
    "notes": "Campbell's tomato soup, paper label matte"
  }
}
```

Measure twice, take the average. If the two measurements disagree by more than 0.1in, measure a third time — probably held the tape wrong.

### Quality Tiers (If Time Permits)

Only capture these *after* the pipeline works end-to-end on `good`. Point is to validate that IQS catches quality issues.

**Medium tier** (realistic careful user):
- Handheld, no prop.
- Distance varies 2.5–3.5ft across views.
- Phone height varies slightly across views.
- Store in `data/soup_can/medium/`.

**Bad tier** (deliberately sloppy):
- One shot intentionally blurry (move phone while capturing).
- Inconsistent distances (2ft on one view, 4ft on another).
- Inconsistent phone height (low angle one view, high angle another).
- Mixed lighting (one shot near window, one with lamp, one in shade).
- Store in `data/soup_can/bad/`.

### File Structure
```
data/
├── ground-truth.json
└── soup_can/
    ├── good/
    │   ├── front.jpg
    │   ├── right.jpg
    │   ├── back.jpg
    │   └── left.jpg
    ├── medium/    (optional — extension)
    └── bad/       (optional — extension)
```

**All of `data/` is gitignored.** Ground truth is re-derivable from photos + a tape measure; the photos aren't source code.

---

## Part 4: Sanity Checks Before Running the Pipeline

Before `python run.py ...` on any photo set:

1. Open each of the 4 photos. Confirm: object visible in full, not cropped, plain background, not blurry, consistent lighting.
2. Verify filenames are exactly `front/right/back/left.jpg` (case-sensitive on Linux).
3. Verify `ground-truth.json` has `height_in` for the object.
4. Delete any `.DS_Store` or Windows Thumbs.db that snuck in.

These take 2 minutes and prevent half the "why is the pipeline broken" sessions.

---

## Part 5: What Gets Committed to Git

- Committed: `ground-truth.json`, figures explicitly exported for the report, generated measurement JSONs once validated.
- **Not committed:** raw photos in `data/`, intermediate masks in `output/`, voxel grids, `.ply` meshes.
- Rationale: photos are heavy, re-derivable, and can contain environmental info we haven't vetted for privacy. `.gitignore` enforces this.
