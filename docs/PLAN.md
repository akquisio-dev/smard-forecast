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

`previous_dayN` ist der Wert aus dem neuesten Lauf, der mindestens N mal 24 h vor der Stunde
startete; im Training hat Tag N also etwa N·24 bis N·24+6 h Vorlauf (Mitte etwa N·24+3 h).

**Korrigiert am 2026-11-03** (Hinweis des Betreuers): Im Betrieb hat die neueste Vorhersage für
eine Stunde einen beliebigen Vorlauf L in Stunden. Abrunden auf ganze Tage (frühere Fassung)
hätte z. B. 95 h als „Tag 3“ behandelt, obwohl Tag 3 nur mit 72 bis 77 h gelernt wurde; die
Bandbreiten wären zu schmal. Stattdessen wird zwischen den beiden benachbarten Vorlauftagen
interpoliert:

    x = (L - 3 h) / 24 h,  N = floor(x),  w = x - N
    Vorhersage = (1 - w) · Modell(Tag N) + w · Modell(Tag N+1)    (x < 1 -> Tag 1, x > 6 -> Tag 6)

danach p10 <= p50 <= p90 erzwingen. Prüfung in Phase 4: mit der Single Runs API (Läufe ab Mai
2026) die Trefferquote je Vorlauf in Stunden messen, mit Interpolation gegen Abrunden.

Die Vorlaufzeit (1 bis 6) ist ein Merkmal. Ein Modell je Quelle und Quantil deckt alle
Vorlauftage ab und lernt selbst, dass Tag 6 unsicherer ist als Tag 1.

Rückfallebene, falls bei der vollständigen Prüfung (Phase 0) doch größere Lücken auftauchen:
den Zusammenhang Wetter zu Strom aus kurzfristigen Vorhersagen lernen und die Bandbreite je
Vorlauftag getrennt aus dem vorhandenen Archiv schätzen.

## 3. Modell

- Je Quelle (Solar, Wind an Land, Wind auf See) ein LightGBM-Modell je Quantil (p10, p50,
  p90): neun kleine Modelle, Training auf CPU in Minuten, unter 1 GB RAM.
- Zielgröße ist die **Auslastung** (Erzeugung geteilt durch installierte Leistung). Im Betrieb
  wird mit der aktuellen Leistung zurück in GW gerechnet. Installierte Leistung: Monatswerte
  (Energy-Charts oder Marktstammdatenregister), weil die SMARD-Jahreswerte zu niedrig sind
  (siehe [phase0.md](phase0.md)).
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

Weiter-Kriterium: an Tag 1 bis 6 mindestens 20 % weniger MAE als die bessere einfache
Messlatte, Trefferquote zwischen 75 und 85 %.

**Geändert am 2026-11-03 (Entscheidung des Betreuers):** Das frühere Kriterium „an Tag 1
höchstens 20 % mehr Fehler als die Netzbetreiber“ ist kein Weiter-Kriterium mehr. Begründung:
Das Tool zeigt die Netzbetreiber-Prognose für Tag 1 ohnehin daneben (`official_forecast`), sein
eigentlicher Wert liegt bei Tag 2 bis 6, für die es keine öffentliche Prognose gibt. Der
Vergleich mit den Netzbetreibern wird weiter gemessen und berichtet. Anlass: Solar lag an Tag 1
bei 1,76 % gegen 1,20 % (Skill −0,47), siehe `docs/journal.md`.

**Entschieden am 2026-11-03 (Betreuer), Prüfpunkt B:** angenommen, obwohl Tag 6 (an Land 0,17,
auf See 0,15) und auf See im Abschlusstest auch Tag 5 unter 0,2 Skill liegen. Ausgleich: Jede
Antwort des Tools trägt einen festen Hinweis, dass es Modellschätzungen sind (`model_notice`),
und jedes Intervall eine Gütestufe aus den gemessenen Werten (`quality`: hoch ab 0,4, mittel ab
0,2, gering darunter; maßgeblich ist der schlechtere Wert aus rollierender Prüfung und
Abschlusstest). Dazu kommt das Tool `describe_forecast_model` (Abschnitt 7).

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

Ergänzt am 2026-11-03 (Wunsch des Betreuers):

- `model_notice` in jeder Antwort und als erste Textzeile: Die Werte sind Schätzungen eines
  Modells, keine Messung und keine amtliche Prognose.
- `quality` je Intervall (siehe Abschnitt 4).
- Zweites Tool `describe_forecast_model`: kurze technische Beschreibung (Daten, Merkmale,
  Verfahren, Vorlauf, Kalibrierung, Prüfung, Fehler je Quelle und Vorlauftag, Grenzen). Alle
  Zahlen darin kommen aus `models/modell.json`, das der Export aus den Kennzahl-Dateien erzeugt;
  nichts davon wird von Hand geschrieben.

