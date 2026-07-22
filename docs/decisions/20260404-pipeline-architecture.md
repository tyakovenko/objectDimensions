# Pipeline Architecture
**Date:** 2026-04-04  
**Status:** Accepted  
**Scope:** Global project architecture — all phases follow this structure

---

## Context

The project progresses through multiple phases (object prototype → human body → SaaS product). Each phase changes *what* runs at each step but not *the steps themselves*. The architecture must allow component swapping without pipeline rewrites.

---

## Decision

A linear pipeline with one controlled feedback loop (validation recovery). Each step is an interface with swappable implementations. Intermediate results are passed as Python objects AND persisted to disk for debuggability.

### Pipeline Steps

```
1. Ingest
2. Segment
3. Validate (may trigger recovery → re-segment)
4. Estimate Pose
5. Calibrate
6. Reconstruct
7. Measure
8. Report
```

### Data Flow

```
                ┌──────────────────────────────────┐
                │          Recovery Loop            │
                │  (correct image → re-segment)     │
                └──────┬───────────────▲───────────┘
                       │               │
Photos + Config        │               │
    │                  │               │
    ▼                  ▼               │
┌─────────┐    ┌─────────────┐    ┌──────────┐
│ Ingest   │───▶│  Segment    │───▶│ Validate │
└─────────┘    └─────────────┘    └────┬─────┘
                                       │
                                       ▼
                               ┌──────────────┐
                               │ Estimate Pose│
                               └──────┬───────┘
                                      │
                                      ▼
                               ┌─────────────┐
                               │  Calibrate   │
                               └──────┬───────┘
                                      │
                                      ▼
                               ┌─────────────┐
                               │ Reconstruct  │──┐
                               └─────────────┘  │ (may run N times
                                      │         │  for N poses)
                                      ◄─────────┘
                                      │
                                      ▼
                               ┌─────────────┐
                               │   Measure    │
                               └──────┬───────┘
                                      │
                                      ▼
                               ┌─────────────┐
                               │   Report     │
                               └─────────────┘
```

### Step Definitions

#### 1. Ingest
**Input:** Directory of photos + config (object type, known dimensions, pose labels)  
**Output:** `ImageSet` — list of `CaptureImage` objects, each tagged with `view` (front/right/back/left) and `pose_id`  
**Phase 1:** Single pose ("default"), 4 views  
**Phase 2+:** Multiple poses (arms_down, arms_90), 4 views each → 8+ images

```python
@dataclass
class CaptureImage:
    path: Path
    view: str          # "front" | "right" | "back" | "left"
    pose_id: str       # "default" for objects, "arms_down" | "arms_90" for humans
    raw: np.ndarray    # loaded image
    exif: dict         # metadata (focal length, timestamp, orientation)

@dataclass
class ImageSet:
    images: list[CaptureImage]
    config: PipelineConfig
```

#### 2. Segment
**Input:** `ImageSet`  
**Output:** `SegmentationResult` — masks + confidence per image  
**Implementations:** `SAM2Segmenter`, `GrabCutSegmenter` (fallback)  
**Phase 1–2+:** Same interface, possibly different prompting strategies for humans

```python
@dataclass
class SegmentedImage:
    source: CaptureImage
    mask: np.ndarray           # binary mask
    confidence: float          # model confidence
    contour: np.ndarray        # extracted contour points

class Segmenter(Protocol):
    def segment(self, image_set: ImageSet) -> SegmentationResult: ...
```

#### 3. Validate
**Input:** `SegmentationResult` + `ImageSet`  
**Output:** `ValidationReport` — IQS scores, warnings, recovery proposals  
**Side effect:** May modify images (Tier 1 auto-corrections) and trigger re-segmentation (Tier 2 accepted corrections)  
**This is the only step with a feedback loop.**

```python
@dataclass
class ValidationReport:
    composite_iqs: float
    quality_label: str         # "good" | "medium" | "bad"
    per_image: dict            # metric breakdown per image
    cross_view: dict           # cross-view metric scores
    warnings: list[str]
    recommendations: list[str]
    corrections_applied: list[str]  # what was auto-fixed or user-accepted
```

#### 4. Estimate Pose
**Input:** `SegmentationResult`  
**Output:** `PoseEstimate` — 2D keypoints per image (or passthrough for objects)  
**Phase 1:** No-op — returns empty keypoints  
**Phase 2+:** MediaPipe or similar → 2D joint locations per view

