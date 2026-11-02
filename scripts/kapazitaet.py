"""Installierte Leistung monatlich (Energy-Charts, Fraunhofer ISE) nach data/kapazitaet.parquet.

SMARD fuehrt nur zu niedrige Jahreswerte (docs/phase0.md). Lizenz der Energy-Charts-Daten
ist noch zu klaeren; Rueckfall: Monatssummen aus dem Marktstammdatenregister.
Spalten: monat (JJJJ-MM), solar (AC), wind_onshore, wind_offshore, alles in MW.
"""

import json
import sys
import urllib.request
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sf.log import log  # noqa: E402
from sf.orte import ROOT  # noqa: E402

URL = ("https://api.energy-charts.info/installed_power?country=de&time_step=monthly"
       "&installation_decommission=false")
NAMEN = {"Solar AC": "solar", "Wind onshore": "wind_onshore", "Wind offshore": "wind_offshore"}


def main():
    req = urllib.request.Request(URL, headers={"User-Agent": "smard-forecast"})
    j = json.load(urllib.request.urlopen(req, timeout=60))
    monat = [f"{t[3:]}-{t[:2]}" for t in j["time"]]  # "MM.JJJJ" -> "JJJJ-MM"
    df = pd.DataFrame({"monat": monat})
    for p in j["production_types"]:
        if p["name"] in NAMEN:
            df[NAMEN[p["name"]]] = [None if v is None else v * 1000 for v in p["data"]]  # GW -> MW
    df = df[df.monat >= "2023-01"].reset_index(drop=True)
    df.to_parquet(ROOT / "data" / "kapazitaet.parquet", index=False)
    log(df.tail(3).to_string(index=False))


if __name__ == "__main__":
    main()
