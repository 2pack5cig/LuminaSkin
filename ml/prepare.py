"""Lock the disease list and the case-level train/val/test split.

Run once:  .venv/bin/python ml/prepare.py
Writes ml/data/class_map.json, ml/data/split.json (+ printed SHA-256), ml/data/cases_final.csv
"""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold

DATA = Path(__file__).resolve().parent / "data"
CONF_CUTOFF = 0.5  # minimum weight of the top dermatologist label

# SCIN raw label -> app class. Chosen from label_counts.csv (enough photos, incl. FST IV-VI).
CLASS_MAP = {
    "Eczema": "Eczema",
    "Acute dermatitis, NOS": "Eczema",
    "Acute and chronic dermatitis": "Eczema",
    "Chronic dermatitis, NOS": "Eczema",
    "Allergic Contact Dermatitis": "Contact Dermatitis",
    "Irritant Contact Dermatitis": "Contact Dermatitis",
    "CD - Contact dermatitis": "Contact Dermatitis",
    "Urticaria": "Urticaria",
    "Insect Bite": "Insect Bite",
    "Folliculitis": "Folliculitis",
    "Psoriasis": "Psoriasis",
    "Tinea": "Tinea",
    "Impetigo": "Impetigo",
    "Herpes Zoster": "Herpes Zoster",
    "Acne": "Acne",
    "Herpes Simplex": "Herpes Simplex",
    "Pityriasis rosea": "Pityriasis Rosea",
    "Tinea Versicolor": "Tinea Versicolor",
}


def assert_no_leak(df):
    n = df.groupby("case_id")["split"].nunique()
    assert (n == 1).all(), f"case in two splits: {n[n > 1].index[:5].tolist()}"


def main():
    df = pd.read_csv(DATA / "labelled_cases.csv", dtype={"case_id": str})
    df["label"] = df["top_label"].map(CLASS_MAP)
    df = df[df["label"].notna() & (df["top_weight"] >= CONF_CUTOFF)].reset_index(drop=True)

    strat = df["label"] + "|" + df["fst_group"]
    sgkf = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=42)
    fold = np.empty(len(df), dtype=int)
    for k, (_, idx) in enumerate(sgkf.split(df, strat, groups=df["case_id"])):
        fold[idx] = k
    df["split"] = np.select([fold == 0, fold == 1], ["test", "val"], "train")
    assert_no_leak(df)

    classes = sorted(df["label"].unique())
    (DATA / "class_map.json").write_text(json.dumps({"classes": classes, "raw_to_class": CLASS_MAP,
                                                     "conf_cutoff": CONF_CUTOFF}, indent=2))
    split = {s: sorted(df.loc[df["split"] == s, "case_id"]) for s in ("train", "val", "test")}
    blob = json.dumps(split, sort_keys=True).encode()
    (DATA / "split.json").write_bytes(blob)
    df.to_csv(DATA / "cases_final.csv", index=False)

    print(pd.crosstab([df["label"]], [df["split"], df["fst_group"]]))
    print({s: len(v) for s, v in split.items()})
    print("split.json sha256:", hashlib.sha256(blob).hexdigest())


if __name__ == "__main__":
    main()
