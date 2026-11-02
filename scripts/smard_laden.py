"""SMARD-Ist-Werte, Netzbetreiber-Prognose und installierte Leistung ab 2024 laden (Phase 0 und 1).

Speichert die Reihen als data/smard/<schluessel>.parquet (wird in Phase 1 weiterverwendet)
und schreibt data/phase0/smard_luecken.csv.
"""

import csv
import datetime as dt
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sf.log import log  # noqa: E402
from sf.orte import ROOT  # noqa: E402
from sf.smard import KAPAZITAET, REIHEN, reihe  # noqa: E402

AB = int(dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc).timestamp() * 1000)
AUS = ROOT / "data" / "smard"
AUS.mkdir(parents=True, exist_ok=True)
(ROOT / "data" / "phase0").mkdir(parents=True, exist_ok=True)


def main():
    zeilen = []
    for key, fid in REIHEN.items():
        p = reihe(fid, ab_ms=AB)
        df = pd.DataFrame(p, columns=["ts", "mwh"])
        df["zeit"] = pd.to_datetime(df.ts, unit="ms", utc=True)
        df.drop(columns="ts").to_parquet(AUS / f"{key}.parquet")
        bis = df.dropna().zeit.max()
        voll = pd.date_range(df.zeit.min(), bis, freq="h")
        da = set(df.dropna().zeit)
        fehlt = [t for t in voll if t not in da]
        mon = pd.Series([t.strftime("%Y-%m") for t in fehlt]).value_counts().sort_index()
        log(f"{key}: {df.zeit.min():%Y-%m-%d} bis {bis:%Y-%m-%d %H:%M}, "
              f"{len(fehlt)} fehlende Stunden {dict(mon)}", flush=True)
        zeilen += [[key, m, n] for m, n in mon.items()]
    with open(ROOT / "data" / "phase0" / "smard_luecken.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["reihe", "monat", "fehlend"])
        w.writerows(zeilen)
    for key, fid in KAPAZITAET.items():
        p = reihe(fid, aufloesung="year", ab_ms=0)
        df = pd.DataFrame(p, columns=["ts", "mw"])
        df["jahr"] = pd.to_datetime(df.ts, unit="ms", utc=True).dt.tz_convert("Europe/Berlin").dt.year
        df[["jahr", "mw"]].to_parquet(AUS / f"capacity_{key}.parquet")
        log(f"capacity_{key}:", dict(zip(df.jahr, df.mw)), flush=True)


if __name__ == "__main__":
    main()
