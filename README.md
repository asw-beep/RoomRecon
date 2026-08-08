# RoomRecon

Turn a smartphone video of a room into an interactive 3D scene you can explore in a
browser.

```
Record room → Upload → Capture analysis → Reconstruct → Explore → Export
```

No LiDAR. No depth sensor. No 3D-scanning hardware. Just an ordinary phone camera.

## What it does

RoomRecon takes consumer RGB video of an indoor space and produces an interactive **3D
Gaussian Splatting** scene. The user never needs to know what SLAM, COLMAP, or Gaussian
splatting are — they record a room and get a room they can walk through.

Before spending any GPU time, the system analyzes the capture and tells the user whether
it is good enough — and if not, exactly what to re-shoot.

**Primary output:** an interactive 3DGS scene
**Secondary:** camera trajectory + sparse reconstruction
**Optional:** extracted mesh (OBJ / GLB / PLY)

## Status

🚧 **M0 — Architecture Freeze.** Contract and structure are being established; the pipeline
is not yet implemented. See [`docs/ROADMAP.md`](docs/ROADMAP.md) for all ten milestones and
their gates.

## Documentation

| | |
|---|---|
| [Contributing](CONTRIBUTING.md) | Working rules, module boundaries, conventions |
| [Roadmap](docs/ROADMAP.md) | Milestones M0–M9, tasks, and gate criteria |
| [Architecture](docs/architecture/system.md) | Trace one video through the entire system |
| [Decisions](docs/adr/README.md) | ADRs — what was chosen, what it costs, what was rejected |
| [Data contracts](docs/data-contracts.md) | Artifact schemas across module and tier boundaries |
| [Compute assessment](docs/compute-assessment.md) | What fits on 6 GB, and what has to give |
| [Dependencies](docs/dependency-inventory.md) | Every external dep, tier, and build status |
| [Risks](docs/risks.md) | Living risk register |

## Design principles

**It is a product, not a paper reproduction.** The papers answer *"what techniques exist?"*
This project answers *"how does a person actually use them?"*

**Hard gates.** "The code runs" does not close a milestone. Tests, validation, documented
failure cases, and updated docs do.

**No fabricated numbers.** Every performance figure is `TBD` until measured on real
hardware, and every measurement is reported with the hardware tier it came from.

**Failure paths are features.** Rejecting a bad capture with an actionable reason is worth
more than a pretty reconstruction of a lucky one.

## Known limitations

**Reconstruction is internally consistent, not metric.** Scale is unobservable from
monocular video, so RoomRecon does not provide real-world measurements. This is disclosed
in the product, not buried here.

Also out of scope for v1: mobile apps, multi-user accounts, semantic understanding, object
editing, dynamic scenes, and multi-room mapping.

## Built on

[3D Gaussian Splatting](https://repo-sam.inria.fr/fungraph/3d-gaussian-splatting/) ·
[ORB-SLAM3](https://github.com/UZ-SLAMLab/ORB_SLAM3) ·
[COLMAP](https://colmap.github.io/) ·
[NeRF](https://www.matthewtancik.com/nerf) ·
[Instant-NGP](https://nvlabs.github.io/instant-ngp/) ·
[ScanNet](http://www.scan-net.org/)

Semester project · IIIT Kottayam · Computer Vision
