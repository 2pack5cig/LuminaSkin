"""Train EfficientNet-B0 on the Mac's GPU (MPS). Source model for the Grad-CAM heatmap + 2nd image voter.

.venv/bin/python ml/train_effnet.py            -> ml/models/effnet_b0.pt, ml/models/effnet_probs_{val,test}.npz
"""
import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
import timm
import torch
import torch.nn as nn
import torchvision.transforms as T
from PIL import Image
from sklearn.metrics import recall_score
from torch.utils.data import DataLoader, Dataset, WeightedRandomSampler

ROOT = Path(__file__).resolve().parent
DATA, IMG = ROOT / "data", ROOT / "data" / "images"
MODELS = Path(os.getenv("MODELS_DIR", ROOT / "models"))
SIZE, CACHE_SIZE, EPOCHS, BS = 320, 384, 15, 32
MEAN, STD = (0.485, 0.456, 0.406), (0.229, 0.224, 0.225)
logging.getLogger("urllib3.connectionpool").setLevel(logging.ERROR)


def pad_square(img):
    w, h = img.size
    s = max(w, h)
    sq = Image.new("RGB", (s, s))
    sq.paste(img, ((s - w) // 2, (s - h) // 2))
    return sq


def table():
    idx = pd.read_csv(DATA / "image_index.csv", dtype={"case_id": str})
    fin = pd.read_csv(DATA / f"cases_final{os.getenv('DATA_SUFFIX', '')}.csv", dtype={"case_id": str})[["case_id", "label", "split", "fst_group"]]
    return idx.reset_index().rename(columns={"index": "image_idx"}).merge(fin, on="case_id")


def download(df):
    """Fetch each photo once, pad to square, store at 384 px (fast to decode every epoch)."""
    from google.cloud import storage
    bucket = storage.Client.create_anonymous_client().bucket("dx-scin-public-data")
    IMG.mkdir(parents=True, exist_ok=True)

    def one(row):
        f = IMG / f"{row.image_idx}.jpg"
        if not f.exists():
            try:
                raw = bucket.blob(row.path).download_as_bytes()
                img = pad_square(Image.open(__import__("io").BytesIO(raw)).convert("RGB"))
                img.resize((CACHE_SIZE, CACHE_SIZE)).save(f, quality=92)
            except Exception:  # noqa: BLE001
                return None
        return str(f)

    t = time.time()
    with ThreadPoolExecutor(32) as ex:
        df["file"] = list(ex.map(one, df.itertuples()))
    print(f"photos ready: {df.file.notna().sum()}/{len(df)} in {time.time()-t:.0f}s", flush=True)
    return df[df.file.notna()].reset_index(drop=True)


train_tf = T.Compose([T.RandomResizedCrop(SIZE, scale=(0.5, 1.0)), T.RandomHorizontalFlip(), T.RandomVerticalFlip(),
                      T.RandomRotation(20), T.ColorJitter(0.25, 0.25, 0.15, 0.02), T.ToTensor(), T.Normalize(MEAN, STD)])
eval_tf = T.Compose([T.Resize((SIZE, SIZE)), T.ToTensor(), T.Normalize(MEAN, STD)])


class DS(Dataset):
    def __init__(self, df, tf, c2i):
        self.df, self.tf, self.c2i = df.reset_index(drop=True), tf, c2i

    def __len__(self):
        return len(self.df)

    def __getitem__(self, i):
        r = self.df.iloc[i]
        return self.tf(Image.open(r.file).convert("RGB")), self.c2i[r.label]


def predict(model, df, c2i, dev, tta=True):
    model.eval()
    out = []
    with torch.no_grad():
        for x, _ in DataLoader(DS(df, eval_tf, c2i), batch_size=64, num_workers=4):
            x = x.to(dev)
            p = model(x).softmax(1)
            if tta:
                p = (p + model(torch.flip(x, [3])).softmax(1)) / 2
            out.append(p.cpu())
    return torch.cat(out).numpy()


def main():
    classes = json.loads((DATA / f"class_map{os.getenv('DATA_SUFFIX', '')}.json").read_text())["classes"]
    c2i = {c: i for i, c in enumerate(classes)}
    df = download(table())
    fz = DATA / "fitz" / "final.csv"
    if fz.exists():  # Fitzpatrick17k dark-skin photos: TRAINING ONLY
        f = pd.read_csv(fz)
        f = f[f.app_label.isin(classes)]  # e.g. v2b drops Scabies (handled by the clinical rule instead)
        df = pd.concat([df, pd.DataFrame({"image_idx": -1, "file": f.file, "label": f.app_label,
                                          "split": "train", "fst_group": "IV-VI", "case_id": "fitz_" + f.md5hash})],
                       ignore_index=True)
        print(f"+ {len(f)} Fitzpatrick17k training photos", flush=True)
    tr, va, te = (df[df.split == s] for s in ("train", "val", "test"))

    is_fitz = tr.case_id.astype(str).str.startswith("fitz_")
    # balance classes; SCIN dark-skin photos x3; Fitzpatrick17k photos x1 (already all dark skin, different photo style)
    w = (1.0 / tr.label.map(tr.label.value_counts())) * np.where((tr.fst_group == "IV-VI") & ~is_fitz, 3.0, 1.0)
    sampler = WeightedRandomSampler(torch.tensor(w.values, dtype=torch.double), num_samples=len(tr), replacement=True)
    dl_tr = DataLoader(DS(tr, train_tf, c2i), batch_size=BS, sampler=sampler, num_workers=4,
                       drop_last=True, persistent_workers=True)

    dev = "mps" if torch.backends.mps.is_available() else "cpu"
    model = timm.create_model("efficientnet_b0", pretrained=True, num_classes=len(classes)).to(dev)
    opt = torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=1e-3, total_steps=EPOCHS * len(dl_tr), pct_start=0.15)
    lossf = nn.CrossEntropyLoss(label_smoothing=0.1)
    MODELS.mkdir(parents=True, exist_ok=True)
    yv, dark = va.label.map(c2i).values, (va.fst_group == "IV-VI").values

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
        p = predict(model, va, c2i, dev, tta=False)
        mr = recall_score(yv, p.argmax(1), average="macro", zero_division=0)
        mrd = recall_score(yv[dark], p[dark].argmax(1), average="macro", zero_division=0)
        dt = time.time() - t
        print(f"epoch {ep+1}/{EPOCHS}: {dt:.0f}s | val macro-recall {mr:.3f} (FST IV-VI {mrd:.3f}) | "
              f"~{dt*(EPOCHS-ep-1)/60:.0f} min left", flush=True)
        if mr > best:
            best = mr
            torch.save({"state_dict": model.state_dict(), "classes": classes, "size": SIZE}, MODELS / "effnet_b0.pt")

    model.load_state_dict(torch.load(MODELS / "effnet_b0.pt")["state_dict"])
    for name, d in (("val", va), ("test", te)):
        np.savez(MODELS / f"effnet_probs_{name}.npz", probs=predict(model, d, c2i, dev), image_idx=d.image_idx.values)
    print(f"DONE best val macro-recall {best:.3f}", flush=True)


if __name__ == "__main__":
    os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
    main()
