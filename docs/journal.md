# Projekttagebuch

Chronologisch, neueste Einträge unten. Jeder Schritt, jede Entscheidung und jeder
Fehlschlag mit Ursache, damit die Entstehung später nachvollziehbar ist. Zeiten in UTC.

Wie die Einträge aufgebaut sind:

- **Ziel**: was erreicht werden sollte
- **Gemacht**: was tatsächlich gelaufen ist (Befehle, Skripte, Commits)
- **Ergebnis**: Zahlen und Befunde
- **Fehlschlag**: was nicht geklappt hat, warum, und wie es gelöst wurde
- **Gelernt**: was man beim nächsten Mal anders oder genauso machen würde

Rohprotokolle der Skripte liegen in `data/logs/<skript>.log` (nicht im Git, jede Zeile mit
Zeitstempel).

---

## 2026-11-02

### 08:00 Ausgangslage

**Ziel:** Prüfen, ob sich das Konzept (Prognose Solar und Wind 1 bis 7 Tage, LightGBM-Quantile,
neues smard-mcp-Tool `forecast_renewables`) umsetzen lässt. Vorerst nur Planung.

**Gemacht:** Das Repo `akquisio-dev/smard-forecast` war leer. Statt nur zu planen, wurde die
größte offene Frage des Konzepts (gibt es ICON-Vorhersagen mit langem Vorlauf ab 2024?)
sofort mit ein paar Stichproben-Abrufen an die Open-Meteo Previous Runs API geprüft. Das
kostet Minuten und kann den ganzen Plan kippen, deshalb zuerst.

**Ergebnis:**

- `icon_seamless` und `dwd_icon_seamless` liefern identische Werte.
- Am 15.01.2024 gibt es noch keine Werte mit Vorlauf, ab Februar 2024 lückenlos.
  Genauer: Tag 1 ab 2024-01-19, Tag 6 ab 2024-01-24.
- **`previous_day7` ist nie gefüllt**, weder 2024 noch 2025 noch 2026. ICON global rechnet
  nur 180 h voraus, ein Lauf von vor 7 Tagen reicht also nicht mehr bis in den Zieltag.
- Die Live-Vorhersage reicht etwa 7,5 Tage.

**Entscheidung:** Version 1 nur bis Tag 6. Tag 7 erst, wenn ein eigenes Archiv
(gespeicherte Live-Vorhersagen) ein Jahr umfasst. Deshalb soll das Archiv früh starten.

**Gelernt:** Die riskanteste Annahme eines Plans zuerst gegen die echte Datenquelle prüfen,
nicht gegen die Dokumentation. Die Doku sagte „ab Januar 2024", tatsächlich fehlt Tag 7 ganz.

### 08:14 Plan ins Repo

**Gemacht:** Deploy-Key `smard_forecast_deploy` erzeugt (nur dieses Repo, Schreibrecht), SSH-Alias
`github-smard-forecast`. `docs/PLAN.md`, `README.md`, `LICENSE` (MIT) angelegt.
Commit `f151cfd`.

### 08:20 Phase 0: Was steckt hinter „Tag N"?

**Ziel:** Genau verstehen, welcher Lauf `previous_dayN` ist, damit Training und Betrieb
dieselbe Vorlaufzeit meinen.

**Gemacht:** Vergleich mit der Single Runs API (einzelne Läufe mit bekanntem Startzeitpunkt).
Für den 20.10.2026 alle Läufe der Woche davor geladen und Wert für Wert verglichen.

**Ergebnis:**

- Tag 3: exakt der Lauf 72 bis 77 h vorher (Läufe alle 6 h).
- Tag 6: exakt der Lauf 144 bis 150 h vorher (ICON global, Läufe alle 12 h).
- Also: `previous_dayN` = neuester Lauf, der mindestens N mal 24 h vor der Stunde startete.

**Fehlschlag 1:** Tag 1 passte zu **keinem** Einzellauf, auch nicht bei stündlichem Durchsuchen
von 18 bis 33 h Vorlauf. Die Werte weichen nur um Zehntelgrade ab. Wahrscheinliche Ursache:
Open-Meteo hat für die ersten 48 h inzwischen ICON-D2-RUC (stündliche Läufe) in
`icon_seamless`; die Single Runs API meldete bei Fehlern genau dieses Modell
(`dwd_icon_d2_ruc_native_15min`). Nicht endgültig geklärt.
**Umgang:** Für das Training unkritisch, die Vorlaufzeit stimmt näherungsweise. Das eigene
Archiv speichert deshalb die Laufzeitpunkte aller ICON-Modelle mit, auch RUC.

**Fehlschlag 2:** Die Single Runs API wäre die sauberste Trainingsquelle (exakter Laufzeitpunkt),
führt Läufe aber erst **ab Mai 2026**. Für das Training zu kurz, nur für Prüfungen brauchbar.

### 08:35 Phase 0: SMARD

**Gemacht:** `scripts/phase0_smard.py` (später umbenannt in `smard_laden.py`) lädt Erzeugung
und Netzbetreiber-Prognose stündlich ab 2024 sowie die installierte Leistung.

**Ergebnis:**

- Erzeugung Solar, Wind an Land, Wind auf See: lückenlos.
- Netzbetreiber-Prognose: ein Tag fehlt (23.10. 22 Uhr bis 24.10.2026, Solar und Wind an Land).
- **Installierte Leistung bei SMARD zu niedrig.** Probe: maximale Auslastung je Jahr. Solar fiel
  von 0,61 (2024) auf 0,56 (2026), Wind auf See stieg von 0,88 auf 0,92. Das ist kein echter
  Trend, sondern ein Nenner, der hinter dem Zubau herhinkt. Vergleich mit Energy-Charts
  (Fraunhofer ISE, monatlich): Solar 103 statt 120 GW, Wind auf See 9,2 statt 11,7 GW.

