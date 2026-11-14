"""v3-FINAL: retrain the Derm-embedding head and the symptom model on 100% of the data (train + val + test).
Fusion weights, 'not confident' threshold, skin threshold and the OOD gate are KEPT from v3 (no held-out data
is left to re-tune them). EfficientNet is retrained separately with:
  MODELS_DIR=ml/models_v3_final TRAIN_SPLITS=train,val,test EPOCHS=12 python ml/v3_train_effnet.py
Reported performance = v3's held-out test results.

.venv/bin/python ml/v3_final.py   -> ml/models_v3_final/{ensemble.joblib, symptom_gb.joblib, report.json}
"""
import glob
import json
import shutil
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.utils.class_weight import compute_sample_weight

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
from app.features import featurize_scin_row  # noqa: E402
from app.fusion import AlignedProba  # noqa: E402

DATA, V3 = ROOT / "ml" / "data", ROOT / "ml" / "data" / "v3"
SRC, OUT = ROOT / "ml" / "models_v3", ROOT / "ml" / "models_v3_final"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    ens = joblib.load(SRC / "ensemble.joblib")
    classes = ens["classes"]; c2i = {c: i for i, c in enumerate(classes)}
    rep = json.loads((SRC / "report.json").read_text())

    df = pd.read_csv(V3 / "images.csv", dtype={"scin_case_id": str})
    emb = {}
    for f in glob.glob(str(DATA / "embeddings" / "*.npz")):
        z = np.load(f); emb.update({f"scin_{i}": e for i, e in zip(z["image_idx"].tolist(), z["emb"])})
    for f in glob.glob(str(V3 / "emb" / "*.npz")):
        z = np.load(f, allow_pickle=True); emb.update(dict(zip(z["key"].tolist(), z["emb"])))
    df = df[df.key.isin(emb)]
    X = np.stack([emb[k] for k in df.key]); y = df.label.map(c2i).to_numpy()
    sw = np.where((df.fst_group == "IV-VI") & (df.source == "SCIN"), 3.0, 1.0)
    scaler = StandardScaler().fit(X)
    lr = LogisticRegression(C=rep["lr_C"], max_iter=4000, class_weight="balanced").fit(scaler.transform(X), y, sample_weight=sw)
    print(f"Derm head trained on {len(df)} photos (100%)", flush=True)

    scin = pd.concat([pd.read_csv(DATA / "cases_final.csv", dtype={"case_id": str}),
                      pd.read_csv(DATA / "labelled_cases.csv", dtype={"case_id": str})]).drop_duplicates("case_id").set_index("case_id")
    sc = df[df.source == "SCIN"].drop_duplicates("scin_case_id")
    F = np.stack([featurize_scin_row(scin.loc[c]) for c in sc.scin_case_id]); ys = sc.label.map(c2i).to_numpy()
    rng = np.random.default_rng(0); drop = rng.random(len(F)) < 0.3
    F[drop, :-1] = np.nan; F[drop, -1] = 0.0
    gb = HistGradientBoostingClassifier(max_iter=300, max_depth=3, learning_rate=0.05, l2_regularization=1.0, random_state=0)
    gb.fit(F, ys, sample_weight=compute_sample_weight("balanced", ys))
    print(f"symptom model trained on {len(sc)} SCIN cases (100%)", flush=True)

    joblib.dump({**ens, "scaler": scaler, "lr": lr}, OUT / "ensemble.joblib")   # pool, thresholds, gate kept from v3
    joblib.dump(AlignedProba(gb, len(classes)), OUT / "symptom_gb.joblib")
    rep["note"] = "v3-final: retrained on 100% of data. Scores below are v3's held-out test results (no test data left)."
    (OUT / "report.json").write_text(json.dumps(rep, indent=2))
    shutil.copy(V3 / "split_v3.json", OUT / "split_v3_used_for_reported_scores.json")
    print("saved", OUT, flush=True)


if __name__ == "__main__":
    main()
