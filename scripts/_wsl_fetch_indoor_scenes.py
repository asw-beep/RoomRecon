"""scratch - fetches the Deep Blending indoor room scenes (playroom, drjohnson).

Chosen over Mip-NeRF 360 'room' because this mirror ships COLMAP sparse/ poses with them,
so the ~25min exhaustive-matching step is not needed, and they are ~8x smaller.
Both are indoor benchmark scenes from the original 3DGS paper.
"""
from huggingface_hub import snapshot_download
import os

DEST = "/home/aswin/roomrecon/datasets/deepblending"
os.makedirs(DEST, exist_ok=True)

p = snapshot_download(
    repo_id="alexmkwizu/gaussian_training_datasets",
    repo_type="dataset",
    allow_patterns=["db/playroom/**", "db/drjohnson/**"],
    local_dir=DEST,
    max_workers=8,
)
print("downloaded to:", p)

for scene in ("playroom", "drjohnson"):
    root = os.path.join(DEST, "db", scene)
    if not os.path.isdir(root):
        print(f"{scene}: MISSING")
        continue
    imgs = os.path.join(root, "images")
    n = len(os.listdir(imgs)) if os.path.isdir(imgs) else 0
    sparse_parts = []
    for dirpath, _, files in os.walk(os.path.join(root, "sparse")):
        for f in files:
            sparse_parts.append(os.path.relpath(os.path.join(dirpath, f), root))
    print(f"{scene}: {n} images | sparse: {sorted(sparse_parts)}")
