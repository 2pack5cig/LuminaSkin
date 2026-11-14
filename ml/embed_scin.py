"""Turn SCIN photos into Derm Foundation embeddings (6,144 numbers each) on this Mac's CPU.

Usage (from the project folder):
  .venv/bin/python ml/embed_scin.py audit   # download CSVs, filter labelled cases, print counts
  .venv/bin/python ml/embed_scin.py time    # time 20 images after warm-up
  .venv/bin/python ml/embed_scin.py run     # full run, resumable (skips chunks already saved)
"""
import ast
import io
import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "ml" / "data"
EMB_DIR = DATA / "embeddings"
BUCKET = "dx-scin-public-data"
CHUNK, BATCH = 256, 16
GRAD_COLS = [f"dermatologist_gradable_for_skin_condition_{i}" for i in (1, 2, 3)]
IMG_COLS = [f"image_{i}_path" for i in (1, 2, 3)]

logging.getLogger("urllib3.connectionpool").setLevel(logging.ERROR)


def bucket():
    from google.cloud import storage
    return storage.Client.create_anonymous_client().bucket(BUCKET)


def load_csvs(b):
    DATA.mkdir(parents=True, exist_ok=True)
    out = []
    for name in ("scin_cases.csv", "scin_labels.csv"):
        local = DATA / name
        if not local.exists():
            local.write_bytes(b.blob(f"dataset/{name}").download_as_bytes())
        out.append(pd.read_csv(local, dtype={"case_id": str}))
    return out


def labelled_cases(cases, labels):
    df = cases.merge(labels, on="case_id", how="inner")
    df = df[df["weighted_skin_condition_label"].notna()].copy()
    # values look like DEFAULT_YES_IMAGE_QUALITY_SUFFICIENT / NO_IMAGE_QUALITY_INSUFFICIENT /
    # YES_IMAGE_QUALITY_SUFFICIENT_NO_DISCERNIBLE_PATHOLOGY -> keep cases where any derm said gradable with pathology
    grad = pd.concat([df[c].astype(str).isin(["DEFAULT_YES_IMAGE_QUALITY_SUFFICIENT"]) for c in GRAD_COLS], axis=1)
    df = df[grad.any(axis=1)].copy()
    w = df["weighted_skin_condition_label"].map(ast.literal_eval)
    df = df[w.map(len) > 0].copy()
    w = w[df.index]
    df["top_label"] = w.map(lambda d: max(d, key=d.get))
    df["top_weight"] = w.map(lambda d: max(d.values()))
    # skin type: dermatologist estimate (majority of up to 3) first, self-reported as fallback
    derm = df[[f"dermatologist_fitzpatrick_skin_type_label_{i}" for i in (1, 2, 3)]]
    derm_mode = derm.apply(lambda r: r.dropna().mode().iloc[0] if r.notna().any() else None, axis=1)
    fst_raw = derm_mode.fillna(df["fitzpatrick_skin_type"])
    fst = {f"FST{i}": ("I-III" if i <= 3 else "IV-VI") for i in range(1, 7)}
    df["fst"] = fst_raw
    df["fst_group"] = fst_raw.map(fst).fillna("unknown")
    return df.reset_index(drop=True)


def image_index(df):
    rows = [(c, p) for c, paths in zip(df["case_id"], df[IMG_COLS].values)
            for p in paths if isinstance(p, str) and p]
    return pd.DataFrame(rows, columns=["case_id", "path"]).drop_duplicates("path").reset_index(drop=True)


def audit():
    b = bucket()
    cases, labels = load_csvs(b)
    print(f"cases: {len(cases)}  labels: {len(labels)}")
    df = labelled_cases(cases, labels)
    print(f"labelled + gradable cases: {len(df)}")
    df.to_csv(DATA / "labelled_cases.csv", index=False)
    counts = pd.crosstab(df["top_label"], df["fst_group"])
    counts["total"] = counts.sum(axis=1)
    counts = counts.sort_values("total", ascending=False)
    counts.to_csv(DATA / "label_counts.csv")
    with pd.option_context("display.max_rows", 60, "display.width", 120):
        print(counts.head(50))
    imgs = image_index(df)
    imgs.to_csv(DATA / "image_index.csv", index=False)
    print(f"images to embed: {len(imgs)}")
    print("example path:", imgs["path"].iloc[0])


# ---------- embedding ----------
def load_model():
    import tensorflow as tf
    from dotenv import load_dotenv
    from huggingface_hub import snapshot_download
    load_dotenv(ROOT / "backend" / ".env")
    token = os.getenv("HF_TOKEN") or None
    path = snapshot_download("google/derm-foundation", token=token)
    with tf.device("/CPU:0"):
        model = tf.saved_model.load(path)
    return model, model.signatures["serving_default"]


