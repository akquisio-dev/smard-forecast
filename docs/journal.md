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
Freigabe-Prüfung von Claude Code abgelehnt (Schreiben auf einem fremden Server). Der Betreuer rollt es
selbst aus.

**Hinweis zum Download:** Beim Start wurde vorsichtshalber eingetragen, dass heute schon 4.500
Einheiten verbraucht seien (wegen der Lückenprüfung am Morgen). Rückblickend lag die Prüfung
über eine Stunde zurück, das Stundenfenster wäre also frei gewesen; der Download startet
dadurch eine Stunde später als nötig. Harmlos, aber zu vorsichtig.

Commit `552f040`, Beschreibung in `docs/phase1.md`.

### 18:36 Protokollierung

**Ziel:** Jeder Schritt und jeder Fehlschlag soll später nachvollziehbar sein (Wunsch des Betreuers).

**Gemacht:**

- Dieses Tagebuch angelegt und die bisherigen Schritte nachgetragen.
- `sf/log.py`: alle Skripte schreiben jede Ausgabe mit UTC-Zeit zusätzlich nach
  `data/logs/<skript>.log`.
- Der Download-Dienst wurde neu gestartet, damit er schon mit Logdatei läuft. Er hatte bis
  dahin noch nichts geladen, es ging nichts verloren. Das Journal des ersten Starts liegt in
  `data/logs/download-erster-start.log`.

### 18:41 Archiv-Job ausgerollt

**Gemacht:** Der Betreuer hat `archiv/ausrollen.sh` selbst ausgeführt. Der Systemnutzer
`smard-forecast` wurde angelegt, der Timer `smard-forecast-archiv.timer` aktiviert, und der
erste Lauf hat gespeichert: `2026/11/02/20261102T1841Z.json.gz`, 95.359 Bytes, Läufe ICON-D2
und ICON-EU 15 UTC, ICON global 12 UTC, ICON-D2-RUC 17 UTC.

**Geprüft:** Der Timer steht auf stündlich (nächster Lauf 19:36). Der Abzug für die
Dienste-Sicherung funktioniert (`tar` über ssh, rund 95 KB). Damit ist die Sicherung heute
Nacht um 04:00 nicht mehr gefährdet.

**Ergebnis:** Ab jetzt wächst das eigene Archiv. Nach einem Jahr reicht es für Tag 7.

### abends: Projektbericht als PDF

**Ziel:** Ein ausführliches Dokument über das ganze Projekt, technisch Schritt für Schritt.

**Gemacht:**

- `docs/bericht/abbildungen.py` erzeugt 15 Abbildungen aus den echten Daten unter `data/`
  (Karte, Leistung, Auslastung, Datenverfügbarkeit, Beispielwoche, Klimatologie) und
  Ablaufdiagramme. Farben aus einer geprüften Palette, je Quelle immer dieselbe Farbe.
  Schematische Abbildungen sind im Titel als „Schema" gekennzeichnet.
- `docs/bericht/bericht.py` baut daraus mit reportlab
  `docs/bericht/smard-forecast-projektbericht.pdf` (32 Seiten, 16 Kapitel, Inhaltsverzeichnis
  mit Lesezeichen).
- Kartenumrisse aus Natural Earth (gemeinfrei) in `docs/bericht/assets/`.

**Fehlschlag:** Der erste Kartenumriss kam aus einem GitHub-Repo, dessen Quelle (DIVA-GIS) nur
nicht-kommerzielle Nutzung erlaubt. Für ein öffentliches Repo ersetzt durch Natural Earth.

**Fehlschlag:** Erste Fassung der Diagramme hatte überlappende Beschriftungen (Architektur,
Ablauf des Archivs, Legenden über Kurven). Jede Abbildung wurde gerendert und angesehen, dann
korrigiert. Im PDF standen Überschriften allein am Seitenende und die Kopfzeile zeigte das
Kapitel der Vorseite; beides behoben.

**Gelernt:** Abbildungen immer rendern und ansehen, nicht nur erzeugen. Bei öffentlichen
Repos auch die Lizenz von Hilfsdaten (Kartenumrisse) prüfen. Personennamen gehören nicht in
öffentliche Dokumente; sie wurden durch „Betreuer" ersetzt.

**Nachtrag:** Der Betreuer möchte das PDF nicht im öffentlichen Repo. Es liegt nur lokal
(`docs/bericht/*.pdf` steht in `.gitignore`); im Repo bleiben nur die Skripte, die es erzeugen.
Das Entfernen aus der Git-Geschichte (Force-Push) wurde von der Freigabe-Prüfung von Claude
Code abgelehnt und bleibt dem Betreuer überlassen.

