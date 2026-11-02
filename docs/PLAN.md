# Plan: Prognose der Erneuerbaren für smard-mcp

Stand: 2026-11-02. Ziel ist ein neues read-only Tool `forecast_renewables` in smard-mcp, das für
Solar, Wind an Land und Wind auf See die Erzeugung der nächsten Tage als Bandbreite (p10, p50,
p90) liefert. Dieses Repo enthält Datenbeschaffung, Archiv, Training, Bewertung und den Export
der Modelle. smard-mcp bekommt nur die fertigen Modelldateien und eine kleine Auswertung der
Bäume in TypeScript.

## 1. Datenlage (geprüft am 2026-11-02)

Ein Modell muss mit genau den Vorhersagen trainiert werden, die es später im Betrieb bekommt:
eine Prognose für Tag 5 lernt man nur aus früheren Vorhersagen mit 5 Tagen Vorlauf. Die
Historical Forecast API von Open-Meteo setzt nur die ersten Stunden jedes Laufs zusammen und
ist dafür ungeeignet. Grundlage ist deshalb die Previous Runs API.

Ergebnis der Stichproben (Ort 52,5 N / 10 E, Modell `icon_seamless`):

| Prüfung | Ergebnis |
|---|---|
| `icon_seamless` und `dwd_icon_seamless` | beide vorhanden, identische Werte |
| `previous_day1` | ab 2024-01-19 |
| `previous_day6` | ab 2024-01-24 |
| `previous_day7` | **nie vorhanden** (ICON global rechnet nur 180 h voraus) |
| Lücken (Feb. bis Juni 2024, Okt. 2026) | keine, jede Stunde vorhanden |
| Variablen | Strahlung (gesamt, direkt, diffus), Wind 100 m und 120 m, Wolken, Temperatur vorhanden |
| Live-Vorhersage `icon_seamless` | reicht etwa 7,5 Tage voraus |

Folgen:

- **Version 1 deckt 6 Tage ab, nicht 7.** Tag 7 wird erst möglich, wenn das eigene Archiv
  (Abschnitt 5) mindestens einen Jahresgang enthält.
- Trainingszeitraum: Ende Januar 2024 bis heute, rund 33 Monate.
- `icon_seamless` nimmt bis 48 h ICON-D2, bis 120 h ICON-EU, danach ICON global. Das ist in
  Training und Betrieb gleich. Tag 6 stammt damit immer aus dem gröberen ICON global (13 km),
  das gehört in die `notes` des Tools.

## 2. Vorlaufzeit

`previous_dayN` ist der Wert aus dem Lauf, der etwa N mal 24 h vor der jeweiligen Stunde
gerechnet wurde. Im Betrieb wird die Vorlaufzeit genauso bestimmt: **Stunde minus Zeitpunkt
des ICON-Laufs**, abgerundet auf ganze Tage. „Morgen = Tag 1" wäre falsch, weil dann Training
und Betrieb verschiedene Dinge meinen.

Die Vorlaufzeit (1 bis 6) ist ein Merkmal. Ein Modell je Quelle und Quantil deckt alle
Vorlauftage ab und lernt selbst, dass Tag 6 unsicherer ist als Tag 1.

Rückfallebene, falls bei der vollständigen Prüfung (Phase 0) doch größere Lücken auftauchen:
den Zusammenhang Wetter zu Strom aus kurzfristigen Vorhersagen lernen und die Bandbreite je
Vorlauftag getrennt aus dem vorhandenen Archiv schätzen.

## 3. Modell

- Je Quelle (Solar, Wind an Land, Wind auf See) ein LightGBM-Modell je Quantil (p10, p50,
  p90): neun kleine Modelle, Training auf CPU in Minuten, unter 1 GB RAM.
- Zielgröße ist die **Auslastung** (Erzeugung geteilt durch installierte Leistung). Im Betrieb
  wird mit der aktuellen Leistung zurück in GW gerechnet. Installierte Leistung: SMARD
  `capacity_*` (Jahreswerte), später Monatswerte aus dem Marktstammdatenregister.
- Quantile dürfen sich nicht kreuzen: nach der Vorhersage p10 <= p50 <= p90 erzwingen
  (sortieren).
- Solar nachts: bei Sonnenhöhe unter 0 fest 0, diese Stunden fließen weder ins Training noch
  in die Kennzahlen ein.

Merkmale:

- Wettergrößen je Wetterort als eigene Spalten (das Modell gewichtet selbst)
- Vorlaufzeit in Tagen (1 bis 6)
- Stunde, Tag im Jahr (Sinus und Kosinus), Sonnenhöhe (berechnet)
- Wochentag und Feiertag (Abregelung bei negativen Preisen, vor allem Solar an Feiertagen)

Wetterorte: in Version 1 eine feste Liste von rund 35 Orten in `config/orte.toml`
(Solar-Schwerpunkte, Windregionen an Land, Cluster in Nord- und Ostsee). Eine aus dem
Marktstammdatenregister berechnete Gewichtung kommt später.

## 4. Bewertung

- Validierung nur zeitlich: rollierend Monat für Monat (trainieren bis Monat M, testen auf
  M+1), erstes Testfenster nach 12 Monaten Training. Dazu die letzten 3 Monate als unberührter
  Abschlusstest.
- Der Abschlusstest enthält zurzeit keinen Winter. Die Wintermonate aus der rollierenden
  Prüfung werden deshalb im Bericht getrennt ausgewiesen (Dunkelflaute, Sturmabschaltung).
- Kennzahlen je Vorlauftag: MAE in GW und in % der Leistung, Fehler der Tagesenergie in GWh,
  Trefferquote der Bandbreite (Anteil der Stunden zwischen p10 und p90, Ziel um 80 %).

Messlatten:

| Messlatte | Was sie ist | Gilt für |
|---|---|---|
| Klimatologie | mittlere Auslastung je Stunde und Monat der Vorjahre | Tag 1 bis 6 |
| Persistenz | wie der letzte vollständige Tag | Tag 1 bis 6 |
| Netzbetreiber | SMARD `forecast_generation_*` | Tag 1 |

Weiter-Kriterium (Startwert, nach den ersten Ergebnissen anpassbar): an Tag 2 bis 6 mindestens
20 % weniger MAE als die bessere einfache Messlatte, an Tag 1 höchstens 20 % mehr Fehler als
die Netzbetreiber, Trefferquote zwischen 75 und 85 %.

## 5. Eigenes Archiv

Ein täglicher Job auf der Web-Maschine speichert die aktuelle Vorhersage aller Wetterorte mit
Laufzeitpunkt. Zweck: Schutz gegen Lücken im fremden Archiv, Daten für das Monitoring und
später Trainingsdaten für Tag 7. Das Archiv startet in Phase 1, also **vor** dem Modell, weil
es Zeit braucht, um zu wachsen. Es läuft mit der bestehenden Sicherung der Maschine mit.

## 6. Datenbeschaffung

- Erster Download einmalig, gestückelt nach Ort und Monat, gespeichert als Parquet unter
  `data/` (nicht im Git). Fortsetzbar: bereits vorhandene Stücke werden übersprungen.
- Umfang: rund 35 Orte, etwa 6 Variablen, 6 Vorlauftage, 33 Monate. Nach der Gewichtung von
  Open-Meteo sind das ungefähr 10.000 Aufrufe, also das Tageslimit. Der Download wird deshalb
  über 2 bis 3 Tage verteilt (Obergrenze je Tag im Skript).
- SMARD-Ist-Werte (Erzeugung je Quelle, stündlich) und die Netzbetreiber-Prognose kommen über
  dieselben Endpunkte wie in smard-mcp.

## 7. Das Tool in smard-mcp

`forecast_renewables`, read-only, im Stil der anderen Tools. Version 1 nur Deutschland gesamt.

| Parameter | Werte | Standard |
|---|---|---|
| `from`, `to` | ISO-Datum oder Datum mit Uhrzeit (Berlin), höchstens 6 Tage ab jetzt | jetzt bis +6 Tage |
| `sources` | `solar`, `wind_onshore`, `wind_offshore` | alle drei |
| `resolution` | `hour`, `day` | `day`, bei bis zu 48 h `hour` |
| `include_intervals` | ja, nein | nein |

Ausgabe: je Quelle und Intervall p10, p50, p90 in GW, je Tag die Energie in GWh mit
Bandbreite; daneben `official_forecast`, wo die Netzbetreiber veröffentlicht haben; die
üblichen Felder (Zeitraum, Region, Auflösung, `covered_until`, `complete`, `notes`,
`warnings`, Quelle, `server_time`); neu `model_version`, `trained_until`, `weather_run` und der
Fehler je Vorlauftag aus dem Abschlusstest sowie aus den letzten 30 Tagen Monitoring.

