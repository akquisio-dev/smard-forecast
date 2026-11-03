"""Phase 4: Prueft die Vorlauf-Interpolation an echten Einzellaeufen (Mai bis Oktober 2026).

Modelle wie im rollierenden Fold fuer Mai 2026 (Training bis 7 Tage vor dem 1. Mai), Kalibrierung
nur aus den rollierenden Monaten vor Mai. Fuer jeden geladenen Einzellauf (data/einzellaeufe/)
wird jede Stunde mit ihrem echten Vorlauf L (Stunden nach Laufbeginn) vorhergesagt:
  * interpoliert: x = (L - 3)/24, Mischung der Tage N und N+1 (so rechnet smard-mcp),
  * abgerundet:   Tag = floor(L/24) (die fruehere, falsche Fassung).
Verglichen werden MAE und Trefferquote p10..p90 je 6-Stunden-Band des Vorlaufs.

Aufruf: scripts/als-dienst.sh scripts/phase4_interpolation.py
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import phase2_abstimmung as A  # noqa: E402
import phase2_solar as P  # noqa: E402
import phase3_wind as W  # noqa: E402
from sf.betrieb import QUANTILE, vorhersage  # noqa: E402
from sf.log import log  # noqa: E402
from sf.merkmale import lauf_merkmale  # noqa: E402
from sf.orte import ROOT  # noqa: E402

PRUEF_MONAT = "2026-05"
PH = ROOT / "data" / "phase2"


def cqr_vor(quelle) -> dict:
    if quelle == "solar":
        e = pd.read_parquet(PH / "solar_rollierend_bester.parquet")
        e["s"] = np.maximum(e.p10 - e.a, e.a - e.p90)
    else:
        e = pd.read_parquet(PH / f"{quelle}_vorhersagen.parquet")
    e = e[(e.monat < PRUEF_MONAT) & (e.teil == "rollierend") if "teil" in e else e.monat < PRUEF_MONAT]
    return {int(n): float(np.quantile(g.s, min(1, 0.8 * (1 + 1 / len(g)))))
            for n, g in e.groupby("vorlauf_tag")}


def sekunden(zeit) -> np.ndarray:
    return ((pd.DatetimeIndex(zeit) - pd.Timestamp(0, tz="UTC")) / pd.Timedelta(seconds=1)).to_numpy()


def main():
    dateien = sorted((ROOT / "data" / "einzellaeufe").glob("*.parquet"))
    log(f"{len(dateien)} Einzellaeufe")
    erg = {"laeufe": [f.stem for f in dateien]}
    for quelle in ("solar", "wind_onshore", "wind_offshore"):
        d, merk = A.vorbereiten() if quelle == "solar" else W.vorbereiten(quelle)
        _, _, mod = A.fold(d, merk, PRUEF_MONAT, A.RASTER["A_start"])
        predict = {q: (lambda X, m=m: m.predict(X[merk])) for q, m in mod.items()}
        cqr = cqr_vor(quelle)
        ist = d[d.vorlauf_tag == 1][["a"]].droplevel("vorlauf")
        zeilen = []
        for f in dateien:
            lauf = pd.Timestamp(f.stem.replace("T", " ") + ":00", tz="UTC")
            roh = pd.read_parquet(f)
            X, m_ohne = lauf_merkmale(roh, quelle)
            L = (sekunden(X.index) - lauf.timestamp()) / 3600
            nacht = (X.sonne_max <= 0).to_numpy() if quelle == "solar" else None
            for art, runden in (("interpoliert", False), ("abgerundet", True)):
                p = vorhersage(predict, X[m_ohne], L, cqr, nacht, runden=runden)
                zeilen.append(pd.DataFrame({"zeit": X.index, "L": L, "art": art, "p10": p[:, 0],
                                            "p50": p[:, 1], "p90": p[:, 2], "lauf": f.stem}))
        e = pd.concat(zeilen).join(ist, on="zeit").dropna(subset=["a"])
        e = e[(e.L >= 24) & (e.L < 150)]
        if quelle == "solar":
            e = e[~((e.p90 == 0) & (e.a == 0))]  # Nachtstunden zaehlen nicht
        e["band"] = (np.floor(e.L / 6) * 6).astype(int)
        e["fehler"] = (e.a - e.p50).abs() * 100
        e["treffer"] = ((e.a >= e.p10) & (e.a <= e.p90)) * 100.0
        tab = e.groupby(["band", "art"])[["fehler", "treffer"]].mean().unstack("art").round(2)
        gesamt = e.groupby("art")[["fehler", "treffer"]].mean().round(2)
        log(f"{quelle}: {len(e) // 2} Stunden\n{gesamt.to_string()}\n{tab.to_string()}")
        erg[quelle] = {"gesamt": gesamt.to_dict(),
                       "je_band": {f"{b}": {f"{k[0]}_{k[1]}": v for k, v in r.items()}
                                   for b, r in tab.iterrows()}}
    aus = ROOT / "data" / "phase4"
    aus.mkdir(parents=True, exist_ok=True)
    (aus / "interpolation.json").write_text(json.dumps(erg, indent=1))
    log("fertig")


if __name__ == "__main__":
    main()