### abends: Bericht als Lehrbuch, Zeitversatz entdeckt

**Ziel:** Der Bericht soll so ausführlich sein, dass man ohne Vorwissen jeden Schritt versteht
(Wunsch des Betreuers): jeder Fachbegriff bei erster Verwendung erklärt, Mathematik hergeleitet.

**Gemacht:**

- `docs/bericht/lehrgrafiken.py`: 20 Lehrgrafiken und alle Zahlen des Textes aus den echten
  Daten (Phase-0-Rohdaten und SMARD), gespeichert in `abb/zahlen.json`. Kleine Lernbeispiele
  mit LightGBM (ausdrücklich nicht das Projektmodell).
- `docs/bericht/bericht.py` neu: Kapiteltexte in `docs/bericht/kapitel/*.txt` mit einfacher
  Auszeichnung, Formelsatz über matplotlib, Begriffskästen, aus denen das Glossar entsteht.
- Ergebnis: 94 Seiten, 6 Teile, 25 Kapitel und 4 Anhänge, 35 Abbildungen, 46 Formeln,
  105 erklärte Begriffe. Das PDF bleibt lokal.

**Ergebnis (für das Projekt wichtig):** Strahlung und Solarstrom sind um eine Stunde versetzt
gestempelt; siehe Nachtrag in `docs/phase0.md`.

**Fehlschlag:** Das erste Lernbeispiel zur Überanpassung (ein einzelner, immer größerer Baum)
zeigte keine Überanpassung, weil der Baum bei 12.500 Stunden nicht weit genug wächst. Neu
gebaut mit sechs Wochen Daten und 600 Bäumen: Trainingsfehler fast null, Prüffehler bleibt bei
rund 2 %.

**Fehlschlag:** Mehrere LaTeX-Konstrukte (`cases`, `\arg\min`) kann der Formelsatz von
matplotlib nicht; umgeschrieben. Kästen, die länger als eine Seite waren, brachen den Satz ab;
Kästen bestehen jetzt aus einer Tabellenzeile je Baustein und können umbrechen.

**Gelernt:** Erklären zwingt zum Nachrechnen; beim Nachrechnen fiel der Zeitversatz auf.

## 2026-11-03

### 01:12 Trainingsdownload fertig

**Ergebnis:** Alle 120 Stücke geladen (40 Orte, je drei Kalenderjahre, Tag 1 bis 6,
22.02.2024 bis 01.11.2026), kein Stück ganz leer. Der Download hat am 2.11. um 19:42 UTC das
Tageskontingent erreicht, selbst bis 00:05 UTC gewartet und den Rest ohne Fehler geladen.
Protokoll: `data/logs/download.log`.

### 07:06 Prüfliste des Betreuers eingearbeitet (vier Punkte)

**Ziel:** Vier Einwände des Betreuers zu Plan und Bericht prüfen und umsetzen.

**1. Vorlauf Training gegen Betrieb (berechtigt, Fehler im Plan):** Im Training hat Tag N etwa
N·24 bis N·24+6 h Vorlauf. Der Plan wollte im Betrieb den Vorlauf auf ganze Tage abrunden; dann
wäre z. B. eine 95 h alte Vorhersage als Tag 3 (gelernt mit 72 bis 77 h) behandelt worden, mit
zu schmalen Bandbreiten. **Korrigiert:** zwischen Tag N und N+1 interpolieren,
x = (L − 3 h)/24 h. Geändert in `docs/PLAN.md` (Abschnitt 2), `docs/phase0.md` und im Bericht
(Kapitel „Das Vorlaufzeit-Problem“, neuer Abschnitt mit Rechenbeispielen; Phase 4 Schritt 3).
Die Prüfung mit der Single Runs API (Trefferquote je Vorlauf in Stunden) ist für Phase 4
eingeplant.

**2. Installierte Leistung der letzten Monate (berechtigt):** Energy-Charts meldete für 11/2026
genau den Wert von 10/2026. `scripts/kapazitaet.py` speichert jetzt jeden Abruf unverändert
unter `data/kapazitaet_staende/` (um spätere Korrekturen zu messen) und schreibt Solar und Wind
an Land nach dem letzten echten Zuwachs (mindestens 20 % des typischen) mit dem Mittel der 6
Monate davor fort (Spalten `geschaetzt_*`). Wind auf See wird nicht fortgeschrieben: Dort kommt
Zubau in Sprüngen, und monatelanger Stillstand ist echt (06/2025 = 12/2024).
**Fehlschlag:** Die erste Fassung erkannte bei Solar 2 MW Änderung im November als „echten
Zuwachs“; ersetzt durch eine relative Schwelle.

