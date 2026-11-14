"""Derm Foundation embeddings for the downloaded Fitzpatrick17k photos (local files).

.venv/bin/python ml/embed_fitz.py   -> ml/data/fitz/emb.npz (emb, md5hash)
"""
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from embed_scin import BATCH, Embedder, to_example  # noqa: E402

FITZ = Path(__file__).resolve().parent / "data" / "fitz"


def main():
    f = pd.read_csv(FITZ / "final.csv")
    e = Embedder()
    e._fetch = lambda p: to_example(Path(p).read_bytes())  # local file instead of Google Cloud
    embs, keep, t0 = [], [], time.time()
    for b in range(0, len(f), BATCH):
        part = f.iloc[b:b + BATCH]
        emb, ok = e.embed(part.file.tolist())
        embs.append(emb)
        keep += [part.md5hash.iloc[i] for i in ok]
        if (b // BATCH) % 8 == 0:
            done = b + len(part)
            print(f"{done}/{len(f)} | {(time.time()-t0)/done:.2f}s/img | ~{(len(f)-done)*(time.time()-t0)/done/60:.0f} min left", flush=True)
    np.savez_compressed(FITZ / "emb.npz", emb=np.concatenate(embs), md5hash=np.array(keep))
    print(f"DONE {len(keep)} embeddings")


if __name__ == "__main__":
    main()
