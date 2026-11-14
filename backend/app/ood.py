"""Not-skin / out-of-distribution gate.

1) skin_ratio (YCrCb) - LOOSE threshold, because fixed YCrCb rules under-detect very dark skin.
2) Mahalanobis distance of the Derm Foundation embedding to the nearest class centroid (PCA-64, shared covariance).
"""
import cv2
import numpy as np


def skin_ratio(bgr) -> float:
    ycc = cv2.cvtColor(cv2.resize(bgr, (256, 256)), cv2.COLOR_BGR2YCrCb)
    _, cr, cb = cv2.split(ycc)
    return float(((cr >= 133) & (cr <= 173) & (cb >= 77) & (cb <= 127)).mean())


class OODGate:
    def fit(self, emb_train, y_train, emb_val, pct=97.5, n_pc=64):
        from sklearn.covariance import LedoitWolf
        from sklearn.decomposition import PCA
        self.pca = PCA(n_pc, random_state=0).fit(emb_train)
        z = self.pca.transform(emb_train)
        classes = np.unique(y_train)
        self.mu = np.stack([z[y_train == c].mean(0) for c in classes])
        resid = z - self.mu[np.searchsorted(classes, y_train)]
        self.prec = LedoitWolf().fit(resid).precision_
        self.val_scores = self.score(emb_val)
        self.thr = float(np.percentile(self.val_scores, pct))
        return self

    def score(self, emb):
        z = self.pca.transform(np.atleast_2d(emb))
        d = z[:, None, :] - self.mu[None]
        return np.einsum("nkd,de,nke->nk", d, self.prec, d).min(1)

    def check(self, bgr, emb, min_skin):
        sr = skin_ratio(bgr)
        if sr < min_skin:
            return {"rejected": True, "reason": "NOT_SKIN", "skin_ratio": round(sr, 3), "ood_score": None}
        s = float(self.score(emb)[0])
        bad = s > self.thr
        return {"rejected": bad, "reason": "OUT_OF_DISTRIBUTION" if bad else None,
                "skin_ratio": round(sr, 3), "ood_score": round(s, 1)}


class KNNGate:
    """Out-of-distribution check v2: cosine distance from a photo's Derm Foundation embedding to its 10 nearest
    TRAINING rash photos (a 2,000-photo reference bank). Tested on 67 negative photos: separates non-skin from
    real rashes far better than the Mahalanobis gate (AUC 0.998 vs 0.705).
      distance > thr_refuse (99.9th pct of real val rashes) -> refused ("not a rash we can assess")
      distance > thr_flag   (99th pct)                      -> analysed, but marked unusual / not confident
    """

    def fit(self, emb_train, emb_val, bank_size=2000, k=10, seed=0):
        rng = np.random.default_rng(seed)
        idx = rng.choice(len(emb_train), min(bank_size, len(emb_train)), replace=False)
        self.bank = self._norm(emb_train[idx]).astype(np.float16)
        self.k = k
        self.val_scores = self.score(emb_val)
        self.thr_flag = float(np.percentile(self.val_scores, 99))
        self.thr_refuse = float(np.percentile(self.val_scores, 99.9))
        self.thr = self.thr_flag
        return self

    @staticmethod
    def _norm(X):
        X = np.atleast_2d(X).astype(np.float32)
        return X / np.linalg.norm(X, axis=1, keepdims=True)

    def score(self, emb):
        sims = self._norm(emb) @ self.bank.T.astype(np.float32)
        return 1 - np.sort(sims, axis=1)[:, -self.k:].mean(1)

    def check(self, bgr, emb, min_skin):
        sr = skin_ratio(bgr)
        if sr < min_skin:
            return {"rejected": True, "reason": "NOT_SKIN", "unusual": False, "skin_ratio": round(sr, 3), "ood_score": None}
        s = float(self.score(emb)[0])
        if s > self.thr_refuse:
            return {"rejected": True, "reason": "OUT_OF_DISTRIBUTION", "unusual": True, "skin_ratio": round(sr, 3), "ood_score": round(s, 4)}
        return {"rejected": False, "reason": None, "unusual": s > self.thr_flag, "skin_ratio": round(sr, 3), "ood_score": round(s, 4)}