**3. Nachtgrenze Solar (berechtigt):** Die Sonnenhöhe nur für 51° N/10° O ließ 563 Stunden mit
Solarstrom bei „Nacht“ weg (0,126 % der Energie). Neu: `sf/sonne.py` mit `max_sonnenhoehe()`
über alle 21 Solar-Orte; ausgeschlossen wird nur, wenn an keinem Ort die Sonne auf ist.

**4. Läufe als root (berechtigt):** Das Repository liegt jetzt unter `/srv/smard-forecast`
(`/root/smard-forecast` ist ein Verweis darauf). Systembenutzer `smard-forecast` (ohne
Anmeldung) besitzt nur `data/`. `scripts/als-dienst.sh` startet jedes Skript als dieser Benutzer
in einer systemd-Sandbox: nur `data/` beschreibbar, kein Zugriff auf Home-Verzeichnisse, keine
neuen Rechte, höchstens 4 GB Speicher und 6 Kerne. Probelauf erfolgreich.

### 07:08 Phase 2, erster Lauf mit den Startwerten

**Gemacht:** `sf/merkmale.py` (Trainingstabelle: 21 Solar-Orte × 6 Variablen zeitlich
ausgerichtet, Strahlung auf S+1 h, Momentanwerte auf die Stundenmitte gemittelt; Mittel über
Orte; Stunde und Tag im Jahr als Sinus/Kosinus; Sonnenhöhe Mitte und Maximum; Wochentag;
bundesweite Feiertage über `sf/kalender.py`), `scripts/phase2_solar.py` (je Quantil ein
LightGBM-Modell mit den Startwerten aus dem Plan; rollierend 03/2025 bis 07/2026; Abschluss
08 bis 10/2026). Laufzeit 147 s in der Sandbox.

**Ergebnis (Abschlusstest, erster und damit gültiger Blick, eingefroren in
`data/phase2/solar_kennzahlen_lauf1_startwerte.json`):**

| Tag | MAE % | Treffer % | Skill gegen Klima/Persistenz |
|---|---|---|---|
| 1 | 1,50 | 77,7 | 0,64 (Netzbetreiber: 1,01 %, Skill −0,50) |
| 2 | 1,75 | 76,4 | 0,58 |
| 3 | 2,03 | 75,2 | 0,51 |
| 4 | 2,30 | 75,5 | 0,45 |
| 5 | 2,83 | 76,1 | 0,32 |
| 6 | 3,37 | 69,0 | 0,19 |

Rollierend (17 Monate): MAE Tag 1 1,75 % bis Tag 6 3,28 %, Trefferquote nur 69 bis 73 %,
Netzbetreiber an Tag 1 1,22 % (Skill −0,44).

**Prüfpunkt A mit Startwerten: nicht bestanden.** Kriterium 1 (Skill ≥ 0,2) erfüllt, im
Abschluss Tag 6 knapp darunter (0,19). Kriterium 2 (Tag 1 höchstens 20 % schlechter als die
Netzbetreiber) klar verfehlt. Kriterium 3 (Trefferquote 75 bis 85 %) rollierend verfehlt.

**Fehlschlag:** Die Persistenz-Messlatte zeigte an Tag 5 und 6 rund 20 % Fehler. Ursache:
`vorlauf_tag` ist int8, und `(n + 1) * 24` lief bei 144 und 168 über (−112, −88); verglichen
wurde dadurch mit Nachtstunden. Behoben (`astype("int64")`). Die Skill-Werte waren nicht
betroffen, weil Klimatologie an diesen Tagen ohnehin die bessere Messlatte war.

**Festgelegt:** Der Abschlusstest ist damit verbraucht. Alle weiteren Entscheidungen fallen
nur noch auf den rollierenden Monaten; ein späterer Blick auf August bis Oktober wird
ausdrücklich als zweiter Blick gekennzeichnet. Wirklich unberührt sind ab jetzt erst die Daten
ab November 2026.

### 07:15 Phase 2, Abstimmung auf den rollierenden Monaten

**Gemacht:** `scripts/phase2_abstimmung.py`: 7 Tage Abstand zwischen Trainingsende und
Testmonat; Diagnose; Raster aus vier Einstellungen auf jedem dritten Monat; danach alle
rollierenden Monate mit der besten Einstellung und leckfreie Kalibrierung der Bandbreite
(konforme Quantilregression: Monat M lernt die Korrektur nur aus den Monaten davor).
Ergebnisse in `data/phase2/solar_abstimmung.json`. Laufzeit 10 Minuten.

