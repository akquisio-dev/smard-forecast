"""Vorhersage im Betrieb: Vorlauf-Interpolation, Kalibrierung, Nachtmaske.

Referenz fuer die TypeScript-Fassung in smard-mcp (Vergleichstest in Phase 4).
"""

import numpy as np
import pandas as pd

QUANTILE = (0.1, 0.5, 0.9)


def tage_und_gewicht(L: np.ndarray, runden: bool = False):
    """Vorlauf L (Stunden ab Laufbeginn) -> unterer Vorlauftag N und Gewicht w fuer N+1.

    Interpolation: x = (L - 3) / 24, begrenzt auf 1..6; Tag N und N+1 werden mit 1-w und w
    gemischt. runden=True ist die fruehere (falsche) Fassung: N = floor(L/24), w = 0.
    """
    L = np.asarray(L, dtype="float64")
    if runden:
        n = np.clip(np.floor(L / 24), 1, 6)
        return n.astype(int), np.zeros_like(L)
    x = np.clip((L - 3) / 24, 1, 6)
    n = np.minimum(np.floor(x), 5)
    return n.astype(int), x - n


def je_tag(predict, X: pd.DataFrame, tag: int, cqr: dict) -> np.ndarray:
    """p10/p50/p90 fuer einen festen Vorlauftag: sortiert, begrenzt, kalibriert."""
    Xt = X.copy()
    Xt["vorlauf_tag"] = tag
    p = np.column_stack([predict[q](Xt) for q in QUANTILE])
    p = np.clip(np.sort(p, axis=1), 0, 1)
    k = cqr[tag]
    p[:, 0] = np.clip(p[:, 0] - k, 0, 1)
    p[:, 2] = np.clip(p[:, 2] + k, 0, 1)
    return p


def vorhersage(predict, X: pd.DataFrame, L: np.ndarray, cqr: dict, nacht=None,
               runden: bool = False) -> np.ndarray:
    """Auslastung p10/p50/p90 je Zeile von X (Merkmale ohne vorlauf_tag)."""
    n, w = tage_und_gewicht(L, runden)
    tage = sorted(set(n) | set(n[w > 0] + 1))
    cache = {t: je_tag(predict, X, t, cqr) for t in tage}
    aus = np.zeros((len(X), 3))
    for t in tage:
        unten = n == t
        aus[unten] += (1 - w[unten])[:, None] * cache[t][unten]
        oben = (n + 1 == t) & (w > 0)
        aus[oben] += w[oben][:, None] * cache[t][oben]
    aus = np.sort(aus, axis=1)
    if nacht is not None:
        aus[np.asarray(nacht)] = 0.0
    return aus
