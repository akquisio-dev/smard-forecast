"""Phase 4: Einzellaeufe aus der Single Runs API laden (Pruefung der Vorlauf-Interpolation).

Ein Lauf alle 15 Tage von 2026-05-01 bis gestern, abwechselnd 00 und 12 UTC (nur diese
ICON-global-Laeufe reichen 180 h weit). Die Single Runs API rechnet icon_seamless je Ort erst bei
der Anfrage zusammen (rund 30 s je Ort; 40 Orte in einem Abruf liefen ueber jede Zeitgrenze).
Deshalb ein Abruf je Ort, 4 gleichzeitig, mit 10 Minuten Zeitgrenze.
Gespeichert als data/einzellaeufe/<lauf>.parquet (lange Form: ort, zeit UTC, Variablen).
Fortsetzbar; Abrufgrenzen ueber dieselbe Buchfuehrung wie der Download.

Aufruf: scripts/als-dienst.sh scripts/phase4_einzellaeufe.py
"""

import datetime as dt
import json
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import download as D  # noqa: E402
from sf.log import log  # noqa: E402
from sf.openmeteo import MODELL, USER_AGENT, gewicht, variablen_fuer  # noqa: E402
from sf.orte import ROOT, lade_orte  # noqa: E402

URL = "https://single-runs-api.open-meteo.com/v1/forecast"
ZIEL = ROOT / "data" / "einzellaeufe"
START = dt.date(2026, 5, 1)


def laeufe():
    tag = START
    bis = dt.date.today() - dt.timedelta(days=1)
    while tag <= bis:
        stunde = 0 if tag.toordinal() % 2 == 0 else 12
        yield dt.datetime(tag.year, tag.month, tag.day, stunde)
        tag += dt.timedelta(days=15)


def main():
    ZIEL.mkdir(parents=True, exist_ok=True)
    orte = lade_orte()
    variablen = variablen_fuer(["solar", "wind"])
    w = gewicht(len(variablen), 8, len(orte))
    buch = D.lade_budget()
    for lauf in laeufe():
        datei = ZIEL / f"{lauf:%Y-%m-%dT%H}.parquet"
        if datei.exists():
            continue
        t0 = time.time()

        def ein_ort(o):
            q = urllib.parse.urlencode({
                "latitude": o.lat, "longitude": o.lon, "models": MODELL,
                "run": f"{lauf:%Y-%m-%dT%H:%M}", "hourly": ",".join(variablen),
                "forecast_days": 8, "timezone": "GMT"})
            for versuch in range(4):
                try:
                    req = urllib.request.Request(f"{URL}?{q}", headers={"User-Agent": USER_AGENT})
                    with urllib.request.urlopen(req, timeout=600) as r:
                        return json.load(r)["hourly"]
                except Exception as e:  # noqa: BLE001
                    log(f"  {o.name} {lauf:%Y-%m-%d %H}: {type(e).__name__} {e}, Versuch {versuch + 1}")
                    time.sleep(30 * (versuch + 1))
            raise RuntimeError(f"{o.name} {lauf}: kein Ergebnis")

        D.warte_auf_platz(buch, w)
        buch.append((time.time(), w))
        D.BUDGET.write_text(json.dumps(buch))
        with ThreadPoolExecutor(4) as pool:
            antworten = list(pool.map(ein_ort, orte))
        teile = []
        for o, h in zip(orte, antworten):
            df = pd.DataFrame({v: pd.array(h[v], dtype="Float32") for v in variablen})
            df.insert(0, "zeit", pd.to_datetime(h["time"], utc=True))
            df.insert(0, "ort", o.name)
            teile.append(df)
        df = pd.concat(teile, ignore_index=True)
        df.to_parquet(datei)
        n = df.groupby("ort").shortwave_radiation.count().min()
        log(f"{lauf:%Y-%m-%d %H} UTC: {len(orte)} Orte, mind. {n} Stunden je Ort "
            f"({time.time() - t0:.0f} s, Gewicht {w:.0f})")
    log("fertig")


if __name__ == "__main__":
    main()
