# Body Measurement Tool — Brainstorm
**Date:** 2026-04-02  
**Status:** Ground 0 — pre-execution, research phase

---

## Problem Statement

Build a phone-based tool that extracts tailor-grade human body measurements from photos. Output is an accurate 3D body model from which standard tailor measurements can be read. Target accuracy: ±0.25 inch.

---

## Key Constraints

- **Input:** 4 photos (front, left, right, back) + user-provided height. Modular — inputs can be added or removed.
- **Platform:** All phones (iOS + Android). No device-specific hardware dependency.
- **Accuracy:** ±0.25 inch — tailor/custom clothing grade.
- **UX:** Minimal user friction. Height is acceptable as the one required manual input.
- **Output:** A 3D mesh from which measurements are extracted programmatically.

---

## The Fundamental Problem: Scale

A phone camera sees angles, not distances. Without a known reference, absolute measurements are impossible. Three viable solutions evaluated:

| Solution | Accuracy | Friction | Device dependency |
|---|---|---|---|
| User inputs height | High | Low (one number) | None — **chosen** |
| Reference object in frame | High | Medium | None |
| LiDAR depth sensor | Very high | None | iPhone 12 Pro+ only |
| Pure AI body model | Medium (~1–2cm) | None | None |

**Decision:** Height as required input. LiDAR noted as a high-value optional enhancement — design the architecture to accept it as a plug-in signal on supported devices.

---

## Prototype Strategy

Before tackling the human body, validate the full pipeline on a simple physical object.

**Chosen prototype object:** A cylindrical object with known dimensions (soup can, cardboard tube). Avoid:
- Spheres (no clear "up" — loses height anchor)
- Reflective or transparent surfaces (breaks feature matching)
- The apple idea was discarded for these reasons

**Why this works:** You can measure ground truth with a tape measure. Validates segmentation quality, reconstruction accuracy, and scale anchoring before introducing the complexity of the human body.

**Expected learning:** Where pipeline error originates — segmentation noise, reconstruction gaps, or scale drift.

---

## Pipeline (Shared Across All Approaches)

```
Photos + height
    → Segmentation       (isolate subject from background)
    → Pose estimation    (locate joints / landmarks)
    → 3D reconstruction  (build the model)  ← approaches differ here
    → Measurement extraction (read off the mesh)
```

---

## Approach A: Visual Hull (Pure Math)

**How it works:** For each silhouette, carve away space the object *cannot* occupy. The intersection across all views forms a conservative 3D shape — the visual hull.

**Verdict:** Use for the prototype only. Concave surfaces (armpits, waist indent) are invisible to it — it always overestimates volume. Unusable for human tailor measurements, but ideal for validating the prototype pipeline.

**Sources:**
- Laurentini, A. (1994). *The visual hull concept for silhouette-based image understanding.* IEEE Transactions on Pattern Analysis and Machine Intelligence. — foundational paper defining the concept.
- COLMAP — open-source multi-view stereo and SfM pipeline, implements visual hull variants. https://colmap.github.io
- Hartley & Zisserman, *Multiple View Geometry in Computer Vision* (2nd ed.) — textbook covering the math. Chapter 12 covers silhouette-based reconstruction.

---

## Approach B: SMPL Body Model Fitting (Industry Standard)

**How it works:** SMPL is a parametric 3D human body model trained on thousands of body scans. It has ~10 shape parameters (β) and ~72 pose parameters (θ). Given 4 silhouettes + pose keypoints + height, run an optimization to find the β/θ that best explain what the cameras see. Output is a full human mesh.

```
silhouettes + keypoints + height
    → optimize SMPL(β, θ) to match observations
    → full human mesh
    → extract measurements from mesh vertices
```

**Pros:** Fills occluded geometry plausibly, outputs a watertight mesh, open source, well-studied, production-proven.  
**Cons:** Optimization can get stuck in local minima. The average-body prior can pull unusual body types toward the mean. Fitting requires compute (cloud vs. on-device is an open question).

**What commercial tools use this:** 3DLOOK, Bodygram, MTailor — all fit a parametric body model under the hood.

**Sources:**
- Loper et al. (2015). *SMPL: A Skinned Multi-Person Linear Model.* ACM SIGGRAPH Asia. — the original SMPL paper. Start here.
- Pavlakos et al. (2019). *Expressive Body Capture: 3D Hands, Face, and Body from a Single Image.* CVPR. — introduces SMPL-X, an extended version.
- Goel et al. (2023). *Humans in 4D: Reconstructing and Tracking Humans with Transformers (4D-Humans / HMR2).* ICCV. — state-of-the-art SMPL fitting from images. https://shubham-goel.github.io/4dhumans
- Zhang et al. (2021). *PyMAF: 3D Human Pose and Shape Regression with Pyramidal Mesh Alignment Feedback Loop.* ICCV. — strong multi-view SMPL fitting baseline.
- Li et al. (2022). *CLIFF: Carrying Location Information in Full Frames into Human Pose and Shape Estimation.* ECCV. — improves scale accuracy, relevant to the height-anchoring problem.
- MediaPipe Pose (Google) — on-device pose keypoint estimation, feeds into SMPL fitting. https://developers.google.com/mediapipe/solutions/vision/pose_landmarker

---

## Approach C: Direct Regression (Pure ML — Future)

**How it works:** Train a neural network end-to-end: 4 photos → measurement vector. No intermediate 3D model.

