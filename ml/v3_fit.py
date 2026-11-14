"""v3: Derm-embedding head + symptom model + fusion pool + thresholds + OOD gate, then evaluate ONCE on test.

.venv/bin/python ml/v3_fit.py   -> ml/models_v3/{ensemble.joblib, symptom_gb.joblib, report.json, test_preds.npz}
"""
import glob
import json
import os
import sys
from pathlib import Path

import cv2
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import recall_score, top_k_accuracy_score
from sklearn.model_selection import KFold
from sklearn.preprocessing import StandardScaler
from sklearn.utils.class_weight import compute_sample_weight

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
from app.features import featurize, featurize_scin_row  # noqa: E402
from app.fusion import AlignedProba, LogPool, to_logp  # noqa: E402
from app.ood import KNNGate, skin_ratio  # noqa: E402

DATA, V3 = ROOT / "ml" / "data", ROOT / "ml" / "data" / "v3"
MODELS = Path(os.getenv("MODELS_DIR", ROOT / "ml" / "models_v3"))
DARK_W, TARGET = 3.0, float(os.getenv("TARGET", 0.75))
rng = np.random.default_rng(0)


def embeddings():
    emb = {}
    for f in glob.glob(str(DATA / "embeddings" / "*.npz")):
        z = np.load(f)
        emb.update({f"scin_{i}": e for i, e in zip(z["image_idx"].tolist(), z["emb"])})
    for f in glob.glob(str(V3 / "emb" / "*.npz")):
        z = np.load(f, allow_pickle=True)
        emb.update(dict(zip(z["key"].tolist(), z["emb"])))
    return emb


def metrics(p, y, mask=None):
    if mask is not None:
        p, y = p[mask], y[mask]
    if len(y) == 0:
        return None
    labels = np.arange(p.shape[1])
    return {"n": int(len(y)),
            "top1": round(float((p.argmax(1) == y).mean()), 3),
            "top3": round(float(top_k_accuracy_score(y, p, k=3, labels=labels)), 3),
            "macro_recall": round(float(recall_score(y, p.argmax(1), average="macro", labels=np.unique(y), zero_division=0)), 3)}


def case_mean(rows, probs, cases):
    return pd.DataFrame(probs, index=rows.case.values).groupby(level=0).mean().reindex(cases).to_numpy()


