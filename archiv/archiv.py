"""Eigenes Archiv der ICON-Vorhersagen (laeuft auf dem Server, nur Standardbibliothek, Python 3.10).

Prueft stuendlich, ob Open-Meteo einen neuen ICON-Lauf hat (ICON-D2, ICON-EU, ICON global).
Wenn ja, wird die aktuelle 8-Tage-Vorhersage aller Wetterorte in einem Abruf geholt und als
<ARCHIV>/JJJJ/MM/TT/JJJJMMTTTHHMMZ.json.gz gespeichert, zusammen mit den Laufzeitpunkten.
Zweck: Monitoring, spaeter Trainingsdaten fuer Tag 7, Schutz gegen Luecken im fremden Archiv.
"""

import datetime as dt
import gzip
import json
import os
import sys
import time
import urllib.parse
import urllib.request

ARCHIV = os.environ.get("ARCHIV_DIR", "/var/lib/smard-forecast/archiv")
ORTE = os.environ.get("ORTE_JSON", os.path.join(os.path.dirname(__file__), "orte.json"))
USER_AGENT = "smard-forecast-archiv (+https://github.com/akquisio-dev/smard-forecast)"
FORECAST = "https://api.open-meteo.com/v1/forecast"
# Ausloeser: ein neuer Lauf eines dieser Modelle. RUC laeuft stuendlich und wird nur
# mitgeschrieben, nicht als Ausloeser genutzt (sonst 24 Abrufe am Tag).
AUSLOESER = ["dwd_icon_d2", "dwd_icon_eu", "dwd_icon"]
NUR_MERKEN = ["dwd_icon_d2_ruc_native_15min"]
VARIABLEN = ["shortwave_radiation", "direct_radiation", "diffuse_radiation", "temperature_2m",
             "cloud_cover", "wind_speed_10m", "wind_speed_100m", "wind_direction_100m",
             "wind_gusts_10m", "surface_pressure"]


def hole(url):
    letzter = None
    for i in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except Exception as e:  # noqa: BLE001
            letzter = e
            time.sleep(20 * (i + 1))
    raise RuntimeError(f"{url}: {letzter}")


def laeufe():
    """Startzeit und Datenende des neuesten Laufs je Modell (Datenende fuer den Vorlauf im
    Monitoring: welcher Lauf deckt welche Stunde ab)."""
    aus, ende = {}, {}
    for m in AUSLOESER + NUR_MERKEN:
        meta = hole(f"https://api.open-meteo.com/data/{m}/static/meta.json")
        fmt = lambda s: dt.datetime.fromtimestamp(s, dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")  # noqa: E731
        aus[m] = fmt(meta["last_run_initialisation_time"])
        if "data_end_time" in meta:
            ende[m] = fmt(meta["data_end_time"])
    return aus, ende


def main():
    os.makedirs(ARCHIV, exist_ok=True)
    stand_datei = os.path.join(ARCHIV, "letzter_stand.json")
    l, l_ende = laeufe()
    vorher = json.load(open(stand_datei)) if os.path.exists(stand_datei) else {}
    if all(vorher.get(m) == l[m] for m in AUSLOESER) and "--immer" not in sys.argv:
        print("kein neuer Lauf:", {m: l[m] for m in AUSLOESER})
        return
    orte = json.load(open(ORTE))
    q = urllib.parse.urlencode({
        "latitude": ",".join(str(o["lat"]) for o in orte),
        "longitude": ",".join(str(o["lon"]) for o in orte),
        "models": "icon_seamless", "hourly": ",".join(VARIABLEN),
        "forecast_days": 8, "timezone": "GMT",
    })
    daten = hole(f"{FORECAST}?{q}")
    if isinstance(daten, dict):
        daten = [daten]
    if len(daten) != len(orte):
        raise RuntimeError(f"{len(daten)} Antworten fuer {len(orte)} Orte")
    jetzt = dt.datetime.now(dt.timezone.utc)
    eintrag = {
        "abgerufen": jetzt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "modell": "icon_seamless",
        "laeufe": l,
        "laeufe_ende": l_ende,
        "orte": [{"name": o["name"], "lat": o["lat"], "lon": o["lon"],
                  "elevation": d.get("elevation"), "hourly": d["hourly"]}
                 for o, d in zip(orte, daten)],
    }
    ordner = os.path.join(ARCHIV, jetzt.strftime("%Y/%m/%d"))
    os.makedirs(ordner, exist_ok=True)
    ziel = os.path.join(ordner, jetzt.strftime("%Y%m%dT%H%MZ") + ".json.gz")
    with gzip.open(ziel + ".tmp", "wt", compresslevel=9) as f:
        json.dump(eintrag, f, separators=(",", ":"))
    os.replace(ziel + ".tmp", ziel)
    with open(stand_datei + ".tmp", "w") as f:
        json.dump(l, f)
    os.replace(stand_datei + ".tmp", stand_datei)
    print("gespeichert:", ziel, os.path.getsize(ziel), "Bytes, Laeufe:", l)


if __name__ == "__main__":
    main()
