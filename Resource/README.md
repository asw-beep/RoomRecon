# Resource/

Source papers. **The PDFs are gitignored** — third-party copyright, large binaries. Keep
your local copies here; they will not be committed.

| File | Paper | Role in RoomRecon |
|---|---|---|
| `2308.04079v1.pdf` | 3D Gaussian Splatting for Real-Time Radiance Field Rendering | **Core.** Primary scene representation, optimization + density control, fast rasterization |
| `2007.11898v2.pdf` | ORB-SLAM3 | **Core.** Camera poses from video; keyframes, loop closing, relocalization |
| `Dai_ScanNet_Richly-Annotated_3D_CVPR_2017_paper.pdf` | ScanNet | Methodology and evaluation reference. RGB-D, so **not** our runtime pipeline |
| `2201.05989v2.pdf` | Instant-NGP (multiresolution hash encoding) | Experimental baseline — the acceleration question |
| `123460392.pdf` | NeRF *(identified by elimination — worth confirming)* | Conceptual foundation, experimental baseline |

## How these are used

The papers answer *"what techniques exist?"* This project answers *"how does a person
actually use them?"* We are not reproducing these results and we do not restate their
performance numbers as our own — their figures came from their hardware. Ours come from
`docs/evaluation/`.

See `docs/adr/` for which techniques were adopted, which were made experimental, and why.