def main():
    classes = json.loads((V3 / "class_map_v3.json").read_text())["classes"]
    c2i = {c: i for i, c in enumerate(classes)}
    K = len(classes)
    df = pd.read_csv(V3 / "images.csv", dtype={"scin_case_id": str})
    emb = embeddings()
    df = df[df.key.isin(emb)].copy()
    df["y"] = df.label.map(c2i)
    print("photos with embeddings by split:", df.groupby(["split", "source"]).size().unstack().to_dict(), flush=True)
    X = lambda d: np.stack([emb[k] for k in d.key])  # noqa: E731

    # ---------- 1. Derm Foundation embedding head ----------
    tr = df[df.split == "train"]
    sw = np.where((tr.fst_group == "IV-VI") & (tr.source == "SCIN"), DARK_W, 1.0)
    scaler = StandardScaler().fit(X(tr))
    Xtr = scaler.transform(X(tr))
    va_img = df[df.split == "val"]
    best = None
    for C in (0.003, 0.01, 0.03):
        lr = LogisticRegression(C=C, max_iter=4000, class_weight="balanced").fit(Xtr, tr.y, sample_weight=sw)
        mr = recall_score(va_img.y, lr.predict(scaler.transform(X(va_img))), average="macro")
        print(f"  LR C={C}: val photo macro-recall {mr:.3f}", flush=True)
        if best is None or mr > best[0]:
            best = (mr, C, lr)
    lr = best[2]

    # ---------- 2. symptom model (SCIN cases only: DermaCon-IN has no symptom answers) ----------
    scin_cases = pd.concat([pd.read_csv(DATA / "cases_final.csv", dtype={"case_id": str}),
                            pd.read_csv(DATA / "labelled_cases.csv", dtype={"case_id": str})]).drop_duplicates("case_id").set_index("case_id")
    case_tbl = df.drop_duplicates("case")[["case", "source", "label", "split", "fst", "fst_group", "monk", "scin_case_id"]].set_index("case")
    def feats(c):
        r = case_tbl.loc[c]
        return featurize_scin_row(scin_cases.loc[r.scin_case_id]) if r.source == "SCIN" else featurize({})
    s_tr = case_tbl[(case_tbl.split == "train") & (case_tbl.source == "SCIN")]
    Fs = np.stack([feats(c) for c in s_tr.index]); ys = s_tr.label.map(c2i).to_numpy()
    drop = rng.random(len(Fs)) < 0.3
    Fs[drop, :-1] = np.nan; Fs[drop, -1] = 0.0
    gb = HistGradientBoostingClassifier(max_iter=300, max_depth=3, learning_rate=0.05, l2_regularization=1.0, random_state=0)
    gb.fit(Fs, ys, sample_weight=compute_sample_weight("balanced", ys))
    sym = AlignedProba(gb, K)

    # ---------- 3. per-case member probabilities ----------
    effp = {}
    for s in ("val", "test"):
        z = np.load(MODELS / f"effnet_probs_{s}.npz", allow_pickle=True)
        effp.update(dict(zip(z["key"].tolist(), z["probs"])))
    out = {}
    for s in ("val", "test"):
        cases = case_tbl.index[case_tbl.split == s].tolist()
        d = df[df.split == s]
        p_lr = case_mean(d, lr.predict_proba(scaler.transform(X(d))), cases)
        de = d[d.key.isin(effp)]
        p_eff = case_mean(de, np.stack([effp[k] for k in de.key]), cases)
        F = np.stack([feats(c) for c in cases])
        p_sym = sym.predict_proba(F)
        ok = ~np.isnan(p_lr).any(1) & ~np.isnan(p_eff).any(1)
        cs = np.array(cases)[ok]
        out[s] = dict(case=cs, logps=np.stack([to_logp(p_lr[ok]), to_logp(p_eff[ok]), to_logp(p_sym[ok])]),
                      has_sym=F[ok, -1] > 0, y=case_tbl.loc[cs, "label"].map(c2i).to_numpy(),
                      source=case_tbl.loc[cs, "source"].to_numpy(), fst=case_tbl.loc[cs, "fst"].to_numpy(),
                      monk=case_tbl.loc[cs, "monk"].to_numpy(), fst_group=case_tbl.loc[cs, "fst_group"].to_numpy())
    v, t = out["val"], out["test"]

    # ---------- 4. fusion pool (val) + honest cross-fitted val predictions ----------
    pool = LogPool(3, K, sym_idx=2).fit(v["logps"], v["y"], v["has_sym"])
    oof = np.zeros((len(v["y"]), K))
    for a, b in KFold(5, shuffle=True, random_state=0).split(v["y"]):
        oof[b] = LogPool(3, K, 2).fit(v["logps"][:, a], v["y"][a], v["has_sym"][a]).predict_proba(v["logps"][:, b], v["has_sym"][b])
    conf, correct = oof.max(1), oof.argmax(1) == v["y"]
    for th in (0.3, 0.4, 0.5, 0.6, 0.7):
        msk = conf >= th
        print(f"  shown if top prob >= {th}: coverage {msk.mean():.2f}, top-1 correct when shown {correct[msk].mean():.2f}", flush=True)
    p_min = next((float(round(th, 2)) for th in np.arange(0.15, 0.9, 0.01)
                  if (conf >= th).any() and correct[conf >= th].mean() >= TARGET), 0.5)
    print(f"'not confident' threshold {p_min} (val coverage {(conf >= p_min).mean():.2f})", flush=True)

    # ---------- 5. OOD gate ----------
    gate = KNNGate().fit(X(tr), X(va_img))
    ratios = []
    for r in va_img[va_img.fst_group == "IV-VI"].itertuples():
        f = (DATA / "images" / f"{int(r.scin_image_idx)}.jpg") if r.source == "SCIN" else (V3 / "cache" / f"{r.key}.jpg")
        if Path(f).exists():
            ratios.append(skin_ratio(cv2.imread(str(f))))
    ratios = np.sort(ratios)
    min_skin = float(round(min(0.10, ratios[1] * 0.9), 3)) if len(ratios) > 2 else 0.05
    print(f"OOD thr {gate.thr:.1f} | min_skin {min_skin} ({len(ratios)} dark-skin val photos)", flush=True)

    # ---------- 6. TEST, evaluated once ----------
    fused = pool.predict_proba(t["logps"], t["has_sym"])
    img_only = pool.predict_proba(t["logps"], np.zeros_like(t["has_sym"]))
    y = t["y"]
    groups = {"all": None, "SCIN": t["source"] == "SCIN", "DermaCon-IN (India)": t["source"] == "DermaCon-IN",
              "FST I-III": np.isin(t["fst"], [1, 2, 3]), "FST IV": t["fst"] == 4, "FST V": t["fst"] == 5, "FST VI": t["fst"] == 6,
              "FST IV-VI": t["fst_group"] == "IV-VI"}
    for m in range(4, 10):
        groups[f"Monk {m}"] = t["monk"] == m
    report = {"classes": classes, "p_min": p_min, "min_skin": min_skin, "ood_thr": gate.thr, "lr_C": best[1],
              "test_fused": {g: metrics(fused, y, msk) for g, msk in groups.items()},
              "ablation_all": {"fused": metrics(fused, y), "image_only": metrics(img_only, y),
                               "symptoms_only": metrics(np.exp(t["logps"][2]), y),
                               "derm_lr_only": metrics(np.exp(t["logps"][0]), y), "effnet_only": metrics(np.exp(t["logps"][1]), y)},
              "per_class_recall": {c: (round(float((fused[y == i].argmax(1) == i).mean()), 3), int((y == i).sum()))
                                   for i, c in enumerate(classes) if (y == i).any()},
              "val_oof_fused": metrics(oof, v["y"])}
    # v1 vs v3 on the SAME old SCIN test cases (13 classes; v3 predictions of Scabies/Vitiligo count as wrong)
    v1 = np.load(ROOT / "ml" / "models_v1_scin" / "test_preds.npz", allow_pickle=True)
    v1_cls = [str(c) for c in v1["classes"]]
    v1_idx = {f"scin_{c}": i for i, c in enumerate(v1["cid"])}
    common = [i for i, c in enumerate(t["case"]) if c in v1_idx]
    yv1 = np.array([v1_cls.index(classes[y[i]]) for i in common])
    p3 = fused[common][:, [classes.index(c) for c in v1_cls]]          # v3 probs restricted to the 13 v1 classes
    p3_full_top1 = np.array([classes[j] for j in fused[common].argmax(1)])
    p1 = v1["fused"][[v1_idx[t["case"][i]] for i in common]]
    dark = t["fst_group"][common] == "IV-VI"
    report["v1_vs_v3_same_SCIN_test"] = {
        "n": len(common),
        "v1": {"all": metrics(p1, yv1), "IV-VI": metrics(p1, yv1, dark)},
        "v3": {"all": metrics(p3, yv1), "IV-VI": metrics(p3, yv1, dark),
               "top1_incl_new_classes": round(float((p3_full_top1 == np.array(v1_cls)[yv1]).mean()), 3)},
    }
    MODELS.mkdir(parents=True, exist_ok=True)
    joblib.dump({"scaler": scaler, "lr": lr, "pool": pool.state(), "gate": gate, "p_min": p_min, "min_skin": min_skin,
                 "classes": classes}, MODELS / "ensemble.joblib")
    joblib.dump(sym, MODELS / "symptom_gb.joblib")
    (MODELS / "report.json").write_text(json.dumps(report, indent=2))
    np.savez(MODELS / "test_preds.npz", case=t["case"], y=y, fused=fused, classes=np.array(classes))
    print(json.dumps({k: report[k] for k in ("test_fused", "ablation_all", "v1_vs_v3_same_SCIN_test")}, indent=1), flush=True)
    print("saved", MODELS, flush=True)


if __name__ == "__main__":
    main()
