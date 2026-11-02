"""Open-Meteo: Previous Runs API (Training) mit Wiederholungen und Drosselung."""

import json
import time
import urllib.error
import urllib.parse
import urllib.request

PREVIOUS_RUNS = "https://previous-runs-api.open-meteo.com/v1/forecast"
MODELL = "icon_seamless"
VORLAUFTAGE = range(1, 7)  # previous_day7 gibt es im Archiv nicht
# Variablen je Ortstyp (cloud_cover_low und snow_depth fehlen im Archiv, siehe docs/phase0.md)
VARIABLEN = {
    "solar": ["shortwave_radiation", "direct_radiation", "diffuse_radiation",
              "temperature_2m", "cloud_cover", "wind_speed_10m"],
    "wind": ["wind_speed_10m", "wind_speed_100m", "wind_direction_100m",
             "wind_gusts_10m", "temperature_2m", "surface_pressure"],
}
VARIABLEN["offshore"] = VARIABLEN["wind"]


def variablen_fuer(typen) -> list[str]:
    """Vereinigung der Variablen aller Typen eines Ortes, Reihenfolge stabil."""
    aus: list[str] = []
    for t in typen:
        aus += [v for v in VARIABLEN[t] if v not in aus]
    return aus


def gewicht(spalten: int, tage: int, orte: int = 1) -> float:
    """Zaehlweise von Open-Meteo: ab 10 Variablen bzw. 14 Tagen anteilig mehr."""
    return orte * max(1.0, spalten / 10) * max(1.0, tage / 14)


USER_AGENT = "smard-forecast (+https://github.com/akquisio-dev/smard-forecast)"


def _hole(url: str, versuche: int = 5) -> dict:
    for i in range(versuche):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429 or e.code >= 500:
                time.sleep(30 * (i + 1))
                continue
            raise RuntimeError(f"{e.code}: {e.read()[:300]!r}") from e
        except (urllib.error.URLError, TimeoutError, ValueError, ConnectionError):
            time.sleep(10 * (i + 1))
    raise RuntimeError(f"Open-Meteo nicht erreichbar: {url}")


def previous_runs(lat: float, lon: float, start: str, ende: str, variablen: list[str],
                  tage=VORLAUFTAGE) -> dict:
    """Stuendliche Werte (UTC) je Variable und Vorlauftag: Schluessel '<var>_previous_day<N>'."""
    spalten = [f"{v}_previous_day{n}" for v in variablen for n in tage]
    q = urllib.parse.urlencode({
        "latitude": lat, "longitude": lon, "models": MODELL,
        "start_date": start, "end_date": ende, "hourly": ",".join(spalten),
        "timezone": "GMT",
    })
    return _hole(f"{PREVIOUS_RUNS}?{q}")["hourly"]
