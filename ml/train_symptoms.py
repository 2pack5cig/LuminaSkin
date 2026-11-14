"""Train the symptom-only XGBoost model with modality dropout.

.venv/bin/python ml/train_symptoms.py   ->  ml/models/symptom_gb.joblib
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import joblib
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import recall_score, top_k_accuracy_score
from sklearn.utils.class_weight import compute_sample_weight

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
from app.features import N_FEATURES, featurize_scin_row  # noqa: E402

import os
DATA = ROOT / "ml" / "data"
MODELS = Path(os.getenv("MODELS_DIR", ROOT / "ml" / "models"))
P_DROP, SEED = 0.3, 0


def load():
    df = pd.read_csv(DATA / "cases_final.csv", dtype={"case_id": str})
    classes = json.loads((DATA / "class_map.json").read_text())["classes"]
    X = np.stack([featurize_scin_row(r) for _, r in df.iterrows()])
    y = df["label"].map({c: i for i, c in enumerate(classes)}).to_numpy()
    return df, X, y, classes


def report(name, p, y, df_part, k=len):
    pred = p.argmax(1)
    out = {"macro_recall": recall_score(y, pred, average="macro", zero_division=0),
           "top3": top_k_accuracy_score(y, p, k=3, labels=np.arange(p.shape[1]))}
    dark = (df_part["fst_group"] == "IV-VI").to_numpy()
    if dark.any():
        out["macro_recall_IV-VI"] = recall_score(y[dark], pred[dark], average="macro", zero_division=0)
    print(name, {k_: round(v, 3) for k_, v in out.items()})


def main():
    df, X, y, classes = load()
    assert X.shape[1] == N_FEATURES
    tr, va = (df["split"] == "train").to_numpy(), (df["split"] == "val").to_numpy()
    print(f"answered rate: {np.nanmean(X[:, -1]):.2f}")

    rng = np.random.default_rng(SEED)
    Xtr, ytr = X[tr].copy(), y[tr]
    drop = rng.random(len(Xtr)) < P_DROP
    Xtr[drop, :-1] = np.nan
    Xtr[drop, -1] = 0.0

    # sklearn gradient boosting (handles NaN natively); replaces XGBoost, which segfaults next to torch+TF on macOS
    clf = HistGradientBoostingClassifier(max_iter=300, max_depth=3, learning_rate=0.05, l2_regularization=1.0,
                                         random_state=SEED)
    clf.fit(Xtr, ytr, sample_weight=compute_sample_weight("balanced", ytr))

    p = clf.predict_proba(X[va])
    report("val (symptoms as answered)", p, y[va], df[va])
    Xs = np.full_like(X[va], np.nan); Xs[:, -1] = 0
    report("val (all skipped -> ~prior)", clf.predict_proba(Xs), y[va], df[va])

    MODELS.mkdir(parents=True, exist_ok=True)
    joblib.dump(clf, MODELS / "symptom_gb.joblib")
    print("saved", MODELS / "symptom_gb.joblib")


if __name__ == "__main__":
    main()
