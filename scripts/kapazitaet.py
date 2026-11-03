"""Installierte Leistung monatlich (Energy-Charts, Fraunhofer ISE) nach data/kapazitaet.parquet.

SMARD fuehrt nur zu niedrige Jahreswerte (docs/phase0.md). Lizenz der Energy-Charts-Daten
ist noch zu klaeren; Rueckfall: Monatssummen aus dem Marktstammdatenregister.

Die juengsten Monate sind unvollstaendig: Anlagen werden im Marktstammdatenregister
nachgemeldet, und der laufende Monat ist bei Energy-Charts nur eine Kopie des Vormonats
(November 2026 = Oktober 2026). Deshalb:
  * jeder Abruf wird unveraendert als Stand gespeichert (data/kapazitaet_staende/), damit sich
    spaetere Korrekturen messen lassen;
  * fuer Solar und Wind an Land gilt ein Monat als bestaetigt bis zum letzten Monat mit echtem
    Zuwachs (mind. 20 % des typischen); danach wird mit dem mittleren Zuwachs der 6 Monate davor
    fortgeschrieben (Spalte geschaetzt_*). Wind auf See waechst sprunghaft und wird nur gehalten.

Spalten: monat (JJJJ-MM), solar (AC), wind_onshore, wind_offshore in MW, geschaetzt_<quelle>.
"""

import datetime as dt
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
FENSTER = 6
STAENDE = ROOT / "data" / "kapazitaet_staende"


def fortschreiben(s: pd.Series, monate: pd.Index) -> tuple[pd.Series, pd.Series]:
    """Nach dem letzten echten Zuwachs mit dem mittleren Zuwachs fortschreiben."""
    s = s.copy()
    zuwachs = s.diff()
    # "echter" Zuwachs: mindestens 20 % des typischen Monatszuwachses (Median der letzten 12)
    schwelle = 0.2 * zuwachs.iloc[-13:-1].median()
    echt = zuwachs[zuwachs > schwelle]
    letzter = echt.index[-1]
    i = list(s.index).index(letzter)
    mittel = zuwachs.iloc[max(1, i - FENSTER + 1):i + 1].mean()
    geschaetzt = pd.Series(False, index=s.index)
    for k in range(i + 1, len(s)):
        s.iloc[k] = s.iloc[k - 1] + mittel
        geschaetzt.iloc[k] = True
    return s, geschaetzt


def main():
    req = urllib.request.Request(URL, headers={"User-Agent": "smard-forecast"})
    roh = urllib.request.urlopen(req, timeout=60).read()
    STAENDE.mkdir(parents=True, exist_ok=True)
    (STAENDE / f"{dt.date.today().isoformat()}.json").write_bytes(roh)
    j = json.loads(roh)
    monat = [f"{t[3:]}-{t[:2]}" for t in j["time"]]  # "MM.JJJJ" -> "JJJJ-MM"
    df = pd.DataFrame({"monat": monat})
    for p in j["production_types"]:
        if p["name"] in NAMEN:
            df[NAMEN[p["name"]]] = [None if v is None else v * 1000 for v in p["data"]]  # GW->MW
    df = df[df.monat >= "2023-01"].dropna(how="all", subset=list(NAMEN.values()))
    # bis zum naechsten Monat verlaengern, damit der Betrieb immer einen Wert hat
    naechster = (pd.Period(dt.date.today(), "M") + 1).strftime("%Y-%m")
    alle = pd.period_range(df.monat.min(), naechster, freq="M").strftime("%Y-%m")
    df = df.set_index("monat").reindex(alle).ffill()
    for q in NAMEN.values():
        if q == "wind_offshore":
            # Wind auf See waechst in Spruengen (ganze Parks), monatelanger Stillstand ist echt
            # (z. B. 06/2025 = 12/2024). Kein Trend, nur den letzten Wert halten.
            df[f"geschaetzt_{q}"] = df.index > pd.Period(dt.date.today(), "M").strftime("%Y-%m")
            log(f"{q}: nicht fortgeschrieben (sprunghafter Zubau)")
            continue
        df[q], df[f"geschaetzt_{q}"] = fortschreiben(df[q], df.index)
        g = df.index[df[f"geschaetzt_{q}"]].tolist()
        log(f"{q}: bestaetigt bis {df.index[~df[f'geschaetzt_{q}']][-1]}, fortgeschrieben {g}")
    df = df.reset_index().rename(columns={"index": "monat"})
    df.to_parquet(ROOT / "data" / "kapazitaet.parquet", index=False)
    log(df.tail(4).to_string(index=False))


if __name__ == "__main__":
    main()
