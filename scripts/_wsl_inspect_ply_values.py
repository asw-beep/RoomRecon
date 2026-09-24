"""scratch - checks whether the exported PLY stores scale/opacity in log/logit space
(INRIA convention, what browser viewers expect) or already-activated linear space."""
import numpy as np, struct, sys

PLY = "/home/aswin/roomrecon/work/south-building-960/3dgs_cap250000_steps7000/ply/point_cloud_6999.ply"

with open(PLY, "rb") as f:
    header, props = b"", []
    while True:
        line = f.readline()
        header += line
        t = line.decode("ascii", "ignore").strip()
        if t.startswith("property float"):
            props.append(t.split()[-1])
        if t == "end_header":
            break
    n = int([l for l in header.decode().splitlines() if l.startswith("element vertex")][0].split()[-1])
    data = np.frombuffer(f.read(n * len(props) * 4), dtype=np.float32).reshape(n, len(props))

idx = {p: i for i, p in enumerate(props)}
print(f"vertices={n} properties={len(props)}")


def stats(name):
    v = data[:, idx[name]]
    return f"{name:10s} min={v.min():9.3f} max={v.max():9.3f} mean={v.mean():8.3f}"


for k in ["scale_0", "scale_1", "scale_2", "opacity", "f_dc_0"]:
    if k in idx:
        print(stats(k))

s = data[:, [idx["scale_0"], idx["scale_1"], idx["scale_2"]]]
o = data[:, idx["opacity"]]
print()
print(f"negative scale values : {(s < 0).mean() * 100:.1f}%  -> log space if high")
print(f"exp(scale) mean       : {np.exp(s).mean():.4f}  (world units)")
print(f"raw scale mean        : {s.mean():.4f}")
print(f"opacity outside [0,1] : {((o < 0) | (o > 1)).mean() * 100:.1f}%  -> logit space if high")
print(f"sigmoid(op) mean      : {(1 / (1 + np.exp(-o))).mean():.3f}")
print()
print("VERDICT:", "log/logit (INRIA standard)" if (s < 0).mean() > 0.5 else "LINEAR/ACTIVATED (non-standard)")
