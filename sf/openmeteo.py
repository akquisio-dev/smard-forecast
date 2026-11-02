"""Open-Meteo: Previous Runs API (Training) mit Wiederholungen und Drosselung."""

import json
import time
import urllib.error
import urllib.parse
import urllib.request

PREVIOUS_RUNS = "https://previous-runs-api.open-meteo.com/v1/forecast"
MODELL = "icon_seamless"
VORLAUFTAGE = range(1, 7)  # previous_day7 gibt es im Archiv nicht
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