**Ergebnis:**

- Diagnose: Mit den Startwerten liegt die Trefferquote im Training bei 81 %, im Testmonat März
  2026 bei 80,5 %. Die Quantile sind also gelernt; die zu schmalen Bänder in anderen Monaten
  kommen von Unterschieden zwischen den Monaten, nicht von zu wenig Training.
- Größere Modelle (31 oder 63 Blätter, 800 Bäume) sind schlechter: kaum besserer Median, aber
  viel schmalere Bänder (Trefferquote 55 bis 61 %). Die Startwerte bleiben.
- Mit Kalibrierung steigt die Trefferquote von 69 bis 73 % auf 84 bis 86 %, ohne dass sich der
  Median ändert; der Pinball-Verlust bleibt gleich oder wird minimal besser.
- Tag 1 gegen die Netzbetreiber bleibt unverändert: 1,76 % gegen 1,20 % (Skill −0,47).

**Stand Prüfpunkt A (rollierend, mit Kalibrierung):** Kriterium 1 erfüllt (Skill 0,57 bis 0,21),
Kriterium 3 erfüllt bis knapp darüber (83,7 bis 85,9 %), Kriterium 2 klar verfehlt. Ob
Kriterium 2 gelockert wird oder die Netzbetreiber-Prognose für Tag 1 als Merkmal dient,
entscheidet der Betreuer.

### 07:40 Entscheidung zu Prüfpunkt A

Der Betreuer hat entschieden: Kriterium 2 (Tag 1 gegen die Netzbetreiber) wird gelockert und ist
kein Weiter-Kriterium mehr, sondern nur noch eine berichtete Kennzahl (Begründung in
`docs/PLAN.md`, Abschnitt 4). Damit ist **Prüfpunkt A für Solar bestanden** (rollierend mit
Kalibrierung: Skill 0,57 bis 0,21, Trefferquote 83,7 bis 85,9 %). Bessere Merkmale (etwa ein
Klarhimmel-Index) kommen später, jedes nur, wenn es die rollierende Prüfung verbessert. Weiter
mit Phase 3 (Wind).

### 07:30 Phase 3, Wind an Land und Wind auf See

**Gemacht:** `scripts/phase3_wind.py` mit genau dem Verfahren von Solar: Startwerte, 7 Tage
Abstand, rollierend 03/2025 bis 07/2026, leckfreie Kalibrierung (CQR). Neu in
`sf/merkmale.py`: `tabelle_wind` (16 Orte an Land, 7 auf See; Windrichtung als Sinus und
Kosinus, kein Sonnenstand-Maximum). Der Abschlusstest 08 bis 10/2026 war für Wind unberührt und
wurde hier genau einmal benutzt; wie im Betrieb wird je Monat neu trainiert, seine Kalibrierung
kommt nur aus den rollierenden Monaten. Laufzeit 6 Minuten.

**Leckprüfung:** Die rollierenden Vorhersagen enden im Juli 2026; der Abschluss steht als ein
eigener „Monat“ hinter allen rollierenden, die Kalibrierung liest also nur 04/2025 bis 07/2026.
Ein Kommentar im Skript sprach fälschlich von „einem Modell“ für den Abschluss; korrigiert.

**Ergebnis (mit Kalibrierung; Skill gegen die bessere einfache Messlatte):**

| Quelle, Teil | Skill Tag 1 bis 6 | Trefferquote |
|---|---|---|
| an Land, rollierend | 0,72 0,65 0,57 0,44 0,30 **0,17** | 81,4 bis 82,6 % |
| an Land, Abschluss | 0,77 0,71 0,64 0,54 0,36 0,26 | 79,5 bis 83,8 % |
| auf See, rollierend | 0,62 0,57 0,48 0,37 0,25 **0,15** | 79,3 bis 81,6 % |
| auf See, Abschluss | 0,48 0,43 0,33 0,23 **0,12 0,03** | 83,8 bis **87,6 %** |

Nur berichtet: Tag 1 gegen die Netzbetreiber an Land 2,75 % gegen 1,77 % (Skill −0,55), auf
See 6,94 % gegen 5,36 % (−0,30). Ohne Kalibrierung liegt die Trefferquote bei 67 bis 75 %;
auf See im Winter auch mit Kalibrierung nur 69 bis 76 %.

**Stand Prüfpunkt B:** nicht erfüllt. An Land fehlt nur Tag 6 (0,17 statt 0,2), auf See Tag 6
rollierend (0,15) und im Abschluss Tag 5 und 6 (0,12 und 0,03); dort sind die Bänder auch zu
breit (über 85 %). Im Abschluss (August bis Oktober, ruhige Monate) ist die Klimatologie auf See
schwerer zu schlagen als sonst: ihr Fehler fällt von 18,5 auf 14,2 %, der des Modells kaum. Die Entscheidung über Prüfpunkt B trifft der Betreuer.