```python
@dataclass
class PoseEstimate:
    keypoints: dict[str, np.ndarray]  # per image: Nx2 array of joint coords
    confidence: dict[str, float]       # per image: overall pose confidence

class PoseEstimator(Protocol):
    def estimate(self, segmentation: SegmentationResult) -> PoseEstimate: ...

class NullPoseEstimator:
    """Phase 1: no pose estimation for objects."""
    def estimate(self, segmentation: SegmentationResult) -> PoseEstimate:
        return PoseEstimate(keypoints={}, confidence={})
```

#### 5. Calibrate
**Input:** `SegmentationResult` + `PoseEstimate` + user-provided reference dimension  
**Output:** `CalibrationResult` — camera models + scale factors

```python
@dataclass
class CameraModel:
    view: str
    pose_id: str
    projection_type: str       # "orthographic" | "pinhole"
    pixels_per_unit: float     # scale factor
    # pinhole-specific (Phase 1 may not use):
    focal_length: float | None
    principal_point: tuple | None

@dataclass
class CalibrationResult:
    cameras: list[CameraModel]
    reference_dimension: float  # user-provided height/known dimension
    reference_unit: str         # "in" | "cm"
```

#### 6. Reconstruct
**Input:** `SegmentationResult` + `CalibrationResult` + `PoseEstimate`  
**Output:** `Reconstruction` — 3D mesh with metric scale  
**Implementations:** `VisualHullReconstructor` (Phase 1), `SMPLReconstructor` (Phase 2+)  
**Multi-pose:** Runs once per pose_id. Phase 1 = 1 run. Phase 2+ = 2 runs (arms_down, arms_90)

```python
@dataclass
class Reconstruction:
    pose_id: str
    mesh: trimesh.Trimesh      # scaled to real-world units
    voxel_resolution: int | None  # for visual hull
    method: str                # "visual_hull" | "smpl"

class Reconstructor(Protocol):
    def reconstruct(
        self,
        segmentation: SegmentationResult,
        calibration: CalibrationResult,
        pose: PoseEstimate,
        pose_id: str,
    ) -> Reconstruction: ...
```

#### 7. Measure
**Input:** list of `Reconstruction` (one per pose) + `MeasurementSchema`  
**Output:** `MeasurementProfile`  
**Schema defines what to measure and from which pose's reconstruction.**

```python
@dataclass
class MeasurementDef:
    name: str              # "circumference_mid", "chest", "waist"
    pose_id: str           # which pose's reconstruction to use
    method: str            # "cross_section_circumference" | "vertex_distance" | "contour_perimeter"
    params: dict           # method-specific: {"height_fraction": 0.5} for cross-section

@dataclass
class MeasurementSchema:
    measurements: list[MeasurementDef]

@dataclass
class MeasurementResult:
    name: str
    value: float
    unit: str
    confidence: float      # derived from IQS + reconstruction quality
    pose_id: str

@dataclass
class MeasurementProfile:
    results: list[MeasurementResult]
    schema_used: str
    iqs: float             # carried from validation

class Measurer(Protocol):
    def measure(
        self,
        reconstructions: list[Reconstruction],
        schema: MeasurementSchema,
    ) -> MeasurementProfile: ...
```

**Phase 1 schema example (object):**
```python
OBJECT_SCHEMA = MeasurementSchema(measurements=[
    MeasurementDef("height", "default", "bbox_extent", {"axis": "z"}),
    MeasurementDef("circumference_top", "default", "cross_section_circumference", {"height_fraction": 0.9}),
    MeasurementDef("circumference_mid", "default", "cross_section_circumference", {"height_fraction": 0.5}),
    MeasurementDef("circumference_bottom", "default", "cross_section_circumference", {"height_fraction": 0.1}),
    MeasurementDef("width_mid", "default", "cross_section_bbox", {"height_fraction": 0.5, "axis": "x"}),
    MeasurementDef("depth_mid", "default", "cross_section_bbox", {"height_fraction": 0.5, "axis": "y"}),
])
```

**Phase 2 schema sketch (tailor — minimum 7 measurements):**
```python
TAILOR_SCHEMA = MeasurementSchema(measurements=[
    MeasurementDef("chest", "arms_90", "cross_section_circumference", {"landmark": "chest_line"}),
    MeasurementDef("waist", "arms_down", "cross_section_circumference", {"landmark": "waist_line"}),
    MeasurementDef("hips", "arms_down", "cross_section_circumference", {"landmark": "hip_line"}),
    MeasurementDef("shoulder_width", "arms_down", "vertex_distance", {"from": "left_shoulder", "to": "right_shoulder"}),
    MeasurementDef("sleeve_length", "arms_90", "vertex_path_length", {"path": ["shoulder", "elbow", "wrist"]}),
    MeasurementDef("inseam", "arms_down", "vertex_path_length", {"path": ["crotch", "inner_ankle"]}),
    MeasurementDef("torso_length", "arms_down", "vertex_distance", {"from": "neck_base", "to": "waist_center"}),
    # ... more as needed
])
```

