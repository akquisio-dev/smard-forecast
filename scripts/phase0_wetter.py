"""Phase 0: Luecken im ICON-Archiv (Previous Runs API) je Ort, Variable und Vorlauftag.

Ergebnis: data/phase0/wetter_luecken.csv (fehlende Stunden je Ort/Spalte/Monat)
und data/phase0/wetter_variablen.csv (Vollstaendigkeit aller Kandidaten an 3 Orten).
"""

import csv
import json
import datetime as dt
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sf.openmeteo import previous_runs  # noqa: E402
from sf.orte import ROOT, lade_orte  # noqa: E402

START = dt.date(2024, 1, 25)  # ab hier soll Tag 1 bis 6 vorhanden sein
ENDE = dt.date.today() - dt.timedelta(days=1)
AUS = ROOT / "data" / "phase0"
AUS.mkdir(parents=True, exist_ok=True)

KANDIDATEN = [
    "temperature_2m", "shortwave_radiation", "direct_radiation", "diffuse_radiation",
    "direct_normal_irradiance", "cloud_cover", "cloud_cover_low", "snow_depth",
    "wind_speed_10m", "wind_speed_100m", "wind_direction_100m", "wind_gusts_10m",
    "surface_pressure",
]


def stuecke():
    a = START
    while a <= ENDE:
        b = min(dt.date(a.year, 12, 31), ENDE)
        yield a.isoformat(), b.isoformat()
        a = b + dt.timedelta(days=1)


def luecken(h: dict) -> Counter:
    c = Counter()
    for k, werte in h.items():
        if k == "time":
            continue
        for t, v in zip(h["time"], werte):
            c[(k, t[:7])] += v is None
        c[(k, "gesamt")] += 0
    return c


def main():
    orte = lade_orte()
    zeilen = []
    for ort in orte:
        var = ["temperature_2m"]
        if "solar" in ort.typ:
            var.append("shortwave_radiation")
        if "wind" in ort.typ or "offshore" in ort.typ:
            var.append("wind_speed_100m")
        c = Counter()
        for a, b in stuecke():
            roh = AUS / "roh" / f"{ort.name}_{a}.json"
            if roh.exists():
                h = json.loads(roh.read_text())
            else:
                h = previous_runs(ort.lat, ort.lon, a, b, var)
                roh.parent.mkdir(exist_ok=True)
                roh.write_text(json.dumps(h))
                time.sleep(10)
            c.update(luecken(h))
        fehl = {k: n for k, n in c.items() if n}
        for (spalte, monat), n in sorted(fehl.items()):
            zeilen.append([ort.name, spalte, monat, n])
        print(f"{ort.name}: {sum(fehl.values())} fehlende Stunden", flush=True)
    with open(AUS / "wetter_luecken.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ort", "spalte", "monat", "fehlend"])
        w.writerows(zeilen)

    # alle Kandidaten-Variablen an drei Orten, ein Jahr
    with open(AUS / "wetter_variablen.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ort", "spalte", "fehlend", "stunden"])
        for name in ("muenchen", "husum", "nordsee_helgoland"):
            ort = next(o for o in orte if o.name == name)
            h = previous_runs(ort.lat, ort.lon, "2025-01-01", "2025-12-31", KANDIDATEN)
            for k, werte in h.items():
                if k != "time":
                    w.writerow([name, k, sum(v is None for v in werte), len(werte)])
            time.sleep(10)
    print("fertig", flush=True)


if __name__ == "__main__":
    main()
