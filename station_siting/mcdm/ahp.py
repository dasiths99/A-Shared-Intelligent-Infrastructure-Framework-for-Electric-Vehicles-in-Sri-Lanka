"""AHP criteria weights (model 2.3) - principal eigenvector + consistency ratio."""

from __future__ import annotations

import numpy as np

CRIT = ["demand", "grid", "road", "land", "competition"]
RI = {3: 0.58, 4: 0.90, 5: 1.12, 6: 1.24, 7: 1.32}
# ⚠️ placeholder judgements until expert interviews (Saaty 1-9; value = how much more important row is than column)
DEFAULT_JUDGEMENTS = {"demand|grid": 2, "demand|road": 3, "demand|land": 4, "demand|competition": 3,
                      "grid|road": 2, "grid|land": 3, "grid|competition": 2,
                      "road|land": 2, "road|competition": 1, "land|competition": 0.5}


def ahp(judgements: dict[str, float], crit: list[str] = CRIT) -> dict:
    n = len(crit)
    A = np.ones((n, n))
    for key, v in judgements.items():
        a, b = key.split("|")
        i, j = crit.index(a), crit.index(b)
        if v <= 0:
            raise ValueError("judgements must be > 0")
        A[i, j], A[j, i] = v, 1 / v
    vals, vecs = np.linalg.eig(A)
    k = int(np.argmax(vals.real))
    w = np.abs(vecs[:, k].real)
    w = w / w.sum()
    ci = (vals.real[k] - n) / (n - 1)
    cr = ci / RI[n]
    return {"weights": dict(zip(crit, map(float, w))), "lambda_max": float(vals.real[k]), "CR": float(cr),
            "consistent": bool(cr < 0.10), "matrix": A.round(4).tolist()}