**Verdict:** Not a starting point. Requires a labeled dataset (photos + ground truth measurements) that doesn't exist yet. Revisit when data accumulates. Also does not produce a 3D model, which is a stated output goal.

**Sources:**
- Caesar et al. (2021). *STAR: Sparse Trained Articulated Human Body Regressor.* ECCV. — lightweight alternative to SMPL with better generalization.
- Tiwari et al. (2021). *Neural-GIF: Neural Generalized Implicit Functions for Reposing People Using a Single Image.* ICCV. — example of implicit-function regression approaches.
- Review 3DLOOK and Bodygram whitepapers for how commercial systems handle dataset collection at scale.

---

## Approach D: Monocular Depth Estimation + Fusion

**How it works:** Run a depth model on each photo to get a per-pixel depth map. Fuse 4 maps into a pseudo-point cloud. Scale with height.

**Verdict:** Not standalone — monocular depth is relative, not metric. Use as an additional signal fed into Approach B (richer than silhouettes alone). The fusion alignment problem across unconstrained phone photos is non-trivial.

**Sources:**
- Yang et al. (2024). *Depth Anything V2.* — current state of the art for monocular depth. https://depth-anything-v2.github.io
- Ranftl et al. (2020). *Towards Robust Monocular Depth Estimation: Mixing Datasets for Zero-Shot Cross-Dataset Transfer (MiDaS).* IEEE TPAMI.
- Bhat et al. (2023). *ZoeDepth: Zero-Shot Transfer by Combining Relative and Metric Depth.* — addresses the relative-vs-metric problem directly. https://github.com/isl-org/ZoeDepth

---

## Approach E: Sparse-View NeRF / 3D Gaussian Splatting (Future Watch)

**How it works:** Modern neural reconstruction from sparse views. Give 4 photos, get a full 3D model without any body prior.

**Verdict:** 2–3 years from being practical for this use case. Compute-heavy, requires known camera poses, metric accuracy not reliable yet. Note as a future direction — the field is moving fast.

**Sources:**
- Mildenhall et al. (2020). *NeRF: Representing Scenes as Neural Radiance Fields for View Synthesis.* ECCV. — foundational paper.
- Kerbl et al. (2023). *3D Gaussian Splatting for Real-Time Radiance Field Rendering.* SIGGRAPH. — faster alternative to NeRF.
- Liu et al. (2023). *Zero-1-to-3: Zero-Shot One Image to 3D Object.* ICCV. — sparse-view reconstruction.
- Xu et al. (2024). *InstantMesh: Efficient 3D Mesh Generation from a Single Image with Sparse-View Large Reconstruction Models.* — current practical benchmark for sparse-view.

---

## Recommended Progression

```
Stage 1 — Prototype (object)
    Visual hull + known object dimensions
    Goal: validate pipeline, measure error sources

Stage 2 — Human v1
    SMPL fitting on 4 views + height
    Goal: get to ±1in accuracy

Stage 3 — Human v2
    SMPL + monocular depth as additional signal
    Goal: push toward ±0.25in

Stage 4 — Human v3 (data flywheel)
    Fine-tune or distill into direct regression as labeled data accumulates
    Goal: faster inference, higher accuracy
```

---

## Commercial References (Study These)

- **3DLOOK / YourFit** — front + side photo approach, B2B clothing brand integrations
- **Bodygram** — mobile-first, similar parametric approach
- **MTailor** — video scan on phone, uses motion to get more views
- **Sizer.io** — retail-focused, worth studying UX approach

---

## Open Questions

1. **Compute budget:** Is SMPL fitting done on-device or in the cloud? On-device limits model size and optimization iterations. Cloud adds latency and infrastructure cost. This decision affects the entire architecture.

2. **Build vs. build-on:** Build the fitting pipeline from scratch, or extend an existing open-source system (HMR2, PyMAF, CLIFF)? Starting from an existing system is likely faster but introduces dependencies and constraints.

---

## Concrete Further Research Steps

1. **Read the SMPL paper** (Loper et al. 2015) — understand the shape/pose parameter space before evaluating any fitting approach.

2. **Run HMR2 / 4D-Humans demo locally** — get a feel for what SMPL fitting looks like on real photos. Assess output quality and failure modes on diverse body types.

3. **Benchmark Depth Anything V2** on phone-captured photos — determine whether relative depth maps are usable as a supplementary signal or too noisy.

4. **Audit 3DLOOK, Bodygram, MTailor** as a user — take measurements with each, compare to tape measure ground truth on yourself. Document where they fail.

5. **Evaluate MediaPipe Pose** on-device — run on 4 photos of a person, assess keypoint quality and consistency across views. This is the likely pose input to SMPL fitting.

6. **Build the prototype pipeline** — take 4 photos of a cylindrical object with known dimensions. Implement visual hull. Measure output vs. tape measure. Record error.

7. **Study SAM (Segment Anything Model)** for segmentation — evaluate whether it handles arbitrary phone backgrounds reliably enough for production use. https://segment-anything.com

8. **Resolve open question #1 (compute)** — benchmark SMPL fitting time on a mid-range phone vs. a cloud endpoint. This gates the architecture decision.

9. **Resolve open question #2 (build vs. extend)** — read PyMAF and CLIFF codebases. Assess what would need to change to support 4-view input with height anchoring. Estimate scope.

10. **Define measurement extraction schema** — decide which measurements matter (chest, waist, hips, inseam, shoulder width, etc.) and map each to SMPL mesh vertices. This is a non-trivial alignment task and should be designed before the model is built.
