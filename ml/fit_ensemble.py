"""After embeddings + EfficientNet finish: train the embedding head, fit the fusion pool, OOD gate,
uncertain threshold, and evaluate ONCE on the frozen test split (ablation table by skin tone).

.venv/bin/python ml/fit_ensemble.py   -> ml/models/ensemble.joblib, ml/models/report.json
"""
import json
import sys
from pathlib import Path

import cv2
import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import recall_score, top_k_accuracy_score
from sklearn.model_selection import KFold
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
from app.features import featurize_scin_row  # noqa: E402
from app.fusion import LogPool, to_logp  # noqa: E402
from app.ood import OODGate, skin_ratio  # noqa: E402

import os
DATA = ROOT / "ml" / "data"
MODELS = Path(os.getenv("MODELS_DIR", ROOT / "ml" / "models"))
DARK_W = 3.0
rng = np.random.default_rng(0)


def load_embeddings():
    embs, idx = [], []
    for f in sorted((DATA / "embeddings").glob("*.npz")):
        z = np.load(f)
        embs.append(z["emb"]); idx.append(z["image_idx"])
    E, I = np.concatenate(embs), np.concatenate(idx)
    _, keep = np.unique(I, return_index=True)
    return dict(zip(I[keep].tolist(), E[keep]))


def case_mean(img_df, probs, cases):
    """Average image-level probabilities per case, ordered like `cases`."""
    p = pd.DataFrame(probs, index=img_df["case_id"].values).groupby(level=0).mean()
    return p.reindex(cases).to_numpy()


def metrics(p, y, dark):
    pred = p.argmax(1)
    labels = np.arange(p.shape[1])
    out = {"macro_recall": recall_score(y, pred, average="macro", labels=np.unique(y), zero_division=0),
           "top3": top_k_accuracy_score(y, p, k=3, labels=labels)}
    if dark.any():
        out["macro_recall_IV-VI"] = recall_score(y[dark], pred[dark], average="macro", labels=np.unique(y[dark]), zero_division=0)
        out["top3_IV-VI"] = top_k_accuracy_score(y[dark], p[dark], k=3, labels=labels)
    return {k: round(float(v), 3) for k, v in out.items()}


