"""Kennzahlen fuer den Vergleich mit veroeffentlichten Studien (Bericht, Kapitel Forschungsstand).

Studien geben meist den RMSE in % der Nennleistung an, das Projekt den MAE. Dieses Skript
rechnet aus der rollierenden Pruefung (data/betrieb/<quelle>_rollierend.parquet, p50 vor der
Kalibrierung; die CQR veraendert den Median nicht) RMSE und MAE je Vorlauftag, fuer Solar nur
Stunden mit Erzeugung, und dieselben Werte fuer die Day-Ahead-Prognose der Netzbetreiber.
Ausgabe: data/betrieb/literaturvergleich.json
Aufruf: scripts/als-dienst.sh scripts/literaturvergleich.py
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sf.log import log  # noqa: E402
from sf.orte import ROOT  # noqa: E402

ERG = {}
for q in ("solar", "wind_onshore", "wind_offshore"):
    d = pd.read_parquet(ROOT / "data" / "betrieb" / f"{q}_rollierend.parquet").dropna(subset=["a", "p50"])
    if q == "solar":
        d = d[d.a > 0.001]  # nur Stunden mit Erzeugung, wie in den Studien
    ERG[q] = {"monate": f"{d.monat.min()} bis {d.monat.max()}"}
    for n in range(1, 7):
        g = d[d.vorlauf_tag == n]
        e = g.a - g.p50
        ERG[q][f"tag{n}"] = {"rmse": float(np.sqrt((e ** 2).mean()) * 100),
                             "mae": float(e.abs().mean() * 100), "stunden": int(len(g))}
    nb = d[d.vorlauf_tag == 1].dropna(subset=["a_nb"])
    e = nb.a - nb.a_nb
    ERG[q]["nb"] = {"rmse": float(np.sqrt((e ** 2).mean()) * 100), "mae": float(e.abs().mean() * 100),
                    "stunden": int(len(nb))}
    log(f"{q}: Tag 1 RMSE {ERG[q]['tag1']['rmse']:.2f} MAE {ERG[q]['tag1']['mae']:.2f}, "
        f"Tag 6 RMSE {ERG[q]['tag6']['rmse']:.2f}, NB RMSE {ERG[q]['nb']['rmse']:.2f} MAE {ERG[q]['nb']['mae']:.2f}")
(ROOT / "data" / "betrieb" / "literaturvergleich.json").write_text(json.dumps(ERG, indent=1))