Verhalten am Rand:

- Zeitraum über 6 Tage hinaus: Fehler mit dem letzten möglichen Zeitpunkt
- Zeitraum in der Vergangenheit: Fehler mit Hinweis auf `get_generation_mix`
- Wetter-API nicht erreichbar: zuletzt gespeicherte Vorhersage mit `warnings` und Alter, ab
  12 Stunden Alter ein Fehler
- Quelle: „Bundesnetzagentur | SMARD.de (CC BY 4.0)" und „Wetterdaten: Open-Meteo.com
  (CC BY 4.0), Modelle des DWD"

Technik:

- Modelle werden als LightGBM-JSON (`dump_model`) exportiert, Baumzahl begrenzt, damit das
  npm-Paket klein bleibt. smard-mcp liest sie aus `models/` (Eintrag in `files` der
  `package.json`) mit einer eigenen Auswertung in TypeScript, ohne neue Abhängigkeit. Ein Test
  vergleicht die TS-Auswertung mit Python-Vorhersagen auf festen Beispielzeilen.
- Wetter: alle Orte in einem Aufruf (kommagetrennt), Cache bis zum nächsten ICON-Lauf (alle
  3 h), etwa 24 Aufrufe am Tag.
- Neue Modelle: monatlicher Workflow in diesem Repo lädt den letzten Monat nach, trainiert,
  misst gegen die Messlatten und öffnet einen Pull Request mit Modelldateien und
  Fehlerbericht. Gemergt wird von Hand. Die Übernahme in smard-mcp ist ein eigener, bewusster
  Schritt.

## 8. Phasen

| Phase | Inhalt | smard-mcp betroffen |
|---|---|---|
| 0 | vollständige Datenprüfung (Prüfliste unten) | nein |
| 1 | Download nach Parquet, täglicher Archiv-Job startet | nein |
| 2 | Solar-Modell und Messlatten, **Prüfpunkt A** | nein |
| 3 | Wind an Land und auf See, **Prüfpunkt B** | nein |
| 4 | TS-Auswertung und Tool auf einem Branch | ja, nicht live |
| 5 | Monitoring und monatlicher Workflow | ja |
| 6 | ausrollen, 2 bis 4 Wochen Fehler im Betrieb beobachten, **Prüfpunkt C**, danach npm-Release | ja |

Erst wenn das Solar-Modell an Prüfpunkt A die Messlatten schlägt, entsteht Code in smard-mcp.
Termine sind bewusst offen.

### Prüfliste Phase 0

- [x] Previous Runs API führt `icon_seamless` ab Ende Januar 2024 (Stichproben)
- [x] Tag 7 ist im Archiv nicht vorhanden
- [ ] alle Wetterorte über den ganzen Zeitraum auf Lücken prüfen, je Variable und Vorlauftag
- [ ] Werte von `previous_day1` gegen die Live-Vorhersage desselben Laufs abgleichen
      (bestätigt die Definition der Vorlaufzeit)
- [ ] SMARD-Ist-Werte Solar, Wind an Land, Wind auf See stündlich ab 2024 vollständig
- [ ] SMARD-Netzbetreiber-Prognose je Quelle ab 2024 vollständig
- [ ] installierte Leistung je Quelle und Jahr aus SMARD
- [ ] Liste der Wetterorte festlegen (`config/orte.toml`)

## 9. Risiken

| Risiko | Folge | Gegenmaßnahme |
|---|---|---|
| Lücken im ICON-Archiv | weniger Trainingsdaten | Prüfung in Phase 0, Rückfallebene aus Abschnitt 2 |
| Abregelung bei negativen Preisen | Erzeugung unter dem Wetterwert | Wochentag und Feiertag als Merkmal, Hinweis in `notes` |
| Zubau nur als Jahreswert | systematischer Versatz, vor allem Solar | später Monatswerte aus dem Marktstammdatenregister |
| seltene Wetterlagen | grobe Ausreißer | Quantile, Winter getrennt bewertet |
| Open-Meteo ändert Bedingungen oder fällt aus | keine Prognose | Cache mit `warnings`, langfristig DWD Open Data als zweite Quelle |
| Lizenz | freie API nur nicht-kommerziell | smard-mcp bleibt kostenlos und ohne Werbung; sonst API-Key-Tarif |

Nicht in Version 1: Anteil an der Last (bräuchte eine eigene Verbrauchsprognose), Regelzonen.
