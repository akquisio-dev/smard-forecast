# Phase 0: Ergebnisse der Datenprüfung

Stand: 2026-11-02. Skripte: `scripts/phase0_wetter.py`, `scripts/smard_laden.py`.
Rohdaten und CSV-Ergebnisse liegen unter `data/` (nicht im Git).

## Wetter (Open-Meteo Previous Runs API, `icon_seamless`)

Geprüft: alle 40 Orte aus `config/orte.toml`, Vorlauftag 1 bis 6, Zeitraum 2024-01-25 bis
2026-11-01. Je Ort `temperature_2m`, dazu `shortwave_radiation` (Solar-Orte) und
`wind_speed_100m` (Wind- und Offshore-Orte).

| Befund | Umfang | Folge |
|---|---|---|
| Ausfall im Archiv 10. bis 13.04.2026 | Tag 2, 4, 5, 6 für 1 bis 3 Tage leer, an allen Orten gleich; Tag 1 und 3 vollständig | Stunden fallen im Training weg |
| `wind_speed_100m` beginnt später | Tag 1 ab 2024-02-16, Tag 6 ab 2024-02-21 | **Trainingsbeginn 2024-02-22** für alle Quellen |
| `previous_day7` | nie vorhanden | Version 1 bis Tag 6 |
| sonst | keine Lücken | Rückfallebene nicht nötig |

Variablen (geprüft an München, Husum, Nordsee Helgoland, Jahr 2025, Tag 1 bis 6):

- vollständig: `temperature_2m`, `shortwave_radiation`, `direct_radiation`,
  `diffuse_radiation`, `direct_normal_irradiance`, `cloud_cover`, `wind_speed_10m`,
  `wind_speed_100m`, `wind_direction_100m`, `wind_gusts_10m`, `surface_pressure`
- **nicht vorhanden**: `cloud_cover_low`, `snow_depth` (Schnee auf Modulen muss ohne
  Schneehöhe auskommen, Ersatz: Temperatur und Strahlung)

Alle 7 Offshore-Orte liegen auf Höhe 0 m.

### Vorlaufzeit

Abgleich mit der Single Runs API (die erst ab Mai 2026 Läufe führt): `previous_dayN` ist der
neueste Lauf, der mindestens N mal 24 h vor der Stunde gerechnet wurde.

| Tag | gefundene Vorlaufzeit |
|---|---|
| 3 | 72 bis 77 h (Läufe alle 6 h) |
| 6 | 144 bis 150 h (Läufe alle 12 h, ICON global) |
| 1 | weicht von jedem Einzellauf um wenige Zehntel ab; die Werte stammen aus ICON-D2, aber aus einer Lauffolge, die die Single Runs API nicht führt |

Im Betrieb: Vorlaufzeit = Stunde minus Zeitpunkt des Laufs, abgerundet auf ganze Tage,
Stunden unter 24 h werden wie Tag 1 behandelt.

Offen für das eigene Archiv: welche Lauffolge `icon_seamless` in den ersten 48 h im Betrieb
liefert (ICON-D2 oder ICON-D2-RUC). Das Archiv speichert deshalb den Laufzeitpunkt mit.

### Abrufgrenzen

Ein Abruf mit 12 Spalten und einem Jahr zählt bei Open-Meteo rund 30-fach. Mit 3 s Abstand
wurde das Minutenlimit (600) erreicht und Open-Meteo lieferte leere Antworten. Mit 10 s
Abstand lief die Prüfung ohne Fehler. Der Download in Phase 1 nutzt dieselbe Drosselung und
speichert jedes Stück, damit er nach Abbruch weiterlaufen kann.

## SMARD

| Reihe | ab 2024-01-01 |
|---|---|
| Erzeugung Solar, Wind an Land, Wind auf See (stündlich) | lückenlos |
| Netzbetreiber-Prognose Wind auf See | lückenlos |
| Netzbetreiber-Prognose Solar und Wind an Land | fehlt 23.10. 22 Uhr bis 24.10.2026 (24 h) |

### Installierte Leistung

SMARD führt nur Jahreswerte, und die liegen deutlich unter dem tatsächlichen Bestand:

| | SMARD 2026 | Energy-Charts 10.2026 (monatlich) |
|---|---|---|
| Solar | 103,3 GW | 120,4 GW (AC), 132,4 GW (DC) |
| Wind an Land | 67,7 GW | 71,7 GW |
| Wind auf See | 9,2 GW | 11,7 GW |

Mit den SMARD-Werten steigt die scheinbare Auslastung von Wind auf See über die Jahre und die
von Solar fällt; beides ist ein Artefakt. **Entscheidung: Monatswerte als Nenner.** Quelle
wird Energy-Charts (Fraunhofer ISE, `installed_power`, monatlich), sofern die Lizenz das
erlaubt; sonst eigene Monatssummen aus dem Marktstammdatenregister (dl-de/by-2-0). Für Solar
wird die AC-Leistung genommen, weil die Einspeisung durch die Wechselrichter begrenzt ist.

## Prüfliste (Stand)

- [x] Previous Runs API führt `icon_seamless` ab Ende Januar 2024
- [x] Tag 7 ist im Archiv nicht vorhanden
- [x] alle Wetterorte über den ganzen Zeitraum auf Lücken geprüft
- [x] Definition der Vorlaufzeit bestätigt (Tag 3 und 6 exakt, Tag 1 näherungsweise)
- [x] SMARD-Ist-Werte ab 2024 vollständig
- [x] SMARD-Netzbetreiber-Prognose ab 2024 (ein fehlender Tag)
- [x] installierte Leistung geprüft, Monatswerte nötig
- [x] Liste der Wetterorte (`config/orte.toml`, 40 Orte)
- [ ] Lizenz der Energy-Charts-Daten klären

Ergebnis: **Phase 0 bestanden.** Die Datenlage trägt den Plan mit Trainingsbeginn 2024-02-22
(rund 32 Monate) und 6 Vorlauftagen.

## Nachtrag 2026-11-02 abends: Zeitversatz der Strahlung

Open-Meteo liefert `shortwave_radiation` als Mittel der **vorangegangenen** Stunde (Wert bei
12:00 = Mittel 11:00 bis 12:00), SMARD stempelt mit dem **Anfang** der Stunde. Geprüft mit der
Korrelation zwischen mittlerer Strahlung (21 Solar-Orte, Tag 1) und Solarerzeugung bei
verschiedenen Verschiebungen: −2 h 0,950, **−1 h 0,987**, 0 h 0,942, +1 h 0,825.
Folge für Phase 2: alle Strahlungsgrößen vor dem Zusammenführen um eine Stunde nach vorn
schieben (`shift(-1)`). Wind (Momentanwert) zeigte kaum Unterschied (0,925 gegen 0,923); wird
in Phase 2 je Variable noch einmal geprüft.