Verhalten am Rand:

- Zeitraum über 6 Tage hinaus: Beginn nach dem Horizont ist ein Fehler mit dem letzten möglichen
  Zeitpunkt; reicht nur das Ende darüber, wird gekürzt (`complete: false` und Hinweis), damit
  die Standardanfrage „bis in 6 Tagen“ nicht scheitert
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

**Umgesetzt in Phase 5 (2026-11-03), mit zwei Abweichungen:**

- Das Neu-Training läuft nicht als GitHub-Workflow, sondern als systemd-Timer auf der
  Trainingsmaschine (`scripts/monatlich.sh`, am 3. jedes Monats). Gründe: Die Trainingsdaten
  liegen nicht im Repository, ein frischer Runner müsste jeden Monat das ganze Archiv neu
  laden (rund 10.000 Einheiten Open-Meteo), und das Training braucht die Sandbox der Maschine.
  Ablauf: nur neue Tage nachladen, rollierende Prüfung über alle Monate, Schranke für den
  neuesten Monat (Trefferquote 65 bis 95 %, MAE höchstens das 1,6-fache des Mittels, Skill über
  alle Monate positiv), Export, Vergleichsdaten. Besteht alles, pusht das Skript einen Branch
  `modelle/<version>` nach smard-mcp, nachdem dort die Tests mit den neuen Dateien gelaufen
  sind. Statt eines Pull Requests (der Deploy-Key kann keine anlegen) öffnet der Betreuer ihn.
- Das Monitoring rechnet in smard-mcp selbst (`dist/monitor.js`, täglicher Timer auf der
  Web-Maschine): Es nimmt die archivierten Vorhersagen, rechnet mit genau dem ausgelieferten
  Code nach, was das Tool geantwortet hätte, und vergleicht mit SMARD. Ergebnis als
  `recent_accuracy` in `forecast_renewables` und `describe_forecast_model`. Das Archiv speichert
  dafür seit 2026-11-03 auch das Datenende jedes Laufs (`laeufe_ende`); ältere Dateien nutzen
  den Fahrplan des DWD.

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

**Phase 6 (seit 2026-11-03):** smard-mcp 1.4.0 mit Modell 2026.11.02 auf `main` (c6eefbc),
Ausrollen auf die Web-Maschine durch den Betreuer. Das monatliche Neu-Training baut seine
Branches ab jetzt auf `main`. Das npm-Paket bleibt bis Prüfpunkt C bei 1.3.0.

**Prüfpunkt C** (Vorschlag, Entscheidung beim Betreuer), frühestens nach 14, regulär nach
28 Tagen Monitoring, je Quelle und Vorlauftag mit mindestens 7 Tagen vergleichbarer Stunden:

1. Trefferquote p10 bis p90 zwischen 70 und 90 %.
2. MAE höchstens das 1,5-fache des MAE aus der rollierenden Prüfung (`models/modell.json`).
3. Betrieb: täglicher Smoke-Test grün; Warnungen wegen veralteter Wetterdaten an höchstens
   2 Tagen.

Verfehlt ein Vorlauftag Punkt 1 oder 2, wird seine Gütestufe gesenkt oder er aus dem Tool
genommen, bevor das npm-Paket erscheint.

Erst wenn das Solar-Modell an Prüfpunkt A die Messlatten schlägt, entsteht Code in smard-mcp.
Termine sind bewusst offen.

### Prüfliste Phase 0

Erledigt am 2026-11-02, Ergebnisse in [phase0.md](phase0.md). Offen ist nur die Lizenz der
Energy-Charts-Daten für die installierte Leistung.

## 9. Risiken

| Risiko | Folge | Gegenmaßnahme |
|---|---|---|
| Lücken im ICON-Archiv | weniger Trainingsdaten | Prüfung in Phase 0, Rückfallebene aus Abschnitt 2 |
| Abregelung bei negativen Preisen | Erzeugung unter dem Wetterwert | Wochentag und Feiertag als Merkmal, Hinweis in `notes` |
| Zubau nur als Jahreswert | systematischer Versatz, vor allem Solar | Monatswerte von Anfang an |
| seltene Wetterlagen | grobe Ausreißer | Quantile, Winter getrennt bewertet |
| Open-Meteo ändert Bedingungen oder fällt aus | keine Prognose | Cache mit `warnings`, langfristig DWD Open Data als zweite Quelle |
| Lizenz | freie API nur nicht-kommerziell | smard-mcp bleibt kostenlos und ohne Werbung; sonst API-Key-Tarif |

Nicht in Version 1: Anteil an der Last (bräuchte eine eigene Verbrauchsprognose), Regelzonen.
