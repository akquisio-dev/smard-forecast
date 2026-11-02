"""Einheitliches Protokoll: jede Zeile mit UTC-Zeit auf stdout und in data/logs/<skript>.log.

Die Logdateien bleiben dauerhaft liegen (nicht im Git), damit jeder Lauf auch spaeter noch
nachvollziehbar ist. Wichtige Ergebnisse und Fehlschlaege gehoeren zusaetzlich ins
Projekttagebuch docs/journal.md.
"""

import datetime as dt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_datei = None


def log(*teile, **_ignoriert):
    global _datei
    if _datei is None:
        ordner = ROOT / "data" / "logs"
        ordner.mkdir(parents=True, exist_ok=True)
        _datei = open(ordner / f"{Path(sys.argv[0]).stem}.log", "a", buffering=1)
    zeile = f"{dt.datetime.now(dt.timezone.utc):%Y-%m-%d %H:%M:%S}Z " + " ".join(map(str, teile))
    print(zeile, flush=True)
    _datei.write(zeile + "\n")
