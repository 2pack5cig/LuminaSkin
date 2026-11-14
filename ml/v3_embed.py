"""Derm Foundation embeddings for every v3 photo that doesn't have one yet (resumable), plus a 384-px
square cache for EfficientNet. Reuses the SCIN embeddings already computed.

.venv/bin/python ml/v3_embed.py   -> ml/data/v3/emb/*.npz (emb, key), ml/data/v3/cache/<key>.jpg
"""
import glob
import io
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from embed_scin import BATCH, Embedder, to_example  # noqa: E402

V3 = ROOT / "data" / "v3"
EMB, CACHE = V3 / "emb", V3 / "cache"
CHUNK = 256


def pad384(raw):
    img = Image.open(io.BytesIO(raw)).convert("RGB")
    w, h = img.size
    s = max(w, h)
    sq = Image.new("RGB", (s, s))
    sq.paste(img, ((s - w) // 2, (s - h) // 2))
    return sq.resize((384, 384))


def have():
    keys = set()
    for f in glob.glob(str(ROOT / "data" / "embeddings" / "*.npz")):          # existing SCIN embeddings
        keys |= {f"scin_{i}" for i in np.load(f)["image_idx"].tolist()}
    for f in glob.glob(str(EMB / "*.npz")):
        keys |= set(np.load(f, allow_pickle=True)["key"].tolist())
    return keys


def main():
    EMB.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(V3 / "images.csv")
    todo = df[~df.key.isin(have())].reset_index(drop=True)
    print(f"{len(todo)} photos to embed", flush=True)
    e = Embedder()

    def fetch(i):
        r = todo.iloc[i]
        try:
            raw = Path(r.local).read_bytes() if r.source != "SCIN" else e.b.blob(r.gcs_path).download_as_bytes()
            c = CACHE / f"{r.key}.jpg"
            if not c.exists():
                pad384(raw).save(c, quality=92)
            return to_example(raw)
        except Exception as ex:  # noqa: BLE001
            print("  skip", r.key, ex, file=sys.stderr)
            return None

    e._fetch = fetch
    t0 = time.time()
    for n, start in enumerate(range(0, len(todo), CHUNK)):
        embs, keys = [], []
        for b in range(start, min(start + CHUNK, len(todo)), BATCH):
            ids = list(range(b, min(b + BATCH, start + CHUNK, len(todo))))
            emb, ok = e.embed(ids)
            embs.append(emb)
            keys += [todo.key.iloc[ids[i]] for i in ok]
        np.savez_compressed(EMB / f"v3_{int(time.time())}_{n:03d}.npz", emb=np.concatenate(embs), key=np.array(keys))
        done = min(start + CHUNK, len(todo))
        rate = (time.time() - t0) / done
        print(f"{done}/{len(todo)} | {rate:.2f}s/img | ~{(len(todo) - done) * rate / 60:.0f} min left", flush=True)
    print("ALL DONE", flush=True)


if __name__ == "__main__":
    main()
