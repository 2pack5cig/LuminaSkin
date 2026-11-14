"""v3 EfficientNet-B0 on SCIN + DermaCon-IN (15 classes), Mac GPU (MPS).

.venv/bin/python ml/v3_train_effnet.py   -> ml/models_v3/effnet_b0.pt + effnet_probs_{val,test}.npz (keyed by photo key)
"""
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import timm
import torch
import torch.nn as nn
from sklearn.metrics import recall_score
from torch.utils.data import DataLoader, WeightedRandomSampler

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from train_effnet import DS, SIZE, eval_tf, predict, train_tf  # noqa: E402

V3 = ROOT / "data" / "v3"
MODELS = Path(os.getenv("MODELS_DIR", ROOT / "models_v3"))
EPOCHS, BS = int(os.getenv("EPOCHS", 15)), 32
SPLITS_TRAIN = os.getenv("TRAIN_SPLITS", "train").split(",")   # final: "train,val" or "train,val,test"


def photo_file(r):
    if r.source == "SCIN":
        f = ROOT / "data" / "images" / f"{int(r.scin_image_idx)}.jpg"
        if f.exists():
            return str(f)
    f = V3 / "cache" / f"{r.key}.jpg"
    return str(f) if f.exists() else None


def main():
    classes = json.loads((V3 / "class_map_v3.json").read_text())["classes"]
    c2i = {c: i for i, c in enumerate(classes)}
    df = pd.read_csv(V3 / "images.csv")
    df["file"] = [photo_file(r) for r in df.itertuples()]
    print("photos with files:", df.file.notna().sum(), "/", len(df), flush=True)
    df = df[df.file.notna()].reset_index(drop=True)
    tr = df[df.split.isin(SPLITS_TRAIN)]
    va, te = df[df.split == "val"], df[df.split == "test"]

    # balance classes; SCIN dark-skin photos x3 (DermaCon-IN is already mostly brown/dark skin)
    w = (1.0 / tr.label.map(tr.label.value_counts())) * np.where((tr.fst_group == "IV-VI") & (tr.source == "SCIN"), 3.0, 1.0)
    sampler = WeightedRandomSampler(torch.tensor(w.values, dtype=torch.double), num_samples=len(tr), replacement=True)
    dl_tr = DataLoader(DS(tr, train_tf, c2i), batch_size=BS, sampler=sampler, num_workers=4, drop_last=True, persistent_workers=True)

    dev = "mps" if torch.backends.mps.is_available() else "cpu"
    model = timm.create_model("efficientnet_b0", pretrained=True, num_classes=len(classes)).to(dev)
    opt = torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=1e-3, total_steps=EPOCHS * len(dl_tr), pct_start=0.15)
    lossf = nn.CrossEntropyLoss(label_smoothing=0.1)
    MODELS.mkdir(parents=True, exist_ok=True)
    yv, dark = va.label.map(c2i).values, (va.fst_group == "IV-VI").values
    use_val = "val" not in SPLITS_TRAIN

    best = -1.0
    for ep in range(EPOCHS):
        t = time.time()
        model.train()
        for x, y in dl_tr:
            x, y = x.to(dev), y.to(dev)
            opt.zero_grad()
            loss = lossf(model(x), y)
            loss.backward()
            opt.step()
            sched.step()
        if use_val:
            p = predict(model, va, c2i, dev, tta=False)
            mr = recall_score(yv, p.argmax(1), average="macro", zero_division=0)
            mrd = recall_score(yv[dark], p[dark].argmax(1), average="macro", zero_division=0)
        else:
            mr = mrd = float(ep)  # final training: no validation left -> keep the last round
        print(f"epoch {ep+1}/{EPOCHS}: {time.time()-t:.0f}s | val macro-recall {mr:.3f} (IV-VI {mrd:.3f})", flush=True)
        if mr > best:
            best = mr
            torch.save({"state_dict": model.state_dict(), "classes": classes, "size": SIZE, "best_epoch": ep + 1},
                       MODELS / "effnet_b0.pt")

    model.load_state_dict(torch.load(MODELS / "effnet_b0.pt")["state_dict"])
    for name, d in (("val", va), ("test", te)):
        if len(d):
            np.savez(MODELS / f"effnet_probs_{name}.npz", probs=predict(model, d, c2i, dev), key=d.key.values)
    print(f"DONE best {best:.3f}", flush=True)


if __name__ == "__main__":
    os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
    main()