### 08:00 Entscheidung zu Prüfpunkt B

Der Betreuer will bei allen Modellwerten einen Hinweis, dass sie nur geschätzt sind, und ein
Tool, das die Funktionsweise des Modells kurz und technisch erklärt. Damit ist **Prüfpunkt B
angenommen** (Möglichkeit 1): Tag 6 und auf See Tag 5 bleiben drin, aber mit Gütestufe „low“.
Festgehalten in `docs/PLAN.md`, Abschnitte 4 und 7.

### 08:05 Phase 4: Betriebsmodelle, TypeScript-Auswertung, Tool

**Gemacht:**

- `sf/merkmale.py`: Die zeitliche Ausrichtung steht jetzt in einer eigenen Funktion
  `ausrichten`, dazu `lauf_merkmale` (Merkmale aus EINEM Wetterlauf, wie im Betrieb).
  `sf/betrieb.py`: Vorhersage im Betrieb (Interpolation der Vorlauftage, Kalibrierung,
  Nachtmaske). Beides ist die Referenz für die TypeScript-Fassung.
- `scripts/phase4_export.py`: je Quelle und Quantil ein Modell auf ALLEN Daten (bis
  1. November 2026), Kalibrierung je Vorlauftag aus allen Vorhersagen außerhalb der Stichprobe,
  Kennzahlen und Gütestufe je Vorlauftag aus den Dateien von Phase 2 und 3, Kapazität je Monat.
  Version `2026.11.01`, 2,3 MB JSON (im npm-Paket 0,8 MB gepackt).
- `scripts/phase4_vergleich.py`: holt die aktuelle Vorhersage aller 40 Orte, genau wie das Tool,
  und rechnet sie mit Python durch. Der Test in smard-mcp rechnet dieselbe Eingabe in TypeScript.
- smard-mcp, Branch `forecast` (778c3d8, nicht live): `forecast_renewables` und
  `describe_forecast_model`, Baumauswertung, Merkmale, Sonnenstand und Feiertage in TypeScript,
  Wetter-Abruf mit Cache bis zum nächsten Lauf und 12 Stunden Notbetrieb.

**Fehlschläge:**

- Die Single Runs API rechnet `icon_seamless` je Ort erst bei der Anfrage zusammen (30 bis 70 s
  je Ort). Ein Abruf für 40 Orte lief über jede Zeitgrenze und wiederholte sich still. Jetzt ein
  Abruf je Ort, 4 gleichzeitig, und nur jeder fünfte Tag. Dabei lief der alte Prozess als
  systemd-Einheit weiter, obwohl die Shell gestoppt war; von Hand beendet.
- Vorlaufzeit im Vergleichsskript um Faktoren falsch (−497.747 h statt −6 h): `asi8` liefert seit
  pandas 3 je nach Auflösung Mikrosekunden statt Nanosekunden. Ersetzt durch eine Rechnung über
  `Timedelta`. Das Training war nicht betroffen (es nutzt `asi8` nicht).
- Wind wich anfangs um bis zu 0,7 % der Kapazität ab, Solar gar nicht. Ursache: pandas bildet die
  Mittel über alle Orte in float32, TypeScript rechnete in float64; beim Luftdruck (um
  1000 hPa) reichen wenige Bits, um eine Baumgrenze zu kippen. TypeScript summiert jetzt ebenso
  in float32. Danach weichen alle drei Quellen um weniger als 1e-6 ab (so prüft es der Test).

**Ergebnis:** Probelauf mit echten Daten am 3. November, 9 Uhr: Für den Rest des Tages sagt das
Modell bei Solar 105,8 GWh voraus, die Netzbetreiber 105,1 GWh. Bei Wind an Land sind es 213,5
gegen 217,1 GWh, bei Wind auf See 61,1 gegen 44,0 GWh. Eine Rechnung dauert rund 150 ms.

### 09:20 Phase 4, Nachbesserungen nach Durchsicht

- Der HTTP-Server von smard-mcp baut je Anfrage einen neuen MCP-Server. Mit je einem eigenen
  Wetter-Client hätte jede Anfrage Open-Meteo gefragt (40 Einheiten, etwa 250 Anfragen am Tag bis
  zum Tageslimit). Jetzt teilen sich alle einen Client; ein Test prüft „zwei Server, ein Abruf“.
