# Data Contracts

Schemas for artifacts that cross a module or tier boundary. **If it crosses a boundary, it
conforms to a schema here.** Anything else is an internal detail of one module.

Two rules apply to every artifact:

- **Stamped with provenance.** `pipeline_version` and `config_hash` on every file, so any
  output can be traced to the inputs and settings that produced it.
- **Stamped with tier.** Anything carrying a measurement records whether it came from T1 or
  T2. A number without its tier is meaningless (ADR-005).

Schemas are **provisional until the producing milestone lands** — fields marked *(M2)*,
*(M3)* etc. are finalized by that milestone. They are recorded now so modules are written
against a contract rather than against each other.

---

## Common envelope

Every artifact carries:

```json
{
  "schema_version": "1.0",
  "pipeline_version": "0.1.0",
  "config_hash": "sha256:...",
  "project_id": "project_001",
  "created_at": "2026-08-08T12:00:00Z",
  "tier": "T1"
}
```

---

## `quality_report.json` *(M2)*

Produced by `src/capture/`. The rejection gate.

```json
{
  "...envelope": "...",
  "accepted": true,
  "score": 82,
  "video": {
    "codec": "h264", "width": 1920, "height": 1080,
    "fps": 30.0, "duration_s": 47.3, "rotation": 0,
    "intrinsics_source": "exif" 
  },
  "metrics": {
    "blur":            { "value": 0.0, "status": "pass" },
    "exposure":        { "value": 0.0, "status": "pass" },
    "feature_density": { "value": 0.0, "status": "pass" },
    "frame_overlap":   { "value": 0.0, "status": "pass" },
    "camera_motion":   { "value": 0.0, "status": "pass" },
    "coverage":        { "value": 0.0, "status": "warn" }
  },
  "rejections": [],
  "recommendations": [
    "Move closer to the rear wall and capture another 3-5 seconds."
  ]
}
```

`status` ∈ `pass | warn | fail`. `intrinsics_source` ∈ `exif | calibration | fallback`.
Any `fail` sets `accepted: false` and populates `rejections` with human-readable reasons.

**Recommendations must be actionable.** "Low feature density" is a metric; "point the
camera at textured surfaces, not blank walls" is a recommendation.

---

## `frame_manifest.json` *(M2)*

Produced by `src/preprocessing/`. **The determinism contract lives here** — same video,
same config, same seed → byte-identical manifest.

```json
{
  "...envelope": "...",
  "seed": 42,
  "source_frame_count": 1419,
  "selected_frame_count": 184,
  "keyframe_count": 63,
  "frames": [
    {
      "index": 0,
      "source_index": 0,
      "path": "frames/000000.jpg",
      "timestamp_s": 0.0,
      "is_keyframe": true,
      "blur_score": 0.0,
      "selection_reason": "keyframe"
    }
  ]
}
```

`selection_reason` ∈ `keyframe | fill | seed_frame`. Frames not selected are absent, with
counts reconcilable against `source_frame_count`.

---

## `camera_poses.json` *(M3)*

Produced by `src/tracking/`. Consumed by sparse validation and Gaussian training. **Crosses
the tier boundary** (T1 → T2).

```json
{
  "...envelope": "...",
  "estimator": "colmap",
  "coordinate_convention": "TBD - M3",
  "scale": "arbitrary",
  "intrinsics": {
    "model": "PINHOLE",
    "width": 1920, "height": 1080,
    "fx": 0.0, "fy": 0.0, "cx": 0.0, "cy": 0.0,
    "distortion": []
  },
  "poses": [
    {
      "frame_index": 0,
      "frame_path": "frames/000000.jpg",
      "qvec": [1.0, 0.0, 0.0, 0.0],
      "tvec": [0.0, 0.0, 0.0],
      "tracking_status": "tracked"
    }
  ],
  "tracking": {
    "tracked_frames": 184,
    "lost_frames": 0,
    "loop_closed": true,
    "failure": null
  }
}
```

`estimator` ∈ `colmap | orbslam3` (ADR-004). `tracking_status` ∈ `tracked | lost |
relocalized`.

**`"scale": "arbitrary"` is mandatory and non-negotiable** — monocular scale is
unobservable (ADR-002). No consumer may treat these translations as metric, and the UI must
surface this to the user.

`coordinate_convention` is finalized at M3 once the pose source is chosen; whichever it is,
it is stated explicitly here rather than assumed.

---

## Sparse point cloud *(M3–M4)*

Binary, not JSON. COLMAP sparse format or `.ply`, decided with ADR-004. A sidecar
`sparse_summary.json` carries the envelope plus point count, spatial extent, and mean
per-view visibility — the values sparse validation checks before training starts.

---

## `reconstruction_metrics.json` *(M4)*

Produced by `src/reconstruction/gaussian/`. The measured record of one training run.

```json
{
  "...envelope": "...",
  "tier": "T2",
  "hardware": { "gpu": "Tesla P100", "vram_total_mb": 16280 },
  "training": {
    "iterations": 30000,
    "wall_clock_s": 0.0,
    "peak_vram_mb": 0.0,
    "gaussian_count": 0,
    "resumed_from_checkpoint": false,
    "config": "configs/t2_16gb.yaml"
  },
  "quality": {
    "psnr": null, "ssim": null, "lpips": null,
    "held_out_views": 0
  }
}
```

Unmeasured values are `null`, never a placeholder number. `hardware` is recorded verbatim
from the machine — this is what makes cross-tier comparison honest rather than misleading.

---

## `scene.json` *(M5)*

Produced for `src/viewer/`. What the user sees in the metadata panel.

```json
{
  "...envelope": "...",
  "status": "complete",
  "scene_file": "gaussian/scene.ply",
  "scene_bytes": 0,
  "summary": {
    "frames": 184, "keyframes": 63,
    "camera_tracking": "ok", "gaussian_scene": "ok",
    "mesh_available": false,
    "scale": "not metric"
  },
  "camera_path": "poses/camera_poses.json",
  "exports": []
}
```

`status` ∈ `queued | running | failed | complete`. On `failed`, a `failure` object carries
a **user-facing** reason — the viewer must never show a blank screen or a stack trace.

`"scale": "not metric"` is required in the UI-facing summary. ADR-002 requires the
limitation be visible in the product, not buried in documentation.
