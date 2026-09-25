#!/usr/bin/env python3
"""Download MuSHRoom iPhone rooms and the COLMAP vocabulary tree, at pinned checksums.

    python scripts/fetch_mushroom.py --dest <dir> koivu vr_room

MuSHRoom (Ren et al., WACV 2024), "iPhone dataset (Basic Data)", Zenodo record 10230733,
CC BY 4.0. Each room is one tarball that unpacks to room_datasets/<room>/iphone/.
A file whose MD5 differs from the pin is deleted and the fetch fails: a changed or truncated
download is a failed download (lessons-learned section 7). Standard library only.
"""
import argparse
import hashlib
import json
import sys
import tarfile
import time
import urllib.request
from pathlib import Path

RECORD = "https://zenodo.org/api/records/10230733/files/{name}/content"
ROOMS = {   # MD5 as published in the Zenodo record, checked 2026-09-25
    "koivu": "a359dba714e7829be11747ce5dee141c",
    "vr_room": "6c411b7bad82041e2fb5eb8d6a46fbf9",
}
VOCAB = ("https://demuc.de/colmap/vocab_tree_flickr100K_words32K.bin",
         "65b200a06e15205bda713c8553953c50")


def download(url: str, out: Path, md5: str) -> dict:
    t0 = time.time()
    h = hashlib.md5()
    with urllib.request.urlopen(url, timeout=120) as r, open(out, "wb") as f:
        while chunk := r.read(1 << 20):
            h.update(chunk)
            f.write(chunk)
    if h.hexdigest() != md5:
        out.unlink()
        raise SystemExit(f"{url}: md5 {h.hexdigest()} != pinned {md5} - deleted")
    return {"file": out.name, "bytes": out.stat().st_size, "md5": md5, "s": round(time.time() - t0, 1)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dest", type=Path, required=True)
    ap.add_argument("rooms", nargs="+", choices=sorted(ROOMS))
    a = ap.parse_args()
    a.dest.mkdir(parents=True, exist_ok=True)
    log = {"record": "zenodo 10230733", "rooms": {}}
    vocab = a.dest / Path(VOCAB[0]).name
    if not vocab.is_file():
        log["vocab_tree"] = download(VOCAB[0], vocab, VOCAB[1])
    for room in a.rooms:
        target = a.dest / "room_datasets" / room / "iphone"
        if (target / "long_capture/transformations.json").is_file():
            log["rooms"][room] = "already present"
            continue
        tgz = a.dest / f"{room}_iphone.tar.gz"
        log["rooms"][room] = download(RECORD.format(name=tgz.name), tgz, ROOMS[room])
        # the "data" filter refuses absolute paths and links out of dest (Python >= 3.10.12)
        safe = {"filter": "data"} if hasattr(tarfile, "data_filter") else {}
        with tarfile.open(tgz) as t:
            t.extractall(a.dest, **safe)
        tgz.unlink()
        if not (target / "long_capture/transformations.json").is_file():
            raise SystemExit(f"{tgz.name} did not unpack to {target}")
    print(json.dumps(log, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