- `deploy/deploy.sh` kopierte nur `dist/`; ohne `models/` wäre der erste Aufruf gescheitert.
- Die Modellbeschreibung hatte doch noch Handgeschriebenes (Prüfzeiträume, welche Tage „low“
  sind, wer an Tag 1 besser ist). Alles kommt jetzt aus `modell.json`
  (`phase4_export.py --nur-meta` schreibt die Angaben, ohne neu zu trainieren). Dort steht auch,
  dass der Solar-Abschlusstest noch ohne Kalibrierung und ohne Abstand lief.
- Einzelläufe: nur noch alle 15 Tage (12 Läufe, je rund 14 Minuten). Probelauf der Auswertung auf
  dem ersten Lauf (1. Mai) lief durch; Ergebnisse erst mit allen Läufen.

**Offen:** Ergebnis der Interpolationsprüfung; Lizenz von Energy-Charts (die monatlichen
Kapazitäten stehen jetzt in `models/modell.json` auf dem öffentlichen Branch und kämen ins
npm-Paket); ein datumsabhängiger Test in smard-mcp (`compare_periods`) schlägt schon auf `main`
fehl und würde `npm run deploy` blockieren.

### 09:45 Bericht: Kapitel zu Phase 2 bis 4 neu

**Gemacht:** Die Kapitel 21 bis 23 des lokalen Projektberichts (PDF nicht im Repository) sind
als Ergebnisteil neu geschrieben: Versuchsaufbau mit formalem Validierungsschema, erster Lauf,
Diagnose (Unteranpassung gegen Verteilungsverschiebung), Hyperparameter-Raster, konforme
Quantilregression mit Herleitung und Grenzen, Ergebnisse und Entscheidungen zu den Prüfpunkten
A und B, Fehlerwachstum mit dem Vorlauf, Gain-Wichtigkeit, Betriebsmodelle, Gütestufen,
numerische Äquivalenz von Python und TypeScript, Schnittstelle, Tagesquantile als Summe.
Neues Skript `docs/bericht/ergebnisse.py` erzeugt 7 Ergebnisgrafiken und alle im Text
zitierten Zahlen aus `data/phase2`, `data/phase4` und `data/modell`; die Tabellen im Text
verweisen nur auf diese Schlüssel. Das Kriterium in Kapitel 15, Risiken, offene Fragen,
Zeitleiste, Fehlschläge, Formelsammlung und Quellen sind nachgezogen.

**Offen im Bericht:** das Ergebnis der Interpolationsprüfung (Abschnitt 23.4 sagt ausdrücklich,
dass es aussteht; die Grafik entsteht erst ab 12 geladenen Läufen).

### 10:30 Bericht: wissenschaftlicher Apparat

**Gemacht:** Der Bericht hat jetzt die Bestandteile einer wissenschaftlichen Arbeit:

- Kurzfassung und englisches Abstract vor dem Inhaltsverzeichnis (Zahlen aus den Ergebnisdateien).
- Abbildungs-, Tabellen- und Abkürzungsverzeichnis.
- Zitate im Autor-Jahr-Verfahren (`[@schluessel]` im Text, `docs/bericht/literatur.toml` mit
  46 Einträgen: Fachliteratur zu Quantilregression, Bewertung von Wahrscheinlichkeitsprognosen,
  Entscheidungsbäumen und Boosting, konformer Vorhersage, Validierung von Zeitreihen,
  Energieprognose, Solar- und Windphysik, Wettermodellen, Gleitkommaarithmetik sowie Daten,
  Dienste und Software). Ein unbekannter Schlüssel bricht den Bau ab; nicht zitierte Einträge
  werden gemeldet und nicht aufgeführt.
- Literaturverzeichnis am Ende von Teil V; der Anhang „Quellen und Lizenzen“ heißt jetzt „Daten,
  Software und Lizenzen“ und verweist auf das Verzeichnis.
- Zitierweise in Kapitel 1 erklärt; Stand der Phasen und wichtigste Befunde aktualisiert.

**Fehlschlag:** Das erste Einsetzen der Zitate brach nach der Hälfte ab, weil ein Anker doppelt
vorkam: Der Begriff „Gleitkommazahl“ war schon in Kapitel 19 erklärt, Kapitel 23 hatte einen
zweiten Begriffskasten dafür. Kapitel aus Git zurückgeholt, der zweite Kasten ist jetzt normaler
Text mit Rückverweis. Danach verlangte das PDF-Inhaltsverzeichnis (Outline), dass Kapitel ohne
Nummer auf der obersten Ebene stehen; eigene Stufe dafür.