def main():
    global V1_TEST
    V1_TEST = json.loads((DATA / "split_v1.json").read_text())["test"] if (DATA / "split_v1.json").exists() else []
    SFX = os.getenv("DATA_SUFFIX", "")  # "_v1" re-fits the original SCIN-only version for comparison
    classes = json.loads((DATA / f"class_map{SFX}.json").read_text())["classes"]
    c2i = {c: i for i, c in enumerate(classes)}
    cases = pd.read_csv(DATA / f"cases_final{SFX}.csv", dtype={"case_id": str}).set_index("case_id")
    imgs = pd.read_csv(DATA / "image_index.csv", dtype={"case_id": str}).reset_index().rename(columns={"index": "image_idx"})
    emb = load_embeddings()
    imgs = imgs[imgs.case_id.isin(cases.index) & imgs.image_idx.isin(emb)].copy()
    imgs = imgs.join(cases[["label", "split", "fst_group"]], on="case_id")
    imgs["y"] = imgs.label.map(c2i)
    print("embedded images:", imgs.groupby("split").size().to_dict())

    # ---------- member 1: logistic regression on Derm Foundation embeddings ----------
    tr = imgs[imgs.split == "train"]
    X = lambda d: np.stack([emb[i] for i in d.image_idx])  # noqa: E731
    Xtr, ytr = X(tr), tr.y.to_numpy()
    sw = np.where(tr.fst_group == "IV-VI", DARK_W, 1.0)
    fz = DATA / "fitz" / "emb.npz"
    if fz.exists() and os.getenv("USE_FITZ", "1") == "1":  # Fitzpatrick17k dark-skin photos: TRAINING ONLY
        z = np.load(fz, allow_pickle=True)
        lab = pd.read_csv(DATA / "fitz" / "final.csv").set_index("md5hash").loc[z["md5hash"], "app_label"]
        keep = lab.isin(classes).to_numpy()  # v2b: drop Scabies photos
        lab, zemb = lab[keep], z["emb"][keep]
        Xtr = np.concatenate([Xtr, zemb]); ytr = np.concatenate([ytr, lab.map(c2i).to_numpy()])
        sw = np.concatenate([sw, np.ones(len(lab))])
        print(f"+ {len(lab)} Fitzpatrick17k training embeddings")
    scaler = StandardScaler().fit(Xtr)
    best = None
    va_img = imgs[imgs.split == "val"]
    for C in (0.01, 0.03, 0.1, 0.3):
        lr = LogisticRegression(C=C, max_iter=3000, class_weight="balanced").fit(scaler.transform(Xtr), ytr, sample_weight=sw)
        mr = recall_score(va_img.y, lr.predict(scaler.transform(X(va_img))), average="macro")
        print(f"  LR C={C}: val image macro-recall {mr:.3f}")
        if best is None or mr > best[0]:
            best = (mr, C, lr)
    lr = best[2]
    print("chosen C", best[1])

    # ---------- per-case member probabilities for val/test ----------
    xgb_sym = joblib.load(MODELS / "symptom_gb.joblib")
    eff = {s: np.load(MODELS / f"effnet_probs_{s}.npz") for s in ("val", "test")}
    out = {}
    for s in ("val", "test"):
        cid = cases.index[cases.split == s].tolist()
        d = imgs[imgs.split == s]
        p_lr = case_mean(d, lr.predict_proba(scaler.transform(X(d))), cid)
        e = eff[s]
        # keep each prediction attached to ITS photo (a plain slice misaligns rows when some photos are missing)
        e_df = pd.DataFrame({"image_idx": e["image_idx"], "row": np.arange(len(e["image_idx"]))}).merge(
            imgs[["image_idx", "case_id"]], on="image_idx")
        p_eff = case_mean(e_df, e["probs"][e_df["row"].to_numpy()], cid)
        feats = np.stack([featurize_scin_row(cases.loc[c]) for c in cid])
        p_sym = xgb_sym.predict_proba(feats)
        ok = ~np.isnan(p_lr).any(1) & ~np.isnan(p_eff).any(1)
        out[s] = dict(cid=np.array(cid)[ok], logps=np.stack([to_logp(p_lr[ok]), to_logp(p_eff[ok]), to_logp(p_sym[ok])]),
                      has_sym=feats[ok, -1] > 0, y=cases.loc[np.array(cid)[ok], "label"].map(c2i).to_numpy(),
                      dark=(cases.loc[np.array(cid)[ok], "fst_group"] == "IV-VI").to_numpy())

    v, t = out["val"], out["test"]
    pool = LogPool(3, len(classes), sym_idx=2).fit(v["logps"], v["y"], v["has_sym"])

    # honest val predictions via 5-fold cross-fitting of the pool (for the bootstrap + thresholds)
    oof = np.zeros((len(v["y"]), len(classes)))
    for a, b in KFold(5, shuffle=True, random_state=0).split(v["y"]):
        pp = LogPool(3, len(classes), 2).fit(v["logps"][:, a], v["y"][a], v["has_sym"][a])
        oof[b] = pp.predict_proba(v["logps"][:, b], v["has_sym"][b])

    # paired bootstrap on val: fused (OOF) vs best single member, macro-recall on FST IV-VI
    singles = {n: np.exp(v["logps"][i]) for i, n in enumerate(("derm_lr", "effnet", "symptoms"))}
    best_single = max(singles, key=lambda n: metrics(singles[n], v["y"], v["dark"]).get("macro_recall", 0))
    dk = np.where(v["dark"])[0]
    gains = []
    for _ in range(1000):
        s = rng.choice(dk, len(dk))
        f = recall_score(v["y"][s], oof[s].argmax(1), average="macro", zero_division=0)
        g = recall_score(v["y"][s], singles[best_single][s].argmax(1), average="macro", zero_division=0)
        gains.append(f - g)
    ci = np.percentile(gains, [2.5, 97.5]).round(3).tolist()
    print(f"bootstrap (val, FST IV-VI) fused - {best_single}: mean {np.mean(gains):.3f}, 95% CI {ci}")

    # uncertain threshold: lowest top-1 prob at which accepted val cases are >= TARGET correct
    TARGET = 0.65
    conf, correct = oof.max(1), oof.argmax(1) == v["y"]
    for th in (0.2, 0.3, 0.4, 0.5, 0.6):
        m = conf >= th
        print(f"  p>={th}: coverage {m.mean():.2f}, top-1 acc of shown {correct[m].mean() if m.any() else 0:.2f}")
    p_min = 0.0
    for th in np.arange(0.15, 0.9, 0.01):
        m = conf >= th
        if m.any() and correct[m].mean() >= TARGET:
            p_min = float(round(th, 2)); break
    print(f"uncertain threshold p_min={p_min} (val coverage {(conf >= p_min).mean():.2f})")

    # ---------- OOD gate ----------
    gate = OODGate().fit(np.stack([emb[i] for i in tr.image_idx]), tr.y.to_numpy(),
                         np.stack([emb[i] for i in va_img.image_idx]))
    ratios = []
    for i in va_img[va_img.fst_group == "IV-VI"].image_idx:
        f = DATA / "images" / f"{i}.jpg"
        if f.exists():
            ratios.append(skin_ratio(cv2.imread(str(f))))
    ratios = np.sort(ratios)
    min_skin = float(round(min(0.10, max(0.0, ratios[1] * 0.9)), 3)) if len(ratios) > 2 else 0.05  # capped: app crops are tight  # reject at most 1 dark-skin val photo
    print(f"OOD: mahalanobis thr {gate.thr:.1f} | min_skin {min_skin} (from {len(ratios)} FST IV-VI val photos)")

    # ---------- test: evaluate ONCE, ablation ----------
    fused = pool.predict_proba(t["logps"], t["has_sym"])
    img_only = pool.predict_proba(t["logps"], np.zeros_like(t["has_sym"]))
    report = {
        "classes": classes, "n_test_cases": int(len(t["y"])), "n_test_dark": int(t["dark"].sum()),
        "test": {
            "fused": metrics(fused, t["y"], t["dark"]),
            "image_only": metrics(img_only, t["y"], t["dark"]),
            "symptoms_only": metrics(np.exp(t["logps"][2]), t["y"], t["dark"]),
            "derm_lr_only": metrics(np.exp(t["logps"][0]), t["y"], t["dark"]),
            "effnet_only": metrics(np.exp(t["logps"][1]), t["y"], t["dark"]),
        },
        "val_oof_fused": metrics(oof, v["y"], v["dark"]),
        "val_oof_fused_no_scabies": (lambda m: metrics(oof[m], v["y"][m], v["dark"][m]))(np.array(classes)[v["y"]] != "Scabies"),
        "test_v1_cases_fused": (lambda m: metrics(fused[m], t["y"][m], t["dark"][m]))(np.isin(t["cid"], V1_TEST)),
        "val_bootstrap_fused_minus_best_single_IV-VI": {"best_single": best_single, "mean": round(float(np.mean(gains)), 3), "ci95": ci},
        "p_min": p_min, "ood_thr": gate.thr, "min_skin": min_skin, "lr_C": best[1],
    }
    print(json.dumps({k: report[k] for k in ("test", "val_oof_fused_no_scabies", "test_v1_cases_fused")}, indent=1))
    MODELS.mkdir(exist_ok=True)
    joblib.dump({"scaler": scaler, "lr": lr, "pool": pool.state(), "gate": gate, "p_min": p_min,
                 "min_skin": min_skin, "classes": classes}, MODELS / "ensemble.joblib")
    (MODELS / "report.json").write_text(json.dumps(report, indent=2))
    np.savez(MODELS / "test_preds.npz", cid=t["cid"], y=t["y"], fused=fused, img_only=img_only, classes=np.array(classes))
    print("saved ensemble.joblib + report.json")


if __name__ == "__main__":
    main()
