"""v2 data: add Scabies (SCIN cases, without reshuffling the locked v1 split) + Fitzpatrick17k dark-skin
photos for TRAINING ONLY. Val/test stay SCIN-only.

.venv/bin/python ml/add_fitz.py select     # build list, print counts (no download)
.venv/bin/python ml/add_fitz.py download   # download + dedupe (exact md5 + perceptual hash vs SCIN)
"""
import ast
import hashlib
import io
import json
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

DATA = Path(__file__).resolve().parent / "data"
FITZ = DATA / "fitz"
FITZ_IMG = FITZ / "images"
CACHE = 512

FITZ_MAP = {
    "eczema": "Eczema", "dyshidrotic eczema": "Eczema",
    "allergic contact dermatitis": "Contact Dermatitis",
    "urticaria": "Urticaria",            # NOT 'urticaria pigmentosa' (different disease)
    "folliculitis": "Folliculitis",
    "psoriasis": "Psoriasis",            # NOT 'pustular psoriasis'
    "acne": "Acne", "acne vulgaris": "Acne",
    "pityriasis rosea": "Pityriasis Rosea",
    "scabies": "Scabies",
}


def pad_square(img):
    w, h = img.size
    s = max(w, h)
    sq = Image.new("RGB", (s, s))
    sq.paste(img, ((s - w) // 2, (s - h) // 2))
    return sq


def select():
    # --- class map v2 (adds Scabies) ---
    cm = json.loads((DATA / "class_map_v1.json").read_text())
    cm["raw_to_class"]["Scabies"] = "Scabies"
    cm["classes"] = sorted(set(cm["classes"]) | {"Scabies"})
    (DATA / "class_map.json").write_text(json.dumps(cm, indent=2))

    # --- SCIN scabies cases -> 60/20/20 split, existing v1 assignments untouched ---
    v1 = pd.read_csv(DATA / "cases_final_v1.csv", dtype={"case_id": str})
    lab = pd.read_csv(DATA / "labelled_cases.csv", dtype={"case_id": str})
    sc = lab[(lab.top_label == "Scabies") & (lab.top_weight >= cm["conf_cutoff"]) & ~lab.case_id.isin(v1.case_id)].copy()
    sc["label"] = "Scabies"
    rng = np.random.default_rng(7)
    sc = sc.sample(frac=1, random_state=7).reset_index(drop=True)
    n = len(sc)
    sc["split"] = ["test"] * round(n * 0.2) + ["val"] * round(n * 0.2) + ["train"] * (n - 2 * round(n * 0.2))
    v2 = pd.concat([v1, sc[v1.columns.intersection(sc.columns)]], ignore_index=True)
    v2.to_csv(DATA / "cases_final.csv", index=False)
    split = {s: sorted(v2.loc[v2.split == s, "case_id"]) for s in ("train", "val", "test")}
    blob = json.dumps(split, sort_keys=True).encode()
    (DATA / "split.json").write_bytes(blob)
    print(f"SCIN scabies cases added: {n} -> {sc.split.value_counts().to_dict()} | split v2 sha256 {hashlib.sha256(blob).hexdigest()[:16]}")

    # --- Fitzpatrick17k: dark skin (FST 4-6), mapped labels, drop wrongly labelled + exact duplicates ---
    f = pd.read_csv(FITZ / "fitzpatrick17k.csv")
    f = f[f.label.isin(FITZ_MAP) & (f.fitzpatrick_scale >= 4) & (f.qc != "3 Wrongly labelled")].copy()
    f = f.drop_duplicates("md5hash")
    f["app_label"] = f.label.map(FITZ_MAP)
    f[["md5hash", "fitzpatrick_scale", "label", "app_label", "url"]].to_csv(FITZ / "selected.csv", index=False)
    print(f"Fitzpatrick17k selected: {len(f)} photos")
    print(f.groupby("app_label").size().to_string())


def fetch(row):
    out = FITZ_IMG / f"{row.md5hash}.jpg"
    if out.exists():
        return str(out)
    try:
        req = urllib.request.Request(row.url, headers={"User-Agent": "Mozilla/5.0 (academic research dataset download)"})
        raw = urllib.request.urlopen(req, timeout=20).read()
        img = pad_square(Image.open(io.BytesIO(raw)).convert("RGB")).resize((CACHE, CACHE))
        img.save(out, quality=92)
        return str(out)
    except Exception:  # noqa: BLE001
        return None


def download():
    import imagehash
    FITZ_IMG.mkdir(parents=True, exist_ok=True)
    f = pd.read_csv(FITZ / "selected.csv")
    with ThreadPoolExecutor(16) as ex:
        f["file"] = list(ex.map(fetch, f.itertuples()))
    ok = f[f.file.notna()].copy()
    print(f"downloaded {len(ok)}/{len(f)} (dead links: {len(f) - len(ok)})")

    # perceptual-hash dedupe: within Fitzpatrick17k, and against every cached SCIN photo
    ok["phash"] = [imagehash.phash(Image.open(p)) for p in ok.file]
    scin = [imagehash.phash(Image.open(p)) for p in sorted((DATA / "images").glob("*.jpg"))]
    scin_arr = np.array([h.hash.flatten() for h in scin])
    def near_scin(h):
        return bool((np.count_nonzero(scin_arr != h.hash.flatten(), axis=1) <= 6).any())
    ok["dup_scin"] = [near_scin(h) for h in ok.phash]
    ok["phash_s"] = ok.phash.astype(str)
    before, ok_dup = len(ok), ok.dup_scin.sum()
    ok = ok[~ok.dup_scin].drop_duplicates("phash_s")
    print(f"removed {before - len(ok)} near-duplicates ({int(ok_dup)} matched SCIN photos)")
    ok[["md5hash", "fitzpatrick_scale", "label", "app_label", "file"]].to_csv(FITZ / "final.csv", index=False)
    print(f"FINAL Fitzpatrick17k training photos: {len(ok)}")
    print(ok.groupby("app_label").size().to_string())


if __name__ == "__main__":
    {"select": select, "download": download}[sys.argv[1]]()