**Entscheidung:** Monatswerte von Energy-Charts als Nenner, für Solar die AC-Leistung
(Wechselrichter begrenzen die Einspeisung).

**Offen:** Lizenz von Energy-Charts. Die Seite „publishing notes" ist eine JavaScript-Seite und
ließ sich ohne Browser nicht lesen. Rückfall: eigene Monatssummen aus dem
Marktstammdatenregister.

**Gelernt:** Eine Plausibilitätsprüfung über Jahre (maximale Auslastung) deckt einen falschen
Nenner sofort auf. Ohne sie hätte das Modell einen Scheintrend gelernt.

### 08:40 Phase 0: Wetterorte und Lückenprüfung

**Gemacht:** 40 Wetterorte in `config/orte.toml` festgelegt (21 Solar, 14 Wind an Land, 7 auf
See; Magdeburg und Cottbus zählen für beides). `scripts/phase0_wetter.py` prüft je Ort den
ganzen Zeitraum, je Vorlauftag 1 bis 6.

**Fehlschlag 3:** Der erste Lauf brach nach 11 Orten ab mit
`json.decoder.JSONDecodeError: Expecting value: line 1 column 1`. Open-Meteo hatte eine leere
Antwort geschickt.
**Ursache:** Open-Meteo zählt große Abrufe mehrfach (ab 10 Variablen bzw. 14 Tagen anteilig).
Ein Abruf mit 12 Spalten über ein Jahr zählt rund 30-fach. Bei 3 s Abstand waren das rund 620
Einheiten pro Minute, das Limit liegt bei 600.
**Lösung:** Abstand 10 s, leere Antworten gelten als vorübergehender Fehler und werden
wiederholt, jede Antwort wird gespeichert (`data/phase0/roh/`), damit ein Abbruch nicht den
ganzen Fortschritt kostet. Der zweite Lauf ging durch.

**Gelernt:** Lange Abrufserien von Anfang an fortsetzbar bauen. Die Ratenlimits nach
gewichteten Einheiten rechnen, nicht nach Anzahl der Abrufe.

**Ergebnis:**

- Ein einziger Ausfall im Archiv: 10. bis 13.04.2026, an allen Orten gleich, Tag 2, 4, 5, 6.
- `wind_speed_100m` beginnt später als die anderen Variablen: Tag 1 ab 2024-02-16, Tag 6 ab
  2024-02-21. **Trainingsbeginn daher 2024-02-22.**
- `cloud_cover_low` und `snow_depth` gibt es im Archiv gar nicht.
- Alle 7 Offshore-Orte liegen auf 0 m Höhe.

Commit `163d455`, Ergebnisse in `docs/phase0.md`.

### 18:20 Phase 1: Download und Archiv

**Gemacht:**

- `sf/openmeteo.py`: Variablen je Ortstyp (6 für Solar, 6 für Wind) und die Zählweise von
  Open-Meteo als Funktion `gewicht()`.
- `scripts/download.py`: lädt je Ort und Kalenderjahr ein Stück (120 Stücke, etwa 10.500
  Einheiten) nach `data/wetter/`, mit eigener Buchführung der Limits (9.000 am Tag, 4.500 je
  Stunde, 450 je Minute) und Warten bis zum nächsten UTC-Tag. Vorher an einem 2-Tage-Zeitraum
  getestet (288 Zeilen, Mittelwerte je Vorlauftag plausibel).
- `scripts/kapazitaet.py`: Monatswerte von Energy-Charts.
- `archiv/archiv.py`: läuft stündlich auf dem Server, liest die Laufzeitpunkte aus
  `meta.json` von Open-Meteo und holt nur bei neuem Lauf die 8-Tage-Vorhersage aller Orte in
  einem Abruf. Lokal getestet: 95 KB je Abruf.
- Posten `smard-forecast` in der nächtlichen Dienste-Sicherung.

**Entscheidung:** Download auf der großen Maschine (dort wird auch trainiert), Archiv auf der
Web-Maschine (läuft dauerhaft, braucht kaum Ressourcen). Der Server hat nur Python 3.10, also
kein `tomllib`: das Archiv-Skript nutzt nur die Standardbibliothek, die Ortsliste wird beim
Ausrollen als JSON erzeugt.

**Fehlschlag 4:** Das Ausrollen auf die Web-Maschine (`archiv/ausrollen.sh`) wurde von der
Freigabe-Prüfung von Claude Code abgelehnt (Schreiben auf einem fremden Server). Joey rollt es
selbst aus.

**Hinweis zum Download:** Beim Start wurde vorsichtshalber eingetragen, dass heute schon 4.500
Einheiten verbraucht seien (wegen der Lückenprüfung am Morgen). Rückblickend lag die Prüfung
über eine Stunde zurück, das Stundenfenster wäre also frei gewesen; der Download startet
dadurch eine Stunde später als nötig. Harmlos, aber zu vorsichtig.

Commit `552f040`, Beschreibung in `docs/phase1.md`.

### 18:36 Protokollierung

**Ziel:** Jeder Schritt und jeder Fehlschlag soll später nachvollziehbar sein (Wunsch von Joey).

**Gemacht:**

- Dieses Tagebuch angelegt und die bisherigen Schritte nachgetragen.
- `sf/log.py`: alle Skripte schreiben jede Ausgabe mit UTC-Zeit zusätzlich nach
  `data/logs/<skript>.log`.
- Der Download-Dienst wurde neu gestartet, damit er schon mit Logdatei läuft. Er hatte bis
  dahin noch nichts geladen, es ging nichts verloren. Das Journal des ersten Starts liegt in
  `data/logs/download-erster-start.log`.
