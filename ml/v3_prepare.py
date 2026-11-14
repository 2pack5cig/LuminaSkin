"""v3 data: SCIN + DermaCon-IN, 15 classes, option B split.

SCIN:        old v1 TEST cases stay test (fair v1-vs-v3 comparison); the rest re-split -> overall 65/15/20.
DermaCon-IN: 70/15/15 by PATIENT (Subject_ID), stratified by label x skin-tone group.
Output: ml/data/v3/images.csv (one row per photo), ml/data/v3/split_v3.json (+ SHA-256 printed).

.venv/bin/python ml/v3_prepare.py
"""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold

DATA = Path(__file__).resolve().parent / "data"
OUT = DATA / "v3"
SEED = 42


def fst_group(n):
    return "I-III" if n in (1, 2, 3) else "IV-VI" if n in (4, 5, 6) else "unknown"


def scin():
    v2 = pd.read_csv(DATA / "cases_final.csv", dtype={"case_id": str})          # v1 cases + 8 SCIN scabies cases
    lab = pd.read_csv(DATA / "labelled_cases.csv", dtype={"case_id": str})
    vit = lab[(lab.top_label == "Vitiligo") & (lab.top_weight >= 0.5) & ~lab.case_id.isin(v2.case_id)].copy()
    vit["label"], vit["split"] = "Vitiligo", "train"
    cases = pd.concat([v2, vit[v2.columns.intersection(vit.columns)]], ignore_index=True)
    v1_test = set(json.loads((DATA / "split_v1.json").read_text())["test"])
    rng = np.random.default_rng(SEED)
    split = []
    for _, r in cases.iterrows():
        if r.case_id in v1_test:
            split.append("test")
        elif r.split == "test":                     # the few new scabies test cases keep their place
            split.append("test")
        elif r.split == "val":                      # old val 20% -> 15% val + 5% train
            split.append("val" if rng.random() < 0.75 else "train")
        else:
            split.append(r.split if r.split in ("train", "val") else "train")
    cases["split"] = split
    if len(vit):                                     # 2 SCIN vitiligo cases: 1 val, 1 train (too few to test)
        cases.loc[cases.case_id == vit.case_id.iloc[0], "split"] = "val"

    idx = pd.read_csv(DATA / "image_index.csv", dtype={"case_id": str}).reset_index().rename(columns={"index": "image_idx"})
    img = idx.merge(cases[["case_id", "label", "split", "fst", "fst_group"]], on="case_id")
    num = img.fst.astype(str).str.extract(r"(\d)")[0].astype(float)
    return pd.DataFrame({
        "key": "scin_" + img.image_idx.astype(str), "source": "SCIN", "group": "scin_" + img.case_id,
        "case": "scin_" + img.case_id, "label": img.label, "split": img.split,
        "fst": num, "fst_group": img.fst_group, "monk": np.nan,
        "local": [str(DATA / "images" / f"{i}.jpg") for i in img.image_idx], "gcs_path": img.path,
        "scin_image_idx": img.image_idx, "scin_case_id": img.case_id,
    })


def dermacon():
    d = pd.read_csv(DATA / "dermacon" / "Skin_Metadata.csv")
    m = json.loads((DATA / "dermacon_map.json").read_text())["map"]
    raw2cls = {r: c for c, rs in m.items() for r in rs}
    d["label"] = d.Disease_label.map(raw2cls)
    d = d[d.label.notna() & d.Quality.str.startswith(("Yes", "The quality"))].copy()
    files = {p.name: str(p) for p in (DATA / "dermacon" / "images").rglob("*") if p.suffix.lower() in (".jpg", ".jpeg", ".png")}
    d["local"] = d.Image_name.map(files)
    d = d[d.local.notna()].copy()
    d["fst"] = d.Fitzpatrick.str.extract(r"(\d)")[0].astype(float)
    d["fst_group"] = d.fst.map(fst_group)
    d["monk"] = d.Monk_skin_tone.str.extract(r"(\d+)")[0].astype(float)
    # 70/15/15 by patient, stratified by label x skin group (a patient's photos never split up)
    strat = d.label + "|" + d.fst_group
    fold = np.empty(len(d), dtype=int)
    sgkf = StratifiedGroupKFold(n_splits=20, shuffle=True, random_state=SEED)   # 20 folds of 5%
    for k, (_, ix) in enumerate(sgkf.split(d, strat, groups=d.Subject_ID)):
        fold[ix] = k
    d["split"] = np.select([fold < 3, fold < 6], ["test", "val"], "train")      # 15% / 15% / 70%
    return pd.DataFrame({
        "key": "dcn_" + d.Image_name, "source": "DermaCon-IN", "group": "dcn_" + d.Subject_ID,
        "case": "dcn_" + d.Subject_ID + "|" + d.label, "label": d.label, "split": d.split,
        "fst": d.fst, "fst_group": d.fst_group, "monk": d.monk, "local": d.local, "gcs_path": None,
        "scin_image_idx": np.nan, "scin_case_id": None,
    })


def assert_no_leak(df):
    n = df.groupby("group")["split"].nunique()
    assert (n == 1).all(), f"patient in two splits: {n[n > 1].index[:5].tolist()}"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    df = pd.concat([scin(), dermacon()], ignore_index=True)
    assert_no_leak(df)
    df.to_csv(OUT / "images.csv", index=False)
    classes = sorted(df.label.unique())
    (OUT / "class_map_v3.json").write_text(json.dumps({"classes": classes}, indent=2))
    split = {s: sorted(df.loc[df.split == s, "group"].unique()) for s in ("train", "val", "test")}
    blob = json.dumps(split, sort_keys=True).encode()
    (OUT / "split_v3.json").write_bytes(blob)

    print(len(classes), "classes:", classes)
    print(pd.crosstab([df.source], df.split, margins=True).to_string())
    pct = df.groupby("split").size() / len(df) * 100
    print("photos overall %:", pct.round(1).to_dict())
    print(pd.crosstab(df.label, [df.split]).to_string())
    print("split_v3.json sha256:", hashlib.sha256(blob).hexdigest())


if __name__ == "__main__":
    main()