**Grundsatz:** Ins Literaturverzeichnis kamen nur Arbeiten, deren bibliographische Angaben
sicher bekannt sind; wo Seitenzahlen unsicher waren (Konferenzbände), fehlen sie lieber.

### 11:00 Literatur online geprüft

**Gemacht:** Alle 46 Einträge in `docs/bericht/literatur.toml` geprüft: Zeitschriftenartikel
und Bücher über die Crossref-Schnittstelle (Titel, Verfasser, Jahr, Zeitschrift, Band, Heft,
Seiten), Konferenzbeiträge gegen die NeurIPS-Proceedings, Bücher ohne DOI gegen
Bibliothekskataloge, Internetquellen per Abruf. 29 Einträge haben jetzt eine geprüfte DOI.

**Korrekturen:**

- Betz (1920): „26“ ist das Heft, nicht der Band der Zeitschrift.
- Romano u. a. (2019) und Ke u. a. (2017): Seitenzahlen ergänzt (3543–3553, 3146–3154).
- Harris u. a. (2020): Heft 7825 ergänzt; Strobl u. a. (2007): Heft 1 ergänzt.
- IEEE 754-2019: Verlagsort Piscataway, nicht New York.
- Manwell u. a. (2009): Verlagsort uneinheitlich belegt (Hoboken oder Chichester), deshalb weggelassen.

**Befund:** In Spencer (1971) steht in der Reihe für die Zeitgleichung die Konstante 0,000075;
nach einer späteren Korrektur des Verfassers muss sie 0,0000075 lauten. `sf/sonne.py` und
`src/forecast/sun.ts` in smard-mcp verwenden den gedruckten Wert. Unterschied knapp eine
Sekunde, Sonnenhöhe weniger als 0,004°; ohne Bedeutung für die Modelle. Die Konstante bleibt
bis zum nächsten Neu-Training (Training und Betrieb müssen identisch rechnen), Kommentar im
Code und Hinweis in Kapitel 6 des Berichts.

### 09:50 Phase 5: monatliches Neu-Training und Überwachung

**Gemacht:**

- `scripts/monatlich.py` (Sandbox): lädt neue Tage nach (download.py hängt nur noch an), prüft
  rollierend über alle Monate ab 03/2025 bis zum letzten vollständigen Monat, legt die Schranke an
  (Trefferquote 65 bis 95 %, MAE höchstens 1,6 × Mittel der Vormonate, Skill > 0 je Vorlauftag),
  exportiert danach Modell und Vergleichsdaten. Status in `data/betrieb/status.json`.
- `phase4_export.py` nimmt Kennzahlen, CQR und Zeitraum aus `data/betrieb/<quelle>_rollierend.parquet`,
  wenn vorhanden.
- `scripts/monatlich.sh`: baut in smard-mcp den Branch `modelle/<version>` auf `origin/forecast`,
  lässt tsc und die Paritäts-/Tooltests laufen und pusht nur, wenn sie bestehen. Gemergt wird von Hand.
- systemd-Timer `smard-forecast-monatlich` (3. jedes Monats, 03:30 UTC) in `scripts/systemd/`.
- Überwachung in smard-mcp (0233a8f): `forecast-monitor` rechnet täglich aus dem Archiv nach, was das
  Tool geantwortet hätte, vergleicht mit SMARD, Ergebnis als `recent_accuracy` in beiden Tools.
- `archiv/archiv.py` speichert zusätzlich das Datenende je ICON-Lauf (`laeufe_ende`).

**Probelauf** (`monatlich.sh --ohne-nachladen --ohne-push`): Exit 0, 571 s Python-Teil, Modell
2026.11.02 mit Prüfung bis 2026-10, 12/12 Tests im Branch bestanden, Commit c89ca7d nur lokal.
Oktober 2026 Tag 1/6: Wind an Land Skill 0,83/0,35, Wind auf See 0,61/0,10, alle Trefferquoten
zwischen 70 und 90 %.

**Fehlschlag:** Timer konnte nicht aus der Sitzung installiert werden (Freigabe fehlt); Joey
installiert ihn. Unter systemd fehlen HOME (SSH-Alias für den Push) und der nvm-Pfad für npx;
beides in der Unit gesetzt.

### 10:15 Phase 6: Ausrollen vorbereitet

**Gemacht:**

- Live-Probe gegen Open-Meteo mit dem gebauten Server: erste Anfrage 0,6 bis 0,7 s, danach 7 ms
  aus dem Cache, 131 MB Speicher (Dienst hat 256 MB). Day-Werte des laufenden und letzten Tags
  sind Teiltage; der Text sagt das jetzt („only 14 of 24 hours“).
