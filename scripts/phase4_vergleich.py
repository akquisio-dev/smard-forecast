"""Phase 4: Vergleichsdaten fuer die TypeScript-Fassung in smard-mcp.

Holt die aktuelle Vorhersage aller Orte (Forecast API, genau der Abruf, den smard-mcp macht)
und die meta.json der drei ICON-Modelle, rechnet mit den exportierten Betriebsmodellen die
Vorhersage nach sf/betrieb.py und speichert Eingabe und Ergebnis als eine JSON-Datei.
Der Test in smard-mcp rechnet dieselbe Eingabe nach und vergleicht.

Aufruf: scripts/als-dienst.sh scripts/phase4_vergleich.py <modellversion>
"""

import json
import sys
import urllib.parse
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sf.betrieb import QUANTILE, vorhersage  # noqa: E402
from sf.log import log  # noqa: E402
from sf.merkmale import lauf_merkmale  # noqa: E402
from sf.openmeteo import MODELL, _hole, variablen_fuer  # noqa: E402
from sf.orte import ROOT, lade_orte  # noqa: E402

QUELLEN = ("solar", "wind_onshore", "wind_offshore")
LAUF_MODELLE = ("dwd_icon_d2", "dwd_icon_eu", "dwd_icon")


def sekunden(zeit: pd.DatetimeIndex) -> np.ndarray:
    """Sekunden seit 1970; nicht asi8, dessen Einheit seit pandas 3 von der Aufloesung abhaengt."""
    return ((zeit - pd.Timestamp(0, tz="UTC")) / pd.Timedelta(seconds=1)).to_numpy(dtype="float64")


def lauf_start(laeufe, zeit: pd.DatetimeIndex) -> np.ndarray:
    """Startzeit des Laufs, der die Stunde abdeckt (D2, dann EU, dann global)."""
    aus = np.full(len(zeit), laeufe[-1]["init"], dtype="float64")
    gesetzt = np.zeros(len(zeit), dtype=bool)
    sek = sekunden(zeit)
    for lf in laeufe:
        neu = ~gesetzt & (sek <= lf["ende"])
        aus[neu] = lf["init"]
        gesetzt |= neu
    return aus


def main():
    version = sys.argv[1]
    mdir = ROOT / "data" / "modell" / version
    meta = json.loads((mdir / "modell.json").read_text())
    orte = lade_orte()
    variablen = variablen_fuer(["solar", "wind"])
    laeufe = []
    for m in LAUF_MODELLE:
        j = _hole(f"https://api.open-meteo.com/data/{m}/static/meta.json")
        laeufe.append({"model": m, "init": j["last_run_initialisation_time"],
                       "ende": j["data_end_time"]})
    q = urllib.parse.urlencode({
        "latitude": ",".join(str(o.lat) for o in orte),
        "longitude": ",".join(str(o.lon) for o in orte),
        "models": MODELL, "hourly": ",".join(variablen), "forecast_days": 8,
        "timezone": "GMT"})
    antwort = _hole(f"https://api.open-meteo.com/v1/forecast?{q}")
    teile = []
    for o, a in zip(orte, antwort):
        h = a["hourly"]
        df = pd.DataFrame({v: pd.array(h[v], dtype="Float32") for v in variablen})
        df.insert(0, "zeit", pd.to_datetime(h["time"], utc=True))
        df.insert(0, "ort", o.name)
        teile.append(df)
    roh = pd.concat(teile, ignore_index=True)

    erwartet = {}
    for quelle in QUELLEN:
        X, merk = lauf_merkmale(roh, quelle)
        voll = merk + ["vorlauf_tag"]
        assert voll == meta["quellen"][quelle]["merkmale"], quelle
        booster = {q: lgb.Booster(model_file=str(mdir / f"{quelle}_p{int(q * 100)}.txt"))
                   for q in QUANTILE}
        predict = {q: (lambda Xt, b=b: b.predict(Xt[voll].to_numpy(dtype="float64")))
                   for q, b in booster.items()}
        zeit = pd.DatetimeIndex(X.index)
        L = (sekunden(zeit) - lauf_start(laeufe, zeit)) / 3600
        cqr = {int(k): v for k, v in meta["quellen"][quelle]["cqr"].items()}
        nacht = (X.sonne_max <= 0).to_numpy() if quelle == "solar" else None
        p = vorhersage(predict, X[merk], L, cqr, nacht)
        erste = X[merk].iloc[30].to_numpy(dtype="float64")
        erwartet[quelle] = {
            "zeit": [f"{t:%Y-%m-%dT%H:%MZ}" for t in zeit],
            "vorlauf_h": L.round(4).tolist(),
            "p": np.round(p, 7).tolist(),
            "merkmale_zeile_30": [None if np.isnan(v) else float(v) for v in erste],
        }
        log(f"{quelle}: {len(zeit)} Stunden, p50 Mittel {p[:, 1].mean():.4f}")
    aus = ROOT / "data" / "phase4"
    aus.mkdir(parents=True, exist_ok=True)
    datei = aus / f"vergleich_{version}.json"
    datei.write_text(json.dumps({"modell": version, "laeufe": laeufe, "antwort": antwort,
                                 "erwartet": erwartet}, separators=(",", ":")))
    log(f"gespeichert: {datei} ({datei.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
