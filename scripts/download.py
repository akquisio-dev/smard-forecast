"""Phase 1: Trainingsdaten aus der Previous Runs API laden.

Je Ort und Kalenderjahr ein Stueck, gespeichert als
data/wetter/<ort>/<start>.parquet (lange Form: zeit UTC, vorlauf 1-6, Variablen).
Fortsetzbar: vorhandene Stuecke werden uebersprungen. Haelt die Abrufgrenzen von
Open-Meteo ein (Buchfuehrung in data/wetter/budget.json) und wartet bei vollem
Tageskontingent bis zum naechsten UTC-Tag.

Aufruf: python -I scripts/download.py [--bis YYYY-MM-DD]
"""

import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sf.log import log  # noqa: E402
from sf.openmeteo import VORLAUFTAGE, gewicht, previous_runs, variablen_fuer  # noqa: E402
from sf.orte import ROOT, lade_orte  # noqa: E402

START = dt.date(2024, 2, 22)  # wind_speed_100m ab hier vollstaendig, siehe docs/phase0.md
ZIEL = ROOT / "data" / "wetter"
BUDGET = ZIEL / "budget.json"
GRENZE = {"tag": 9000, "stunde": 4500, "minute": 450}  # Open-Meteo: 10000/5000/600


def jetzt():
    return dt.datetime.now(dt.timezone.utc)


def lade_budget() -> list[tuple[float, float]]:
    if BUDGET.exists():
        return [tuple(x) for x in json.loads(BUDGET.read_text())]
    return []


def warte_auf_platz(buch: list, w: float):
    """Blockiert, bis ein Abruf mit Gewicht w in alle drei Fenster passt."""
    while True:
        t = time.time()
        heute = jetzt().replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        buch[:] = [(ts, g) for ts, g in buch if ts >= min(heute, t - 3600)]
        tag = sum(g for ts, g in buch if ts >= heute)
        std = sum(g for ts, g in buch if ts >= t - 3600)
        mnt = sum(g for ts, g in buch if ts >= t - 60)
        if tag + w > GRENZE["tag"]:
            morgen = heute + 86400 + 300
            log(f"Tageskontingent erreicht ({tag:.0f}), warte bis "
                  f"{dt.datetime.fromtimestamp(morgen, dt.timezone.utc):%Y-%m-%d %H:%M} UTC",
                  flush=True)
            time.sleep(max(60, morgen - t))
        elif std + w > GRENZE["stunde"]:
            time.sleep(120)
        elif mnt + w > GRENZE["minute"]:
            time.sleep(15)
        else:
            return


def stuecke(bis: dt.date, ab: dt.date = START):
    """Stuecke je Kalenderjahr von ab bis bis."""
    a = ab
    while a <= bis:
        b = min(dt.date(a.year, 12, 31), bis)
        yield a, b
        a = b + dt.timedelta(days=1)


def in_tabelle(h: dict, variablen: list[str]) -> pd.DataFrame:
    zeit = pd.to_datetime(h["time"], utc=True)
    teile = []
    for n in VORLAUFTAGE:
        df = pd.DataFrame({"zeit": zeit, "vorlauf": n})
        for v in variablen:
            df[v] = pd.array(h[f"{v}_previous_day{n}"], dtype="Float32")
        teile.append(df)
    df = pd.concat(teile, ignore_index=True)
    df["vorlauf"] = df.vorlauf.astype("int8")
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bis", type=dt.date.fromisoformat,
                    default=dt.date.today() - dt.timedelta(days=1))
    args = ap.parse_args()
    ZIEL.mkdir(parents=True, exist_ok=True)
    buch = lade_budget()
    offen = []
    for ort in lade_orte():
        var = variablen_fuer(ort.typ)
        # Nur anhaengen: Stuecke beginnen nach dem Ende des letzten vorhandenen Stuecks,
        # damit beim Nachladen kein Zeitraum doppelt vorkommt (merkmale.py liest alle Stuecke).
        enden = [dt.date.fromisoformat(f.stem.split("_")[1])
                 for f in (ZIEL / ort.name).glob("*.parquet")]
        ab = max(enden) + dt.timedelta(days=1) if enden else START
        for a, b in stuecke(args.bis, ab):
            datei = ZIEL / ort.name / f"{a.isoformat()}_{b.isoformat()}.parquet"
            if not datei.exists():
                offen.append((ort, var, a, b, datei))
    gesamt = sum(gewicht(len(v) * len(VORLAUFTAGE), (b - a).days + 1) for _, v, a, b, _ in offen)
    log(f"{len(offen)} Stuecke offen, Gewicht etwa {gesamt:.0f}", flush=True)
    for i, (ort, var, a, b, datei) in enumerate(offen, 1):
        w = gewicht(len(var) * len(VORLAUFTAGE), (b - a).days + 1)
        warte_auf_platz(buch, w)
        h = previous_runs(ort.lat, ort.lon, a.isoformat(), b.isoformat(), var)
        buch.append((time.time(), w))
        BUDGET.write_text(json.dumps(buch))
        df = in_tabelle(h, var)
        datei.parent.mkdir(parents=True, exist_ok=True)
        tmp = datei.with_suffix(".tmp")
        df.to_parquet(tmp, index=False)
        tmp.rename(datei)
        leer = int(df[var].isna().all(axis=1).sum())
        log(f"[{i}/{len(offen)}] {ort.name} {a}..{b}: {len(df)} Zeilen, "
              f"{leer} ganz leer, Gewicht {w:.0f}", flush=True)
    log("fertig", flush=True)


if __name__ == "__main__":
    main()