def to_example(raw):
    import tensorflow as tf
    from PIL import Image
    img = Image.open(io.BytesIO(raw)).convert("RGB")
    w, h = img.size
    s = max(w, h)
    sq = Image.new("RGB", (s, s))
    sq.paste(img, ((s - w) // 2, (s - h) // 2))  # pad to square, keep the whole photo
    buf = io.BytesIO()
    sq.resize((448, 448)).save(buf, format="PNG")
    return tf.train.Example(features=tf.train.Features(feature={
        "image/encoded": tf.train.Feature(bytes_list=tf.train.BytesList(value=[buf.getvalue()]))
    })).SerializeToString()


class Embedder:
    def __init__(self):
        self.b = bucket()
        self.pool = ThreadPoolExecutor(16)
        _, self.infer = load_model()

    def _fetch(self, p):
        try:
            return to_example(self.b.blob(p).download_as_bytes())
        except Exception as e:  # noqa: BLE001
            print(f"  skip {p}: {e}", file=sys.stderr)
            return None

    def embed(self, paths):
        import tensorflow as tf
        exs = list(self.pool.map(self._fetch, paths))
        ok = [i for i, e in enumerate(exs) if e is not None]
        if not ok:
            return np.zeros((0, 6144), np.float32), ok
        with tf.device("/CPU:0"):
            out = self.infer(inputs=tf.constant([exs[i] for i in ok]))["embedding"].numpy()
        return out.reshape(len(ok), -1).astype(np.float32), ok


def load_index():
    f = DATA / "image_index.csv"
    if not f.exists():
        sys.exit("Run `audit` first.")
    return pd.read_csv(f, dtype={"case_id": str})


def time_it():
    imgs = load_index()
    e = Embedder()
    t = time.time(); e.embed(imgs["path"][:BATCH].tolist()); print(f"warm-up batch: {time.time()-t:.1f}s")
    t = time.time(); emb, ok = e.embed(imgs["path"][BATCH:BATCH + 20].tolist()); dt = time.time() - t
    per = dt / max(len(ok), 1)
    print(f"shape {emb.shape}  {per:.2f} s/image  ->  about {per*len(imgs)/3600:.1f} h for {len(imgs)} images")


def run():
    imgs = load_index()
    EMB_DIR.mkdir(parents=True, exist_ok=True)
    e = Embedder()
    t0 = time.time(); done = 0
    for start in range(0, len(imgs), CHUNK):
        f = EMB_DIR / f"chunk_{start:06d}.npz"
        if f.exists():
            continue
        part = imgs.iloc[start:start + CHUNK]
        embs, idx = [], []
        for bstart in range(0, len(part), BATCH):
            emb, ok = e.embed(part["path"].iloc[bstart:bstart + BATCH].tolist())
            embs.append(emb)
            idx += [int(part.index[bstart + i]) for i in ok]
        np.savez_compressed(f, emb=np.concatenate(embs), image_idx=np.array(idx))
        done += len(part)
        rate = (time.time() - t0) / done
        left = (len(imgs) - start - len(part)) * rate / 3600
        print(f"{f.name}: {len(idx)} imgs | {rate:.2f}s/img | ~{left:.1f} h left", flush=True)
    print("ALL DONE")


def done_indices():
    done = set()
    for f in EMB_DIR.glob("*.npz"):
        done |= set(np.load(f)["image_idx"].tolist())
    return done


def run_final():
    """Embed only images of cases in cases_final.csv that aren't embedded yet (image_idx = row in image_index.csv)."""
    imgs = load_index()
    final = set(pd.read_csv(DATA / "cases_final.csv", dtype={"case_id": str})["case_id"])
    todo = imgs[imgs["case_id"].isin(final) & ~imgs.index.isin(done_indices())]
    print(f"{len(todo)} images left for the final disease list", flush=True)
    e = Embedder()
    t0 = time.time()
    for n, start in enumerate(range(0, len(todo), CHUNK)):
        part = todo.iloc[start:start + CHUNK]
        embs, idx = [], []
        for bstart in range(0, len(part), BATCH):
            emb, ok = e.embed(part["path"].iloc[bstart:bstart + BATCH].tolist())
            embs.append(emb)
            idx += [int(part.index[bstart + i]) for i in ok]
        np.savez_compressed(EMB_DIR / f"final_{int(time.time())}_{n:03d}.npz", emb=np.concatenate(embs), image_idx=np.array(idx))
        rate = (time.time() - t0) / (start + len(part))
        print(f"final chunk {n}: {len(idx)} imgs | {rate:.2f}s/img | ~{(len(todo)-start-len(part))*rate/60:.0f} min left", flush=True)
    print("ALL DONE")


if __name__ == "__main__":
    {"audit": audit, "time": time_it, "run": run, "final": run_final}[sys.argv[1] if len(sys.argv) > 1 else "audit"]()