#### 8. Report
**Input:** `MeasurementProfile` + `ValidationReport` + `Reconstruction`  
**Output:** `OutputBundle` — JSON measurements, visualizations, IQS summary, confidence flags

```python
@dataclass
class OutputBundle:
    measurements: MeasurementProfile
    validation: ValidationReport
    visualizations: list[Path]     # saved figures
    output_dir: Path
```

### Pipeline Runner

```python
class Pipeline:
    def __init__(self, config: PipelineConfig):
        self.segmenter = load_segmenter(config.segmentation)
        self.validator = InputValidator(config.validation)
        self.pose_estimator = load_pose_estimator(config.pose_estimation)
        self.calibrator = load_calibrator(config.calibration)
        self.reconstructor = load_reconstructor(config.reconstruction)
        self.measurer = load_measurer(config.measurement)
        self.reporter = Reporter(config.output)

    def run(self, image_dir: Path, reference_dim: float) -> OutputBundle:
        images = ingest(image_dir)
        segmentation = self.segmenter.segment(images)
        validation = self.validator.validate(images, segmentation)

        # Recovery loop (runs at most once)
        if validation.has_corrections():
            corrected = validation.apply_accepted_corrections(images)
            segmentation = self.segmenter.segment(corrected)
            validation = self.validator.validate(corrected, segmentation)

        pose = self.pose_estimator.estimate(segmentation)
        calibration = self.calibrator.calibrate(segmentation, pose, reference_dim)

        # Reconstruct per pose
        pose_ids = images.unique_pose_ids()
        reconstructions = [
            self.reconstructor.reconstruct(segmentation, calibration, pose, pid)
            for pid in pose_ids
        ]

        profile = self.measurer.measure(reconstructions, self.config.schema)
        return self.reporter.report(profile, validation, reconstructions)
```

### Persistence

Every step saves its output to disk under `output/{run_id}/`:
```
output/
└── 2026-04-10_soup_can_good/
    ├── config.json
    ├── masks/
    │   ├── front.png
    │   └── ...
    ├── validation.json
    ├── calibration.json
    ├── reconstruction/
    │   ├── default.ply          # mesh file
    │   └── default_voxels.npy   # raw voxel grid
    ├── measurements.json
    └── figures/
        ├── mask_overlay_front.png
        ├── mesh_3d.png
        └── cross_sections.png
```

This is for debugging and report generation, not for pipeline data flow. The pipeline passes Python objects between steps.

---

## DAG Note

The current linear + one loop design is sufficient through Phase 3. A true DAG executor becomes necessary if:
- Multiple reconstruction methods run in parallel and results are compared/merged
- Validation triggers selective re-processing (only re-segment the bad images, not all 4)
- The pipeline branches (e.g., run SMPL fitting AND depth estimation, then fuse results)

Phase 4 (SMPL + depth fusion) is the likely trigger for DAG migration. When that happens, consider a lightweight DAG runner (not Airflow/Prefect — those are infra-scale). Something like a topological sort over step dependencies with caching. ~100 lines of code, or adopt hamilton/dagster-lite if the complexity warrants it.

Do NOT pre-build the DAG executor. Build it when the linear model actually breaks.

---

## Rejected

- **Full DAG from day 1:** Overengineering. The only feedback loop is validation recovery, and it runs once. A DAG executor adds complexity that slows Phase 1 for no benefit.
- **File-based data flow between steps:** Too slow, too rigid. Parsing serialized masks/meshes between steps adds I/O overhead and format coupling. Python object passing is faster and more natural. Files are saved as a side effect for debugging, not as the communication mechanism.
- **Open3D for mesh processing:** SMPL ecosystem uses trimesh. Having both creates dependency conflicts and API confusion. trimesh handles everything Phase 1 needs.

---

## Consequences

- Every pipeline component is swappable via config. Phase transitions don't require pipeline rewrites.
- `pose_id` is built into every data structure from day 1. Multi-pose (arms_down + arms_90) works without refactoring.
- Intermediate outputs are always on disk. Any step can be inspected or re-run independently.
- The pipeline runner is ~50 lines. Complexity lives in the components, not the orchestration.
- Phase 1 components (VisualHullReconstructor, NullPoseEstimator) are simple implementations that validate the architecture before the hard stuff arrives in Phase 2.
