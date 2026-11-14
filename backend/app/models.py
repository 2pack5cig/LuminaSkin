"""Loads all trained models once and runs the real pipeline for one photo."""
import base64
import io
import os
from pathlib import Path

import cv2
import joblib
import numpy as np

from .features import featurize
from .fusion import LogPool, to_logp

ROOT = Path(__file__).resolve().parent.parent.parent
MODELS = Path(os.getenv("MODELS_DIR", ROOT / "ml" / "models"))
REQUIRED = ["ensemble.joblib", "effnet_b0.pt", "symptom_gb.joblib"]
MEAN, STD = np.array([0.485, 0.456, 0.406]), np.array([0.229, 0.224, 0.225])


def available() -> bool:
    return all((MODELS / f).exists() for f in REQUIRED)


class Pipeline:
    def __init__(self):
        import tensorflow as tf
        import timm
        import torch
        from dotenv import load_dotenv
        from huggingface_hub import snapshot_download
        load_dotenv(ROOT / "backend" / ".env")

        self.tf, self.torch = tf, torch
        ens = joblib.load(MODELS / "ensemble.joblib")
        self.classes, self.scaler, self.lr = ens["classes"], ens["scaler"], ens["lr"]
        self.pool, self.gate = LogPool.from_state(ens["pool"]), ens["gate"]
        self.p_min, self.min_skin = ens["p_min"], ens["min_skin"]

        path = snapshot_download("google/derm-foundation", token=os.getenv("HF_TOKEN") or None)
        with tf.device("/CPU:0"):
            self.derm = tf.saved_model.load(path).signatures["serving_default"]

        ck = torch.load(MODELS / "effnet_b0.pt", map_location="cpu")
        self.size = ck["size"]
        self.dev = "mps" if torch.backends.mps.is_available() else "cpu"
        self.eff = timm.create_model("efficientnet_b0", pretrained=False, num_classes=len(self.classes))
        self.eff.load_state_dict(ck["state_dict"])
        self.eff.eval().to(self.dev)

        self.sym = joblib.load(MODELS / "symptom_gb.joblib")

    # ---------- members ----------
    def _derm_embedding(self, rgb):
        from PIL import Image
        buf = io.BytesIO()
        Image.fromarray(rgb).resize((448, 448)).save(buf, format="PNG")
        tf = self.tf
        ex = tf.train.Example(features=tf.train.Features(feature={
            "image/encoded": tf.train.Feature(bytes_list=tf.train.BytesList(value=[buf.getvalue()]))
        })).SerializeToString()
        with tf.device("/CPU:0"):
            return self.derm(inputs=tf.constant([ex]))["embedding"].numpy().reshape(1, -1)

    def _eff_input(self, rgb):
        x = cv2.resize(rgb, (self.size, self.size)).astype(np.float32) / 255.0
        x = (x - MEAN) / STD
        return self.torch.tensor(x.transpose(2, 0, 1), dtype=self.torch.float32)[None]

    def _eff_probs(self, x):
        with self.torch.no_grad():
            x = x.to(self.dev)
            p = self.eff(x).softmax(1) + self.eff(self.torch.flip(x, [3])).softmax(1)
        return (p / 2).cpu().numpy()

    def _heatmap(self, x, rgb, cls):
        from pytorch_grad_cam import GradCAMPlusPlus
        from pytorch_grad_cam.utils.model_targets import ClassifierOutputTarget
        model = self.eff.to("cpu")  # grad-cam hooks are most reliable on CPU
        try:
            with GradCAMPlusPlus(model=model, target_layers=[model.conv_head]) as cam:
                g = cam(input_tensor=x, targets=[ClassifierOutputTarget(cls)])[0]
        finally:
            self.eff.to(self.dev)
        g = cv2.resize(g, (rgb.shape[1], rgb.shape[0]))
        color = cv2.applyColorMap(np.uint8(255 * g), cv2.COLORMAP_JET)
        rgba = cv2.cvtColor(color, cv2.COLOR_BGR2BGRA)
        rgba[..., 3] = np.uint8(255 * np.clip(g * 1.2, 0, 1))  # transparent where the model didn't look
        ok, png = cv2.imencode(".png", rgba)
        return base64.b64encode(png.tobytes()).decode() if ok else None

    # ---------- full pipeline ----------
    def run(self, bgr, symptoms: dict) -> dict:
        return self.run_multi([bgr], symptoms)

    def run_multi(self, bgrs: list, symptoms: dict) -> dict:
        """Several photos of the same rash (close-up first). Probabilities are averaged per model, the same way
        test cases with several photos were scored. Heatmap is made for the first usable photo (the close-up)."""
        kept, oods = [], []
        for bgr in bgrs:
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            emb = self._derm_embedding(rgb)
            ood = self.gate.check(bgr, emb, self.min_skin)
            oods.append(ood)
            if not ood["rejected"]:
                kept.append((rgb, emb))
        if not kept:
            return {"ood": oods[0], "top3": None, "uncertain": False, "contributions": None,
                    "symptoms_used": False, "heatmap_png_b64": None, "photos_used": 0}

        p_lr = np.mean([self.lr.predict_proba(self.scaler.transform(e))[0] for _, e in kept], axis=0)[None]
        xs = [self._eff_input(rgb) for rgb, _ in kept]
        p_eff = np.mean([self._eff_probs(x)[0] for x in xs], axis=0)[None]
        feats = featurize(symptoms)[None]
        has_sym = bool(feats[0, -1] > 0)
        p_sym = self.sym.predict_proba(feats)
        logps = np.stack([to_logp(p_lr), to_logp(p_eff), to_logp(p_sym)])
        p = self.pool.predict_proba(logps, np.array([has_sym]))[0]

        order = np.argsort(p)[::-1][:3]
        top3 = [{"label": self.classes[i], "prob": round(float(p[i]), 3)} for i in order]
        return {
            "ood": {"rejected": False, "reason": None, "photos_rejected": len(bgrs) - len(kept)},
            "top3": top3,
            "uncertain": bool(p[order[0]] < self.p_min),
            "contributions": self.pool.contributions(logps[:, 0, :], has_sym, {"image": [0, 1], "symptoms": [2]}),
            "symptoms_used": has_sym,
            "heatmap_png_b64": self._heatmap(xs[0], kept[0][0], int(order[0])),
            "heatmap_photo": next(i for i, o in enumerate(oods) if not o["rejected"]),
            "photos_used": len(kept),
        }
