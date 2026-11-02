# Phase 1: Daten laden und eigenes Archiv

Stand: 2026-11-02.

## Trainingsdaten

| Was | Skript | Ziel (nicht im Git) |
|---|---|---|
| ICON-Vorhersagen Tag 1 bis 6, 40 Orte, ab 2024-02-22 | `scripts/download.py` | `data/wetter/<ort>/<von>_<bis>.parquet` |
| SMARD Erzeugung und Netzbetreiber-Prognose, stündlich ab 2024 | `scripts/smard_laden.py` | `data/smard/*.parquet` |
| installierte Leistung monatlich (Energy-Charts) | `scripts/kapazitaet.py` | `data/kapazitaet.parquet` |

`download.py` lädt je Ort und Kalenderjahr ein Stück (120 Stücke, Gewicht etwa 10.500) und
hält die Grenzen von Open-Meteo ein: höchstens 9.000 am Tag, 4.500 je Stunde, 450 je Minute,
gebucht in `data/wetter/budget.json`. Ist das Tageskontingent erschöpft, wartet es bis zum
nächsten UTC-Tag. Abbruch ist unkritisch: vorhandene Stücke werden übersprungen. Laufzeit
etwa zwei Tage.

Variablen je Ortstyp stehen in `sf/openmeteo.py` (`VARIABLEN`).

## Eigenes Archiv

`archiv/archiv.py` läuft auf dem Server (nur Standardbibliothek, Python 3.10) als
`smard-forecast-archiv.timer`, stündlich um :35. Er liest die Laufzeitpunkte aus
`meta.json` von Open-Meteo und holt nur bei einem neuen Lauf von ICON-D2, ICON-EU oder ICON
global die aktuelle 8-Tage-Vorhersage aller Orte in einem Abruf (etwa 8 Abrufe am Tag,
Gewicht je 40). Gespeichert wird je Abruf eine Datei
`/var/lib/smard-forecast/archiv/JJJJ/MM/TT/<zeit>.json.gz` (etwa 95 KB, rund 300 MB im
Jahr) mit den Laufzeitpunkten aller ICON-Modelle, auch ICON-D2-RUC.

Ausrollen: `ARCHIV_HOST=root@<server> archiv/ausrollen.sh` (legt den Systemnutzer
`smard-forecast` an, kopiert Skript und Ortsliste nach `/opt/smard-forecast-archiv`,
installiert und startet den Timer). Die Server-Adresse steht nicht im Repo.

Gesichert wird das Archiv mit der nächtlichen Dienste-Sicherung (Posten `smard-forecast`).
