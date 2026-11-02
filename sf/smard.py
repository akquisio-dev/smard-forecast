"""SMARD chart_data: Index und Wochenstuecke laden."""

import json
import time
import urllib.request

BASE = "https://www.smard.de/app/chart_data"
USER_AGENT = "smard-forecast (+https://github.com/akquisio-dev/smard-forecast)"

# Schluessel wie in smard-mcp (src/catalog.ts)
REIHEN = {
    "generation_solar": 4068,
    "generation_wind_onshore": 4067,
    "generation_wind_offshore": 1225,
    "forecast_generation_solar": 125,
    "forecast_generation_wind_onshore": 123,
    "forecast_generation_wind_offshore": 3791,
}
KAPAZITAET = {"solar": 188, "wind_onshore": 186, "wind_offshore": 4076}


def _hole(url: str) -> dict:
    for i in range(5):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except Exception:
            time.sleep(5 * (i + 1))
    raise RuntimeError(f"SMARD nicht erreichbar: {url}")


def reihe(filter_id: int, region: str = "DE", aufloesung: str = "hour",
          ab_ms: int = 0) -> list[tuple[int, float | None]]:
    """Alle Punkte (Zeitstempel ms UTC, MWh) ab ab_ms."""
    idx = _hole(f"{BASE}/{filter_id}/{region}/index_{aufloesung}.json")["timestamps"]
    starts = [t for t in idx if t >= ab_ms - 7 * 86400_000]
    punkte = []
    for t in starts:
        d = _hole(f"{BASE}/{filter_id}/{region}/{filter_id}_{region}_{aufloesung}_{t}.json")
        punkte += [(ts, v) for ts, v in d["series"] if ts >= ab_ms]
        time.sleep(0.2)
    return sorted(dict(punkte).items())
