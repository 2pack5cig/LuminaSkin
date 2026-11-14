"""Late fusion: weighted log-linear pool of member probabilities, two regimes (symptoms answered / skipped).

log p(y) = log_softmax( sum_m W[r,m] * log p_m(y) + B[r,y] )
Fit on the validation split only. W also acts as a temperature, so no separate calibration step.
"""
import numpy as np
from scipy.optimize import minimize
from scipy.special import log_softmax


class LogPool:
    def __init__(self, n_models: int, n_classes: int, sym_idx: int):
        self.M, self.C, self.S = n_models, n_classes, sym_idx
        self.p = None

    def _unpack(self, p):
        return p[: 2 * self.M].reshape(2, self.M), p[2 * self.M:].reshape(2, self.C)

    def _logits(self, p, logps, has_sym):
        W, B = self._unpack(p)
        r = (~has_sym).astype(int)
        lp = logps.copy()
        lp[self.S][~has_sym] = 0.0  # symptom term removed when skipped
        return np.einsum("nm,mnc->nc", W[r], lp) + B[r]

    def fit(self, logps, y, has_sym, l2=1e-2):
        # modality dropout: add every row again in the "skipped" regime
        logps = np.concatenate([logps, logps], axis=1)
        y = np.concatenate([y, y])
        has_sym = np.concatenate([has_sym, np.zeros_like(has_sym)])
        idx = np.arange(len(y))

        def nll(p):
            return -log_softmax(self._logits(p, logps, has_sym), axis=1)[idx, y].mean() + l2 * np.sum(p ** 2)

        x0 = np.concatenate([np.full(2 * self.M, 1.0 / self.M), np.zeros(2 * self.C)])
        self.p = minimize(nll, x0, method="L-BFGS-B").x
        return self

    def predict_proba(self, logps, has_sym):
        return np.exp(log_softmax(self._logits(self.p, logps, has_sym), axis=1))

    def contributions(self, logp_one, has_sym: bool, groups: dict):
        """logp_one: (M, C) for one case. groups e.g. {'image': [0, 1], 'symptoms': [2]}. Approximate shares."""
        if not has_sym:
            return None
        W, _ = self._unpack(self.p)
        top = int(self.predict_proba(logp_one[:, None, :], np.array([True]))[0].argmax())
        c = np.clip([W[0, m] * (logp_one[m, top] - logp_one[m].mean()) for m in range(self.M)], 0, None)
        g = {k: float(c[v].sum()) for k, v in groups.items()}
        tot = sum(g.values())
        return None if tot == 0 else {k: round(v / tot, 2) for k, v in g.items()}

    def state(self):
        return {"M": self.M, "C": self.C, "S": self.S, "p": self.p.tolist()}

    @classmethod
    def from_state(cls, s):
        obj = cls(s["M"], s["C"], s["S"])
        obj.p = np.array(s["p"])
        return obj


def to_logp(p):
    return np.log(np.clip(p, 1e-6, 1.0))


class AlignedProba:
    """Wraps a classifier so predict_proba always returns columns for the full class list (in order),
    even if some classes were missing from its training data (prob 0 + tiny smoothing)."""

    def __init__(self, clf, n_classes: int):
        self.clf, self.n = clf, n_classes

    def predict_proba(self, X):
        p = np.full((len(X), self.n), 1e-4)
        p[:, self.clf.classes_] = self.clf.predict_proba(X)
        return p / p.sum(1, keepdims=True)