- Lizenz Energy-Charts geklärt: Laut Beschreibung der Energy-Charts-API stehen die Daten, wenn
  nicht anders angegeben, unter CC BY 4.0 mit Nennung von Energy-Charts.info. Nennung in der
  Quellenangabe des Tools und in der README ergänzt. Damit ist der letzte offene Punkt aus
  Phase 0 erledigt.
- smard-mcp: README (Abschnitt Forecast, Datenschutz Open-Meteo, Datenquellen, Betrieb),
  Smoke-Test ruft `forecast_renewables` auf, Version 1.4.0, Modelle 2026.11.02 aus dem
  monatlichen Branch übernommen, `forecast` per Fast-Forward nach `main` (c6eefbc).
  179 Tests, Smoke-Test gegen lokalen HTTP-Server 12/12.
- `monatlich.sh` baut ab jetzt auf `main`. Kriterien für Prüfpunkt C in PLAN.md.

**Fehlschlag:** `npm run deploy` aus der Sitzung blockiert (Freigabe fehlt), Joey rollt aus.
Bis dahin schlägt der tägliche Smoke-Test der GitHub-Action fehl, weil er die neuen Tools erwartet.
`npm install --package-lock-only` hätte nebenbei `libc`-Felder im Lockfile entfernt (andere
npm-Version); zurückgenommen, nur die Versionszeilen geändert.

### 10:35 Interpolationsprüfung abgeschlossen

**Gemacht:** Einzelläufe-Download endete mit 12 von 13 Läufen; der Lauf vom 28.10. 12 UTC lieferte
bei der Single Runs API auch nach vier Versuchen je Ort nur leere Antworten. Mit 12 Läufen
`phase4_interpolation.py`: Trefferquote interpoliert gegenüber abgerundet Solar 85,6 gegenüber
84,8 %, Wind an Land 84,8 gegenüber 81,9 %, Wind auf See 88,0 gegenüber 85,5 %; MAE praktisch
gleich. Interpolation bleibt. Abschnitt 23.4 des Berichts nachgetragen, Grafik e_interpolation,
PDF neu gebaut (nur lokal).

### 11:40 Phase 6: ausgerollt und geprüft

**Gemacht:** Joey hat smard-mcp 1.4.0 und das neue Archivskript ausgerollt. Geprüft:
`/health` meldet 1.4.0, 13 Tools; Smoke-Test gegen energie.akquisio.eu 12/12; Live-Aufruf
liefert Modell 2026.11.02 ohne Warnungen. Das Archiv speichert seit 10:33 UTC `laeufe_ende`;
dabei taucht `dwd_icon_d2_ruc_native_15min` als eigener Lauf auf (Bestätigung der Vermutung
zu ICON-D2-RUC in Kapitel 20).

**Fehlschlag:** Der erste Smoke-Test direkt nach dem Ausrollen scheiterte: Open-Meteo antwortete
dem frisch gestarteten Server mit HTTP 503, und ohne Cache gibt es dann keine Rückfallebene.
Wenige Minuten später lief derselbe Abruf von der Web-Maschine fehlerfrei; vorübergehende Störung
bei Open-Meteo. Die Units für `forecast-monitor` sind auf der Web-Maschine noch nicht installiert,
`recent_accuracy` bleibt bis dahin `null`.

### 11:50 Überwachung läuft

**Gemacht:** Timer `forecast-monitor` auf der Web-Maschine aktiv (täglich 05:20 UTC), erster
Lauf erfolgreich; `recent_accuracy` erscheint live in `forecast_renewables`. Erste Werte, nur
Tag 1, 11 archivierte Vorhersagen: Wind an Land 80 h, MAE 1,21 GW, Treffer 95 %; Wind auf See
80 h, MAE 0,69 GW, Treffer 100 %; Solar 36 h, MAE 3,67 GW (3,0 % der Leistung), Treffer 47 %.
Solar liegt damit klar unter der Prüfung (Tag 1 um 1,5 bis 2 %, Treffer um 80 %); 36 Stunden
aus zwei bis drei Novembertagen sind aber zu wenig für einen Schluss. Beobachten.

**Fehlschlag:** Joeys erster, beim Kopieren umgebrochener Befehl führte `scp` ohne Ziel aus und
kopierte dabei lokal `forecast-monitor.service` über `forecast-monitor.timer`; das Skript lud
die kaputte Datei hoch („Timer unit lacks value setting“). Datei aus Git wiederhergestellt,
erneut installiert. Lehre: Befehle für Joey als kurze Skriptdatei übergeben, nicht als langen
Einzeiler.
