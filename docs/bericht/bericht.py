"""Projektbericht smard-forecast als PDF.

Aufruf (aus dem Repo-Wurzelverzeichnis):
    .venv/bin/python -I docs/bericht/abbildungen.py   # Abbildungen aus data/ erzeugen
    .venv/bin/python -I docs/bericht/bericht.py       # PDF bauen

Ergebnis: docs/bericht/smard-forecast-projektbericht.pdf
"""

import datetime as dt
import sys
import tomllib
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, CondPageBreak, Frame, Image, KeepTogether,
                                NextPageTemplate, PageBreak, PageTemplate, Paragraph,
                                Preformatted, Spacer, Table, TableStyle)
from reportlab.platypus.tableofcontents import TableOfContents

HIER = Path(__file__).resolve().parent
ROOT = HIER.parents[1]
ABB = HIER / "abb"
ZIEL = HIER / "smard-forecast-projektbericht.pdf"
STAND = "2. November 2026"

F = "/usr/share/fonts/truetype/dejavu/"
pdfmetrics.registerFont(TTFont("Sans", F + "DejaVuSans.ttf"))
pdfmetrics.registerFont(TTFont("Sans-Bold", F + "DejaVuSans-Bold.ttf"))
pdfmetrics.registerFont(TTFont("Serif", F + "DejaVuSerif.ttf"))
pdfmetrics.registerFont(TTFont("Serif-Bold", F + "DejaVuSerif-Bold.ttf"))
pdfmetrics.registerFont(TTFont("Mono", F + "DejaVuSansMono.ttf"))
pdfmetrics.registerFontFamily("Sans", normal="Sans", bold="Sans-Bold", italic="Sans",
                              boldItalic="Sans-Bold")

TEXT = colors.HexColor("#0b0b0b")
TEXT2 = colors.HexColor("#52514e")
GRID = colors.HexColor("#e6e5e1")
FLAECHE = colors.HexColor("#f3f3f1")
AKZENT = colors.HexColor("#2a78d6")

S = {
    "titel": ParagraphStyle("titel", fontName="Serif", fontSize=34, leading=40, textColor=TEXT),
    "untertitel": ParagraphStyle("ut", fontName="Sans", fontSize=13, leading=19,
                                 textColor=TEXT2),
    "h1": ParagraphStyle("h1", fontName="Serif", fontSize=21, leading=26, textColor=TEXT,
                         spaceBefore=4, spaceAfter=10),
    "h2": ParagraphStyle("h2", fontName="Serif", fontSize=14, leading=18, textColor=TEXT,
                         spaceBefore=12, spaceAfter=5),
    "h3": ParagraphStyle("h3", fontName="Sans-Bold", fontSize=9.6, leading=13, textColor=TEXT,
                         spaceBefore=8, spaceAfter=3),
    "p": ParagraphStyle("p", fontName="Sans", fontSize=9.2, leading=13.6, textColor=TEXT,
                        spaceAfter=5, alignment=TA_LEFT),
    "klein": ParagraphStyle("klein", fontName="Sans", fontSize=7.8, leading=10.5,
                            textColor=TEXT2, spaceAfter=3),
    "zelle": ParagraphStyle("zelle", fontName="Sans", fontSize=7.8, leading=10.2,
                            textColor=TEXT),
    "zellek": ParagraphStyle("zellek", fontName="Sans-Bold", fontSize=7.8, leading=10.2,
                             textColor=TEXT),
    "bild": ParagraphStyle("bild", fontName="Sans", fontSize=7.6, leading=10, textColor=TEXT2,
                           spaceBefore=3, spaceAfter=10),
    "code": ParagraphStyle("code", fontName="Mono", fontSize=7.2, leading=9.4, textColor=TEXT),
    "liste": ParagraphStyle("liste", fontName="Sans", fontSize=9.2, leading=13.4,
                            textColor=TEXT, leftIndent=12, bulletIndent=2, spaceAfter=2.5),
    "kasten": ParagraphStyle("kasten", fontName="Sans", fontSize=8.8, leading=12.8,
                             textColor=TEXT),
    "toc1": ParagraphStyle("toc1", fontName="Sans", fontSize=9.6, leading=15, textColor=TEXT),
    "toc2": ParagraphStyle("toc2", fontName="Sans", fontSize=8.4, leading=12, textColor=TEXT2,
                           leftIndent=14),
}

BREITE = A4[0] - 4.2 * cm


class Bericht(BaseDocTemplate):
    def __init__(self, ziel):
        super().__init__(str(ziel), pagesize=A4, leftMargin=2.1 * cm, rightMargin=2.1 * cm,
                         topMargin=2.2 * cm, bottomMargin=2.0 * cm,
                         title="smard-forecast | Projektbericht",
                         author="akquisio-dev", subject="Prognose der Erneuerbaren für smard-mcp")
        rahmen = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="f")
        self.addPageTemplates([PageTemplate("titel", [rahmen], onPage=self.titelseite),
                               PageTemplate("normal", [rahmen], onPageEnd=self.seite)])
        self.kapitel = ""

    def titelseite(self, c, doc):
        c.saveState()
        c.setFillColor(FLAECHE)
        c.rect(0, 0, A4[0], A4[1], stroke=0, fill=1)
        c.setFillColor(AKZENT)
        c.rect(2.1 * cm, A4[1] - 3.0 * cm, 1.6 * cm, 0.16 * cm, stroke=0, fill=1)
        c.restoreState()

    def seite(self, c, doc):
        c.saveState()
        c.setFont("Sans", 7.5)
        c.setFillColor(TEXT2)
        c.drawString(2.1 * cm, A4[1] - 1.3 * cm, "smard-forecast | Projektbericht")
        c.drawRightString(A4[0] - 2.1 * cm, A4[1] - 1.3 * cm, self.kapitel)
        c.setStrokeColor(GRID)
        c.setLineWidth(0.6)
        c.line(2.1 * cm, A4[1] - 1.5 * cm, A4[0] - 2.1 * cm, A4[1] - 1.5 * cm)
        c.drawString(2.1 * cm, 1.1 * cm, f"Stand {STAND}")
        c.drawRightString(A4[0] - 2.1 * cm, 1.1 * cm, f"Seite {doc.page}")
        c.restoreState()

    def beforeDocument(self):
        self.kapitel = ""

    def afterFlowable(self, fl):
        if isinstance(fl, Paragraph) and fl.style.name in ("h1", "h2"):
            text = fl.getPlainText()
            stufe = 0 if fl.style.name == "h1" else 1
            if stufe == 0:
                self.kapitel = text
            key = f"k{id(fl)}"
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(text, key, level=stufe, closed=stufe > 0)
            self.notify("TOCEntry", (stufe, text, self.page, key))


# Bausteine -------------------------------------------------------------------
story = []
NR = {"kap": 0, "abb": 0, "tab": 0}


def h1(t):
    NR["kap"] += 1
    story.append(PageBreak())
    story.append(Paragraph(f"{NR['kap']}  {t}", S["h1"]))


def h2(t):
    story.append(CondPageBreak(5.5 * cm))
    story.append(Paragraph(t, S["h2"]))


def h3(t):
    story.append(CondPageBreak(2.2 * cm))
    story.append(Paragraph(t, S["h3"]))


def p(t):
    story.append(Paragraph(t, S["p"]))


def klein(t):
    story.append(Paragraph(t, S["klein"]))


def liste(punkte, nummern=False):
    for i, t in enumerate(punkte, 1):
        story.append(Paragraph(t, S["liste"], bulletText=f"{i}." if nummern else "•"))
    story.append(Spacer(1, 4))


def code(t):
    pre = Preformatted(t.strip("\n"), S["code"])
    tab = Table([[pre]], colWidths=[BREITE])
    tab.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), FLAECHE),
                             ("LEFTPADDING", (0, 0), (-1, -1), 8),
                             ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                             ("TOPPADDING", (0, 0), (-1, -1), 6),
                             ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    story.append(tab)
    story.append(Spacer(1, 7))


def kasten(titel, text):
    inhalt = [Paragraph(f"<b>{titel}</b>", S["kasten"]), Spacer(1, 2)]
    for t in text if isinstance(text, list) else [text]:
        inhalt.append(Paragraph(t, S["kasten"]))
    tab = Table([[inhalt]], colWidths=[BREITE])
    tab.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), FLAECHE),
                             ("LINEBEFORE", (0, 0), (0, -1), 2.2, AKZENT),
                             ("LEFTPADDING", (0, 0), (-1, -1), 10),
                             ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                             ("TOPPADDING", (0, 0), (-1, -1), 7),
                             ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    story.append(KeepTogether([tab, Spacer(1, 8)]))


def tabelle(kopf, zeilen, breiten=None, titel=None):
    NR["tab"] += 1
    daten = [[Paragraph(str(k), S["zellek"]) for k in kopf]]
    for z in zeilen:
        daten.append([Paragraph(str(x), S["zelle"]) for x in z])
    if breiten:
        summe = sum(breiten)
        breiten = [BREITE * b / summe for b in breiten]
    tab = Table(daten, colWidths=breiten, repeatRows=1)
    tab.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, 0), 0.9, TEXT),
        ("LINEBELOW", (0, 1), (-1, -1), 0.4, GRID),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    teile = []
    if titel:
        teile.append(Paragraph(f"Tabelle {NR['tab']}: {titel}", S["bild"]))
    teile.append(tab)
    story.append(KeepTogether(teile) if len(zeilen) < 14 else Table([[t] for t in teile],
                                                                    colWidths=[BREITE]))
    story.append(Spacer(1, 9))


def bild(name, text, breite=1.0):
    NR["abb"] += 1
    from PIL import Image as PI
    pfad = ABB / f"{name}.png"
    w, h = PI.open(pfad).size
    bw = BREITE * breite
    img = Image(str(pfad), width=bw, height=bw * h / w)
    story.append(KeepTogether([img, Paragraph(f"Abbildung {NR['abb']}: {text}", S["bild"])]))


def c(t):
    return f'<font face="Mono" size="8">{escape(t)}</font>'


# Inhalt -----------------------------------------------------------------------
orte = tomllib.loads((ROOT / "config" / "orte.toml").read_text())["ort"]

story.append(NextPageTemplate("titel"))
story.append(Spacer(1, 5.2 * cm))
story.append(Paragraph("smard-forecast", S["titel"]))
story.append(Spacer(1, 10))
story.append(Paragraph("Wahrscheinlichkeits-Prognose für Solar, Wind an Land und Wind auf See "
                       "bis 6 Tage voraus, als neues Tool für smard-mcp", S["untertitel"]))
story.append(Spacer(1, 1.4 * cm))
story.append(Paragraph("Projektbericht: Ziel, Daten, Technik, Ablauf, Betrieb und Entstehung, "
                       "Schritt für Schritt", S["p"]))
story.append(Spacer(1, 5.5 * cm))
for z in [f"Stand: {STAND}", "Repository: github.com/akquisio-dev/smard-forecast",
          "Zielprojekt: github.com/akquisio-dev/smard-mcp (v1.3.0)",
          "Status: Phase 0 abgeschlossen, Phase 1 läuft (Download und Archiv)"]:
    story.append(Paragraph(z, S["klein"]))
story.append(NextPageTemplate("normal"))
story.append(PageBreak())

story.append(Paragraph("Inhalt", ParagraphStyle("inhalt", parent=S["h1"])))
toc = TableOfContents()
toc.levelStyles = [S["toc1"], S["toc2"]]
toc.dotsMinLevel = 0
story.append(toc)

# 1 -----------------------------------------------------------------------------
h1("Kurzfassung")
p("smard-mcp ist ein öffentlicher MCP-Server, über den KI-Assistenten deutsche Strommarktdaten "
  "von SMARD (Bundesnetzagentur) abfragen. Er beantwortet heute Fragen über Vergangenheit und "
  "Gegenwart: wie viel Solarstrom gestern, wie teuer morgen. Was fehlt, ist der Blick nach vorn "
  "über den nächsten Tag hinaus. Die Netzbetreiber veröffentlichen ihre Prognose nur für den "
  "Folgetag.")
p("<b>smard-forecast</b> soll diese Lücke schließen: ein neues Tool "
  f"{c('forecast_renewables')}, das für Solar, Wind an Land und Wind auf See die Erzeugung der "
  "nächsten 6 Tage liefert, und zwar nicht als eine Zahl, sondern als Bandbreite: p10 (in 9 von "
  "10 Fällen wird es mehr), p50 (der mittlere Wert) und p90 (in 9 von 10 Fällen wird es weniger).")
p("Grundlage sind Wettervorhersagen des Deutschen Wetterdienstes (Modell ICON), bezogen über "
  "Open-Meteo, und die tatsächliche Erzeugung aus SMARD. Ein Lernverfahren (LightGBM) lernt aus "
  "gut zweieinhalb Jahren Daten, wie aus einer Wettervorhersage mit einem bestimmten Vorlauf "
  "eine Stromerzeugung wird, und wie unsicher das ist.")
kasten("Stand am 2. November 2026", [
    "<b>Phase 0 (Datenprüfung): abgeschlossen.</b> Die Daten tragen den Plan. Trainingsbeginn "
    "22.02.2024, rund 32 Monate, Vorhersagen bis Tag 6. Tag 7 gibt es im fremden Archiv nicht.",
    "<b>Phase 1 (Daten laden, eigenes Archiv): läuft.</b> Der Download der Trainingsdaten läuft "
    "seit 18:37 UTC und braucht wegen der Abrufgrenzen etwa zwei Tage. Das eigene Archiv der "
    "Vorhersagen ist seit 18:41 UTC auf der Web-Maschine in Betrieb.",
    "<b>Phase 2 bis 6: geplant.</b> Code in smard-mcp entsteht erst, wenn das Solar-Modell die "
    "Messlatten schlägt (Prüfpunkt A).",
])
bild("phasen", "Die sieben Phasen und drei Prüfpunkte. Blau: erledigt bzw. laufend.")
h2("Die wichtigsten Befunde bisher")
liste([
    "<b>Tag 7 fehlt im Archiv vollständig.</b> ICON global rechnet nur 180 Stunden voraus; ein "
    "Lauf von vor 7 Tagen erreicht den Zieltag nicht mehr. Version 1 geht deshalb bis Tag 6.",
    "<b>Die Daten sind fast lückenlos.</b> 40 Orte, 6 Vorlauftage, 33 Monate: ein einziger Ausfall "
    "im April 2026 (wenige Tage, nur einige Vorlauftage).",
    "<b>SMARD führt die installierte Leistung zu niedrig.</b> 2026: 103 statt 120 GW Solar, 9,2 statt "
    "11,7 GW Wind auf See. Die Auslastung wird deshalb mit Monatswerten berechnet.",
    "<b>Open-Meteo zählt große Abrufe mehrfach.</b> Ein Abruf über ein Jahr mit vielen Spalten "
    "zählt 30- bis 150-fach. Der Download muss deshalb über zwei Tage verteilt werden.",
])

# 2 -----------------------------------------------------------------------------
h1("Ausgangslage und Ziel")
h2("smard-mcp heute")
p("smard-mcp (Version 1.3.0) läuft auf der Web-Maschine unter energie.akquisio.eu/mcp und als "
  "npm-Paket. Er bietet 11 Tools, unter anderem " + c("get_current_status") + ", "
  + c("get_generation_mix") + ", " + c("analyze_prices") + " und " + c("plan_charging") + ". "
  "Alle Tools lesen nur, rechnen in Berliner Zeit, nennen die Quelle und geben Felder wie "
  + c("covered_until") + ", " + c("complete") + ", " + c("notes") + " und " + c("warnings")
  + " zurück.")
h2("Was fehlt")
p("Für die Zukunft gibt es bei SMARD nur zwei Dinge: die Day-Ahead-Prognose der Netzbetreiber "
  "(für morgen) und die Preise der Day-Ahead-Auktion (ab etwa 12 Uhr für morgen). Wer wissen will, "
  "ob am Wochenende viel Solarstrom kommt, ob eine Windflaute droht oder wann sich das "
  "Laden eines Elektroautos in den nächsten Tagen lohnt, bekommt keine Antwort.")
h2("Ziel")
liste([
    "Ein Tool " + c("forecast_renewables") + " für Deutschland gesamt (Regelzonen später).",
    "Horizont: bis 6 Tage ab jetzt, stündlich oder täglich.",
    "Ausgabe: p10, p50, p90 in GW, Tagesenergie in GWh mit Bandbreite.",
    "Ehrlichkeit: das Tool nennt seinen eigenen gemessenen Fehler je Vorlauftag.",
    "Betrieb ohne GPU, ohne Kosten, ohne neue Abhängigkeiten im Server.",
])
h2("Was ausdrücklich nicht dazugehört (Version 1)")
liste([
    "Anteil an der Last: bräuchte eine eigene Verbrauchsprognose.",
    "Regelzonen (50Hertz, Amprion, TenneT, TransnetBW).",
    "Preisprognose.",
    "Tag 7: erst, wenn das eigene Archiv ein Jahr umfasst.",
])

# 3 -----------------------------------------------------------------------------
h1("Grundbegriffe")
p("Dieses Kapitel erklärt die Begriffe, die im Rest des Berichts vorkommen. Wer sie kennt, kann "
  "es überspringen.")
h2("Wettermodell, Lauf und Vorlaufzeit")
p("Ein numerisches Wettermodell rechnet aus dem aktuellen Zustand der Atmosphäre die Zukunft "
  "voraus. Jede Rechnung heißt <b>Lauf</b> und hat einen <b>Startzeitpunkt</b> (Initialisierung). "
  "Der Deutsche Wetterdienst betreibt drei ICON-Modelle:")
tabelle(["Modell", "Gebiet", "Auflösung", "Läufe", "reicht bis"], [
    ["ICON-D2", "Deutschland und Nachbarn", "2,2 km", "alle 3 h", "48 h"],
    ["ICON-D2-RUC", "wie D2", "2,2 km", "stündlich", "kurz (Schnellaktualisierung)"],
    ["ICON-EU", "Europa", "6,5 km", "alle 3 h (lange Läufe alle 6 h)", "120 h"],
    ["ICON (global)", "Welt", "13 km", "alle 6 h (lange Läufe 00 und 12 UTC)", "180 h"],
], [1.3, 2, 1, 2.2, 1.8], "Die ICON-Modelle des DWD")
p("<b>Vorlaufzeit</b> ist der Abstand zwischen Startzeitpunkt eines Laufs und der Stunde, für die "
  "er etwas vorhersagt. Je länger der Vorlauf, desto unsicherer die Vorhersage. "
  + c("icon_seamless") + " ist eine Zusammenstellung von Open-Meteo: für die ersten Stunden die "
  "feinste verfügbare Quelle (D2), danach EU, danach global.")
h2("Quantile: p10, p50, p90")
p("Eine Punktprognose sagt „morgen 12 Uhr: 40 GW Solar“. Eine <b>Quantilsprognose</b> sagt: "
  "„mit 10 % Wahrscheinlichkeit weniger als 31 GW (p10), mit 50 % weniger als 40 GW (p50), mit "
  "90 % weniger als 46 GW (p90)“. Zwischen p10 und p90 sollte der echte Wert also in etwa 80 % "
  "aller Stunden liegen. Das nennt man <b>Trefferquote der Bandbreite</b> (englisch coverage).")
p("Ein Modell lernt ein Quantil τ mit dem <b>Pinball-Verlust</b>. Ist der Fehler e = y minus "
  "Vorhersage, dann ist der Verlust τ·e bei e größer 0 und (τ − 1)·e bei e kleiner 0. Für τ = 0,9 "
  "kostet zu niedrig Vorhersagen neunmal so viel wie zu hoch, deshalb landet die Vorhersage so, "
  "dass nur 10 % der echten Werte darüber liegen.")
bild("pinball", "Links: Pinball-Verlust für drei Quantile. Rechts: so sieht eine Tagesausgabe "
     "aus (Schema mit erfundenen Werten).")
h2("Auslastung")
p("<b>Auslastung</b> = Erzeugung geteilt durch installierte Leistung, ein Wert zwischen 0 und 1. "
  "Weil jeden Monat Anlagen dazukommen, wächst die Erzeugung bei gleichem Wetter. Lernt das "
  "Modell die Auslastung statt der GW, stört der Zubau nicht. Im Betrieb wird mit der aktuellen "
  "Leistung zurück in GW gerechnet.")
h2("LightGBM")
p("LightGBM ist ein Verfahren aus Entscheidungsbäumen (Gradient Boosting). Viele kleine Bäume "
  "werden nacheinander gelernt, jeder korrigiert die Fehler der vorherigen. Vorteile hier: "
  "schnell auf der CPU, kommt mit vielen Spalten und fehlenden Werten klar, kann Quantile "
  "lernen, und ein fertiges Modell ist nur eine Liste von Bäumen, die sich in jeder Sprache "
  "mit ein paar Zeilen auswerten lässt.")

# 4 -----------------------------------------------------------------------------
h1("Das Vorlaufzeit-Problem")
p("Das ist der Kern des ganzen Projekts, deshalb ein eigenes Kapitel.")
kasten("Die Regel", "Ein Modell muss mit genau den Vorhersagen trainiert werden, die es im "
       "Betrieb bekommt. Eine Prognose für Tag 5 lernt man nur aus früheren Vorhersagen, die "
       "ebenfalls 5 Tage Vorlauf hatten.")
p("Warum? Eine 5 Tage alte Wettervorhersage liegt oft daneben. Ein Modell, das mit fast "
  "perfektem Wetter trainiert wurde, vertraut der Vorhersage zu sehr und gibt zu schmale "
  "Bandbreiten aus. Im Test sähe es gut aus, im Betrieb wäre es schlecht.")
h2("Zwei Archive bei Open-Meteo")
tabelle(["API", "was sie liefert", "geeignet?"], [
    ["Historical Forecast API", "setzt aus jedem Lauf nur die ersten Stunden zusammen; also "
     "fast immer Vorlauf 0 bis 6 h, fast so gut wie eine Messung", "nein, viel zu optimistisch"],
    ["Previous Runs API", "für jede Stunde zusätzlich die Werte aus dem Lauf von vor 1, 2, ... "
     "Tagen (Spalten " + c("_previous_day1") + " bis " + c("_previous_day7") + ")",
     "ja, genau das Richtige"],
    ["Single Runs API", "einen ganzen Lauf mit exaktem Startzeitpunkt", "nur ab Mai 2026, für "
     "Prüfungen"],
], [1.6, 4, 1.6], "Die Archive von Open-Meteo")
bild("vorlauf_schema", "Oben: die Historical Forecast API nimmt für jede Stunde den jüngsten "
     "Lauf. Unten: die Previous Runs API nimmt für Tag 3 den Lauf, der mindestens 72 h vorher "
     "startete.")
h2("Was „Tag N“ genau bedeutet (geprüft)")
p("Am 2. November wurde für einen Ort (52,5° N, 10° E) und den 20.10.2026 jede Stunde aus der "
  "Previous Runs API mit allen Einzelläufen der Woche davor verglichen, Wert für Wert "
  "(Temperatur und Wind in 100 m).")
tabelle(["Spalte", "passt zu", "Vorlauf"], [
    ["previous_day3", "Lauf 3 Tage vorher, genau", "72 bis 77 h"],
    ["previous_day6", "ICON-global-Lauf, genau", "144 bis 150 h"],
    ["previous_day1", "keinem Einzellauf genau; Abweichung wenige Zehntel", "etwa 24 bis 27 h"],
], [1.6, 3.6, 1.6], "Abgleich mit Einzelläufen")
p("Daraus folgt die Definition, die in Training und Betrieb gleich gilt: <b>Tag N ist der neueste "
  "Lauf, der mindestens N mal 24 Stunden vor der Zielstunde gestartet ist.</b> Im Betrieb wird "
  "für jede Stunde die Vorlaufzeit = Zielstunde minus Startzeitpunkt des Laufs berechnet und auf "
  "ganze Tage abgerundet; Stunden unter 24 h zählen als Tag 1.")
p("Dass Tag 1 nicht exakt passt, liegt sehr wahrscheinlich an ICON-D2-RUC: Open-Meteo nutzt für "
  "die ersten Stunden inzwischen die stündlich aktualisierte Variante, und die Single Runs API "
  "führt diese Lauffolge nicht vollständig. Für das Training ist das unkritisch. Das eigene "
  "Archiv speichert deshalb die Startzeitpunkte aller ICON-Modelle mit, damit sich das später "
  "genau klären lässt.")

# 5 -----------------------------------------------------------------------------
h1("Datenquellen")
h2("Open-Meteo")
p("Open-Meteo stellt die DWD-Modelle frei über eine einfache HTTP-Schnittstelle bereit. Die Daten "
  "stehen unter CC BY 4.0. Die freie Schnittstelle ist für nicht-kommerzielle Nutzung ohne "
  "Werbung und Abo gedacht; smard-mcp ist kostenlos und werbefrei.")
h3("Abrufgrenzen und Gewichtung")
p("Open-Meteo erlaubt frei 600 Abrufe pro Minute, 5.000 pro Stunde und 10.000 pro Tag. Große "
  "Abrufe zählen mehrfach: anteilig mehr ab 10 Spalten und ab 14 Tagen, und jeder Ort zählt "
  "einzeln. Als Formel (so im Code, Funktion " + c("gewicht()") + "):")
code("gewicht = orte × max(1, spalten / 10) × max(1, tage / 14)")
p("Beispiel: ein Solar-Ort, 6 Variablen × 6 Vorlauftage = 36 Spalten, ein Jahr (365 Tage): "
  "1 × 3,6 × 26,1 = 94 Einheiten. Ein Ort, der für Solar und Wind zählt, hat 10 Variablen, also "
  "60 Spalten: 156 Einheiten pro Jahr.")
h3("Variablen")
tabelle(["Variable", "Einheit", "für", "im Archiv"], [
    ["shortwave_radiation", "W/m²", "Solar", "ja"],
    ["direct_radiation", "W/m²", "Solar", "ja"],
    ["diffuse_radiation", "W/m²", "Solar", "ja"],
    ["cloud_cover", "%", "Solar", "ja"],
    ["temperature_2m", "°C", "Solar und Wind (Modulwärme, Luftdichte)", "ja"],
    ["wind_speed_10m", "km/h", "Solar (Kühlung) und Wind", "ja"],
    ["wind_speed_100m", "km/h", "Wind (Nabenhöhe)", "ja, ab 16.02.2024"],
    ["wind_direction_100m", "°", "Wind", "ja"],
    ["wind_gusts_10m", "km/h", "Wind (Sturmabschaltung)", "ja"],
    ["surface_pressure", "hPa", "Wind (Luftdichte)", "ja"],
    ["direct_normal_irradiance", "W/m²", "(ableitbar, nicht geladen)", "ja"],
    ["cloud_cover_low", "%", "geplant", "nein"],
    ["snow_depth", "m", "geplant (Schnee auf Modulen)", "nein"],
], [2.2, 0.9, 3, 1.4], "Wettervariablen")
h2("SMARD")
p("SMARD ist die Strommarktdaten-Plattform der Bundesnetzagentur. Die Daten kommen über "
  + c("https://www.smard.de/app/chart_data") + " als Wochenstücke im JSON-Format. Die Kennungen "
  "sind dieselben wie in smard-mcp (src/catalog.ts).")
tabelle(["Schlüssel", "Filter-ID", "Inhalt"], [
    ["generation_solar", "4068", "Erzeugung Photovoltaik"],
    ["generation_wind_onshore", "4067", "Erzeugung Wind an Land"],
    ["generation_wind_offshore", "1225", "Erzeugung Wind auf See"],
    ["forecast_generation_solar", "125", "Day-Ahead-Prognose der Netzbetreiber, Solar"],
    ["forecast_generation_wind_onshore", "123", "Prognose Wind an Land"],
    ["forecast_generation_wind_offshore", "3791", "Prognose Wind auf See"],
    ["capacity_solar / _wind_onshore / _wind_offshore", "188 / 186 / 4076",
     "installierte Leistung, nur Jahreswerte"],
], [3, 1.4, 3], "SMARD-Reihen")
bild("woche", "Eine Woche im Juni 2026: echte Erzeugung gegen die Prognose der Netzbetreiber "
     "vom Vortag. Das ist die Messlatte für Tag 1.")
h2("Energy-Charts (installierte Leistung)")
p("Energy-Charts (Fraunhofer ISE) veröffentlicht die installierte Leistung monatlich, abgeleitet "
  "aus dem Marktstammdatenregister. Abgerufen über "
  + c("api.energy-charts.info/installed_power?country=de&time_step=monthly") + ". Für Solar gibt "
  "es zwei Werte: DC (Modulleistung) und AC (Wechselrichterleistung). Genommen wird AC, weil die "
  "Wechselrichter die Einspeisung begrenzen.")
kasten("Offener Punkt", "Die Lizenz der Energy-Charts-Daten ist noch zu klären; die Seite mit den "
       "Nutzungshinweisen ließ sich ohne Browser nicht lesen. Rückfall: Monatssummen selbst aus "
       "dem Marktstammdatenregister berechnen (Lizenz dl-de/by-2-0).")

# 6 -----------------------------------------------------------------------------
h1("Phase 0: Datenprüfung (abgeschlossen)")
p("Ziel von Phase 0: bevor eine Zeile Modellcode entsteht, beweisen, dass die Daten den Plan "
  "tragen. Ein Fehlschlag hier kostet nur Zeit, nicht smard-mcp.")
h2("Wetter: Lückenprüfung über den ganzen Zeitraum")
p("Skript " + c("scripts/phase0_wetter.py") + ". Für alle 40 Orte, Zeitraum 25.01.2024 bis "
  "01.11.2026, je Vorlauftag 1 bis 6: Temperatur, dazu Strahlung (Solar-Orte) bzw. Wind in 100 m "
  "(Wind-Orte). Je Ort drei Abrufe (je Kalenderjahr), jede Antwort wird gespeichert.")
bild("verfuegbarkeit", "Ab wann es Werte gibt, je Variable und Vorlauftag. Die senkrechte Linie "
     "ist der gewählte Trainingsbeginn.")
tabelle(["Befund", "Umfang", "Folge"], [
    ["Ausfall im Archiv", "10. bis 13.04.2026, Tag 2, 4, 5, 6, an allen Orten gleich; Tag 1 und 3 "
     "vollständig", "Stunden fallen im Training weg"],
    ["wind_speed_100m beginnt später", "Tag 1 ab 16.02.2024, Tag 6 ab 21.02.2024",
     "Trainingsbeginn 22.02.2024 für alle Quellen"],
    ["previous_day7", "nie vorhanden", "Version 1 bis Tag 6"],
    ["cloud_cover_low, snow_depth", "nicht im Archiv", "Merkmale entfallen"],
    ["Offshore-Orte", "alle 7 auf 0 m Höhe", "liegen wirklich auf See"],
    ["sonst", "keine Lücken", "Rückfallebene nicht nötig"],
], [1.8, 3.2, 2.2], "Befunde der Wetterprüfung")
h2("SMARD")
p("Skript " + c("scripts/smard_laden.py") + " (in Phase 0 noch phase0_smard.py). Erzeugung aller "
  "drei Quellen ab 01.01.2024 stündlich: lückenlos. Netzbetreiber-Prognose: ein fehlender Tag "
  "(23.10.2026 22 Uhr bis 24.10.2026, Solar und Wind an Land).")
h2("Installierte Leistung: ein falscher Nenner")
p("Prüfidee: Wenn die installierte Leistung stimmt, sollte die höchste Auslastung über die Jahre "
  "etwa gleich bleiben (das Wetter hat keinen Trend). Mit den SMARD-Jahreswerten fällt sie bei "
  "Solar, und bei Wind auf See steigt sie. Der Vergleich mit Energy-Charts zeigt den Grund: SMARD "
  "hinkt dem Zubau hinterher.")
bild("kapazitaet", "Installierte Leistung: SMARD-Jahreswerte (gestrichelt) gegen Monatswerte "
     "von Energy-Charts. Zahl am Ende: Stand Oktober 2026 in GW.")
bild("auslastung_nenner", "99%-Quantil der stündlichen Auslastung je Jahr, einmal mit SMARD als "
     "Nenner, einmal mit Monatswerten. Mit Monatswerten liegt die Auslastung niedriger und "
     "gleichmäßiger.")
p("Zahlen 2026: Solar 103,3 GW (SMARD) gegen 120,4 GW AC (Energy-Charts), Wind an Land 67,7 gegen "
  "71,7 GW, Wind auf See 9,2 gegen 11,7 GW. <b>Entscheidung:</b> Monatswerte als Nenner.")
h2("Wetterorte")
p("40 feste Orte in " + c("config/orte.toml") + ": 21 Solar-Orte nach Schwerpunkten der "
  "Photovoltaik (stark in Bayern und Baden-Württemberg), 14 Wind-Orte (Küste, Norddeutsches "
  "Tiefland, Mittelgebirge), 7 Orte auf See in den Clustern der Nord- und Ostsee. Magdeburg und "
  "Cottbus zählen für Solar und Wind. Eine Gewichtung aus dem Marktstammdatenregister kommt "
  "später; das Modell gewichtet die Orte ohnehin selbst.")
bild("karte", "Die 40 Wetterorte.", 0.78)
tabelle(["Name", "Breite", "Länge", "Typ"],
        [[o["name"], f"{o['lat']:.2f}", f"{o['lon']:.2f}", ", ".join(o["typ"])] for o in orte],
        [2.4, 1, 1, 1.6], "Alle Wetterorte")
h2("Ergebnis")
kasten("Phase 0 bestanden", "Trainingsbeginn 22.02.2024, rund 32 Monate, 6 Vorlauftage, "
       "40 Orte. Einziger offener Punkt: Lizenz Energy-Charts.")

# 7 -----------------------------------------------------------------------------
h1("Architektur")
p("Das Projekt verteilt sich auf zwei Maschinen, zwei Repositories und drei externe Quellen.")
bild("architektur", "Wer was macht. Training auf der großen Maschine, Betrieb auf der "
     "Web-Maschine, Austausch über GitHub.")
tabelle(["Ort", "Was dort liegt", "Warum dort"], [
    ["große Maschine, /root/smard-forecast", "Download, Trainingsdaten (data/), Training, "
     "Berichte", "viel Arbeitsspeicher und Platz; Training ist rechenintensiver"],
    ["Web-Maschine, /opt/smard-forecast-archiv", "Archiv-Skript und Ortsliste",
     "läuft dauerhaft, braucht kaum Ressourcen, smard-mcp läuft dort auch"],
    ["Web-Maschine, /var/lib/smard-forecast/archiv", "gespeicherte Vorhersagen",
     "Zustand des Dienstes, nachts gesichert"],
    ["GitHub akquisio-dev/smard-forecast", "Plan, Code, später Modelle und Workflow",
     "öffentlich, nachvollziehbar"],
    ["GitHub akquisio-dev/smard-mcp", "Tool, TS-Auswertung, models/*.json", "Auslieferung"],
    ["npm, energie.akquisio.eu/mcp", "das fertige Tool", "dort nutzen es KI-Clients"],
], [2.4, 2.8, 2.6], "Orte im Überblick")
h2("Aufbau des Repositorys")
code("""
smard-forecast/
├── README.md, LICENSE (MIT), pyproject.toml, .gitignore
├── config/orte.toml          40 Wetterorte (Name, Breite, Länge, Typ)
├── sf/                       kleine Python-Bibliothek
│   ├── orte.py               lädt die Ortsliste
│   ├── openmeteo.py          Previous Runs API, Variablen je Typ, gewicht()
│   ├── smard.py              SMARD chart_data, Kennungen
│   └── log.py                Protokoll mit Zeitstempel nach data/logs/
├── scripts/
│   ├── phase0_wetter.py      Lückenprüfung Wetter
│   ├── smard_laden.py        SMARD laden und prüfen
│   ├── download.py           Trainingsdaten laden (Phase 1)
│   └── kapazitaet.py         installierte Leistung monatlich
├── archiv/
│   ├── archiv.py             Archiv-Job (Server, nur Standardbibliothek)
│   ├── smard-forecast-archiv.service / .timer
│   └── ausrollen.sh          bringt den Job auf den Server
├── docs/
│   ├── PLAN.md, phase0.md, phase1.md
│   ├── journal.md            Projekttagebuch
│   └── bericht/              dieser Bericht (abbildungen.py, bericht.py)
└── data/                     nicht im Git: wetter/, smard/, phase0/, logs/
""")
p("Alles unter " + c("data/") + " lässt sich jederzeit neu laden und ist deshalb nicht im Git. "
  "Ausnahme ist das Archiv auf dem Server: das lässt sich nicht neu beschaffen und wird deshalb "
  "gesichert.")

# 8 -----------------------------------------------------------------------------
h1("Phase 1: Daten laden und eigenes Archiv (läuft)")
h2("Der Trainingsdownload Schritt für Schritt")
p("Skript " + c("scripts/download.py") + ", gestartet als eigener systemd-Dienst "
  + c("smard-forecast-download") + ", damit er unabhängig von der Sitzung weiterläuft.")
liste([
    "Ortsliste lesen; je Ort die Variablen bestimmen (Solar 6, Wind 6, beides 10).",
    "Zeitraum 22.02.2024 bis 01.11.2026 in Kalenderjahre teilen: 3 Stücke je Ort, 120 insgesamt.",
    "Stücke überspringen, deren Datei schon existiert (" + c("data/wetter/<ort>/<von>_<bis>.parquet")
    + "). Dadurch kann der Download jederzeit abbrechen und weitermachen.",
    "Für jedes offene Stück das Gewicht berechnen (94 bis 156 Einheiten pro Jahr).",
    "Prüfen, ob das Gewicht in alle drei Fenster passt: Tag (höchstens 9.000), letzte Stunde "
    "(4.500), letzte Minute (450). Die Grenzen liegen bewusst unter denen von Open-Meteo. Wenn "
    "nicht, warten: bei vollem Tag bis 00:05 UTC, bei voller Stunde je 2 Minuten, bei voller "
    "Minute je 15 Sekunden.",
    "Abruf an die Previous Runs API; bei leerer Antwort, Zeitüberschreitung oder Fehler 429/5xx "
    "bis zu fünfmal wiederholen, mit wachsender Pause.",
    "Abruf mit Zeitstempel und Gewicht in " + c("data/wetter/budget.json") + " buchen.",
    "Antwort in die lange Form bringen: eine Zeile je Stunde und Vorlauftag, Spalten zeit (UTC), "
    "vorlauf (1 bis 6) und die Variablen als Float32.",
    "Erst in eine .tmp-Datei schreiben, dann umbenennen: eine halb geschriebene Datei kann so nie "
    "als fertig gelten.",
    "Zeile ins Protokoll " + c("data/logs/download.log") + ": Ort, Zeitraum, Zeilen, ganz leere "
    "Zeilen, Gewicht.",
], nummern=True)
p("Gesamtgewicht etwa 10.460 Einheiten. Am 2. November war das Tageskontingent durch die "
  "Lückenprüfung schon belastet, deshalb lädt der Download am ersten Abend etwa 4.500 Einheiten "
  "und den Rest ab 00:05 UTC am 3. November.")
code("""
# Aufbau einer Trainingsdatei (Magdeburg); Schema, Werte erfunden
zeit                       vorlauf  shortwave_radiation  ...  wind_speed_100m  surface_pressure
2025-06-01 12:00:00+00:00  1        812.0                ...  19.4             1003.1
2025-06-01 12:00:00+00:00  2        790.0                ...  21.0             1002.7
...
2025-06-01 12:00:00+00:00  6        655.0                ...  17.8             1004.9
""")
h2("Das eigene Archiv")
p("Warum ein eigenes Archiv, wenn Open-Meteo eins hat? Drei Gründe: Tag 7 gibt es dort nicht; "
  "das Monitoring braucht genau die Vorhersagen, die zum Zeitpunkt der Prognose vorlagen; und "
  "ein fremdes Archiv kann Lücken bekommen oder verschwinden.")
bild("archiv_ablauf", "Was der Archiv-Job jede Stunde tut.")
liste([
    "Der Timer startet den Dienst stündlich um :35 (mit bis zu 2 Minuten Zufallsversatz).",
    "Der Dienst liest für vier Modelle " + c("meta.json") + " von Open-Meteo und daraus "
    + c("last_run_initialisation_time") + ". Das kostet kein Kontingent.",
    "Hat sich der Lauf von ICON-D2, ICON-EU oder ICON global gegenüber "
    + c("letzter_stand.json") + " geändert? RUC wird nur mitgeschrieben, sonst wären es 24 Abrufe "
    "am Tag.",
    "Wenn ja: ein Abruf an die Forecast API mit allen 40 Orten kommagetrennt, 10 Variablen, "
    "8 Tage (Gewicht 40).",
    "Speichern als " + c("/var/lib/smard-forecast/archiv/JJJJ/MM/TT/<zeit>.json.gz") + " mit "
    "Abrufzeit, Modell, allen Laufzeitpunkten und den Werten je Ort. Wieder über .tmp und "
    "Umbenennen.",
], nummern=True)
code("""
{
  "abgerufen": "2026-11-02T18:41:29Z",
  "modell": "icon_seamless",
  "laeufe": {"dwd_icon_d2": "2026-11-02T15:00Z", "dwd_icon_eu": "2026-11-02T15:00Z",
             "dwd_icon": "2026-11-02T12:00Z", "dwd_icon_d2_ruc_native_15min": "2026-11-02T17:00Z"},
  "orte": [{"name": "muenchen", "lat": 48.14, "lon": 11.58, "elevation": 519.0,
            "hourly": {"time": [...192 Stunden...], "shortwave_radiation": [...], ...}}, ...]
}
""")
p("Größe: etwa 95 KB je Abruf, etwa 8 Abrufe am Tag, rund 300 MB im Jahr.")
h3("Absicherung des Dienstes")
p("Der Dienst läuft als eigener Systemnutzer " + c("smard-forecast") + " ohne Anmeldung, mit "
  "systemd-Härtung: kein Schreiben außerhalb seines Zustandsverzeichnisses "
  "(" + c("ProtectSystem=strict") + ", " + c("StateDirectory") + "), kein Zugriff auf Home-"
  "Verzeichnisse, keine Rechte (" + c("CapabilityBoundingSet=") + " leer), nur IPv4/IPv6, "
  "höchstens 256 MB Speicher. Der Server hat nur Python 3.10, deshalb nutzt das Skript nur die "
  "Standardbibliothek; die Ortsliste wird beim Ausrollen als JSON erzeugt.")
h3("Sicherung")
p("Die nächtliche Dienste-Sicherung (04:00 UTC) holt das Archiv per ssh als tar.gz auf die große "
  "Maschine (Posten " + c("smard-forecast") + "), prüft es und rotiert die Stände.")
bild("tagesablauf", "Ein Tag im Betrieb: Modellläufe, Archiv-Prüfungen, Sicherung.")

# 9 -----------------------------------------------------------------------------
h1("Phase 2: Das Solar-Modell (geplant)")
p("Solar kommt zuerst, weil es am besten vorhersagbar ist und der Fehler am klarsten zu messen. "
  "Schlägt Solar die Messlatten nicht, lohnt sich der Rest nicht.")
bild("pipeline", "Datenfluss von den Rohdaten bis zum Tool.")
h2("Schritt 1: Trainingstabelle bauen")
liste([
    "Alle Parquet-Stücke der Solar-Orte einlesen.",
    "Breit machen: je (Zeit, Vorlauftag) eine Zeile; je Ort und Variable eine Spalte, zum Beispiel "
    + c("muenchen__shortwave_radiation") + ". Bei 21 Orten und 6 Variablen sind das 126 "
    "Wetterspalten.",
    "SMARD-Erzeugung Solar dazu (stündlich, UTC).",
    "Zielgröße: Erzeugung geteilt durch installierte AC-Leistung des Monats.",
    "Zeilen ohne Zielwert oder mit ganz leerem Wetter (Ausfall April 2026) entfernen.",
], nummern=True)
p("Größe: rund 23.000 Stunden × 6 Vorlauftage = etwa 140.000 Zeilen, davon etwa die Hälfte am Tag.")
h2("Schritt 2: Merkmale")
tabelle(["Merkmal", "Berechnung", "Zweck"], [
    ["Wetter je Ort", "6 Variablen × 21 Orte", "Hauptinformation; das Modell gewichtet selbst"],
    ["Mittel über Orte", "z. B. mittlere Strahlung aller Solar-Orte", "stabiler Gesamtwert"],
    ["vorlauf", "1 bis 6", "Unsicherheit wächst mit dem Vorlauf"],
    ["Stunde", "Sinus und Kosinus von 2π·h/24", "Tagesgang ohne Sprung um Mitternacht"],
    ["Tag im Jahr", "Sinus und Kosinus von 2π·d/365,25", "Jahresgang"],
    ["Sonnenhöhe", "berechnet für 51° N, 10° E (nicht vorhergesagt)", "Geometrie, Einfallswinkel"],
    ["Wochentag, Feiertag", "bundesweite Feiertage", "Abregelung bei negativen Preisen"],
], [1.8, 3, 2.6], "Merkmale des Solar-Modells")
p("Nachtstunden (Sonnenhöhe unter 0°) bekommen fest 0 und gehen weder ins Training noch in die "
  "Kennzahlen ein. Sonst sähe der Fehler künstlich klein aus, weil nachts jedes Modell recht hat.")
h2("Schritt 3: Training")
p("Je Quantil ein Modell, also drei Modelle für Solar. Startwerte (werden in Phase 2 abgestimmt):")
tabelle(["Parameter", "Startwert", "Bedeutung"], [
    ["objective / alpha", "quantile / 0,1, 0,5, 0,9", "Pinball-Verlust für das Quantil"],
    ["num_leaves", "15", "Größe eines Baums; klein hält das Paket klein"],
    ["learning_rate", "0,05", "Schrittweite"],
    ["n_estimators", "höchstens 300, frühes Stoppen", "Zahl der Bäume"],
    ["min_data_in_leaf", "50", "gegen Auswendiglernen seltener Stunden"],
    ["feature_fraction", "0,8", "je Baum nur ein Teil der Spalten"],
    ["bagging_fraction / freq", "0,8 / 1", "je Baum nur ein Teil der Zeilen"],
], [2, 2.4, 3], "Startwerte LightGBM")
p("Danach werden die drei Vorhersagen je Stunde sortiert, damit nie p10 über p50 oder p50 über "
  "p90 liegt (getrennt gelernte Quantile können sich sonst kreuzen). Werte unter 0 werden 0, "
  "Auslastung über 1 wird 1.")
h2("Schritt 4: Bewertung")
bild("validierung", "Zeitliche Validierung: trainieren bis Monat M, testen auf M+1; dazu die "
     "letzten 3 Monate als unberührter Abschlusstest.")
p("Nie zufällig teilen: benachbarte Stunden sind fast gleich, eine zufällige Teilung würde das "
  "Modell mit der Antwort im Training testen. Die erste Testrunde beginnt nach 12 Monaten "
  "Training, damit jede Jahreszeit einmal gesehen wurde.")
tabelle(["Kennzahl", "Formel", "Ziel"], [
    ["MAE", "Mittel von |echt − p50| in GW", "klein"],
    ["MAE in %", "MAE geteilt durch installierte Leistung", "vergleichbar über Jahre"],
    ["Fehler Tagesenergie", "|Summe echt − Summe p50| je Tag in GWh", "für Tagesfragen"],
    ["Trefferquote", "Anteil Stunden mit p10 ≤ echt ≤ p90", "um 80 %"],
    ["Pinball", "mittlerer Pinball-Verlust über alle drei Quantile", "klein"],
    ["Skill", "1 − MAE Modell / MAE Messlatte", "größer 0,2 ab Tag 2"],
], [1.6, 3.6, 1.8], "Kennzahlen, je Vorlauftag")
h2("Die Messlatten")
tabelle(["Messlatte", "was sie ist", "gilt für"], [
    ["Klimatologie", "mittlere Auslastung je Stunde und Monat der Vorjahre", "Tag 1 bis 6"],
    ["Persistenz", "wie der letzte vollständige Tag", "Tag 1 bis 6"],
    ["Netzbetreiber", "SMARD forecast_generation_* vom Vortag", "Tag 1"],
], [1.6, 4, 1.4], "Messlatten")
bild("klimatologie", "So sieht die Messlatte Klimatologie für Solar aus, aus echten Daten "
     "2024 und 2025.")
kasten("Prüfpunkt A: Weiter-Kriterium (Startwert)", [
    "An Tag 2 bis 6 mindestens 20 % weniger MAE als die bessere der beiden einfachen Messlatten.",
    "An Tag 1 höchstens 20 % mehr Fehler als die Netzbetreiber.",
    "Trefferquote der Bandbreite zwischen 75 und 85 %.",
    "Die Wintermonate werden getrennt ausgewiesen, weil der Abschlusstest (August bis Oktober "
    "2026) keinen Winter enthält.",
])

# 10 ----------------------------------------------------------------------------
h1("Phase 3: Wind an Land und auf See (geplant)")
p("Gleicher Ablauf wie Solar, mit anderen Merkmalen.")
tabelle(["", "Wind an Land", "Wind auf See"], [
    ["Orte", "16 (14 Wind + Magdeburg, Cottbus)", "7 (5 Nordsee, 2 Ostsee)"],
    ["Variablen", "Wind 10 m und 100 m, Richtung, Böen, Temperatur, Luftdruck", "dieselben"],
    ["zusätzlich", "Windrichtung als Sinus/Kosinus", "dito"],
    ["Besonderheit", "Leistungskurve: unter 3 m/s nichts, ab etwa 12 m/s voll, ab etwa 25 m/s "
     "Abschaltung", "wenige große Parks; Netzengpässe und Abregelung häufig"],
    ["Nachtstunden", "zählen voll", "zählen voll"],
], [1.4, 3, 3], "Unterschiede der Wind-Modelle")
p("Prüfpunkt B: gleiche Kriterien wie A, je Quelle. Wind ist schwerer vorherzusagen als Solar; "
  "Wind auf See leidet zusätzlich unter Abregelung, die nichts mit dem Wetter zu tun hat.")

# 11 ----------------------------------------------------------------------------
h1("Phase 4: Das Tool in smard-mcp (geplant)")
h2("Modelle von Python nach TypeScript")
p("smard-mcp ist in TypeScript geschrieben und soll keine neue Abhängigkeit bekommen. LightGBM "
  "kann ein Modell als JSON ausgeben (" + c("dump_model()") + "). Ein eigenes, kompaktes Format "
  "hält die Dateien klein:")
code("""
// models/solar_p50.json (vereinfacht)
{ "version": "2026-12-01", "quelle": "solar", "quantil": 0.5,
  "spalten": ["vorlauf", "stunde_sin", ..., "muenchen__shortwave_radiation", ...],
  "basis": 0.0812,
  "baeume": [ { "s": [12, 3, ...],        // Spalte je innerem Knoten
                "t": [210.5, 0.31, ...],  // Schwelle
                "l": [1, 3, ...], "r": [2, 4, ...],  // Kinder; negativ = Blatt -(i+1)
                "v": [0.0123, -0.004, ...],          // Blattwerte
                "n": [0, 1, ...] } ] }    // fehlender Wert geht links (0) oder rechts (1)
""")
code("""
// TypeScript: ein Baum, eine Zeile
function baum(b: Baum, x: Float64Array): number {
  let k = 0;
  for (;;) {
    const w = x[b.s[k]];
    const links = Number.isNaN(w) ? b.n[k] === 0 : w <= b.t[k];
    const z = links ? b.l[k] : b.r[k];
    if (z < 0) return b.v[-z - 1];
    k = z;
  }
}
const vorhersage = (m: Modell, x: Float64Array) =>
  m.baeume.reduce((s, b) => s + baum(b, x), m.basis);
""")
p("Ein Test in smard-mcp vergleicht die TypeScript-Auswertung mit Python-Vorhersagen auf festen "
  "Beispielzeilen (Abweichung kleiner 1e-9). Ziel für alle neun Modelle zusammen: unter 2 MB.")
h2("Ablauf einer Anfrage")
liste([
    "Eingaben prüfen: Zeitraum höchstens 6 Tage ab jetzt, nicht in der Vergangenheit.",
    "Wetter holen: ein Abruf für alle 40 Orte, Ergebnis im Zwischenspeicher, bis "
    + c("meta.json") + " einen neueren Lauf meldet (etwa 8 Abrufe am Tag).",
    "Je Zielstunde die Vorlaufzeit bestimmen (Zielstunde minus Laufstart, auf Tage abgerundet).",
    "Merkmale bauen, genau wie im Training (gemeinsame Spaltenliste aus der Modelldatei).",
    "Drei Modelle je Quelle auswerten, sortieren, auf 0 bis 1 begrenzen.",
    "Mal installierte Leistung (aktueller Monat) ergibt GW; je Tag summieren zu GWh.",
    "Wo für morgen veröffentlicht: Netzbetreiber-Prognose daneben stellen.",
    "Ausgabe mit Metadaten und den gemessenen Fehlern.",
], nummern=True)
h2("Schnittstelle")
tabelle(["Parameter", "Werte", "Standard"], [
    ["from, to", "ISO-Datum oder Datum mit Uhrzeit (Berlin), höchstens 6 Tage ab jetzt",
     "jetzt bis +6 Tage"],
    ["sources", "solar, wind_onshore, wind_offshore", "alle drei"],
    ["resolution", "hour, day", "day, bei bis zu 48 h hour"],
    ["include_intervals", "ja oder nein", "nein"],
], [1.5, 4, 1.8], "Eingaben von forecast_renewables")
code("""
// Beispielantwort, gekürzt; Zahlen erfunden
{ "period": {"from": "2026-12-03T00:00+01:00", "to": "2026-12-09T00:00+01:00"},
  "region": "DE", "resolution": "day",
  "sources": {
    "solar": { "days": [ {"date": "2026-12-03", "p10_gwh": 41, "p50_gwh": 58, "p90_gwh": 72,
                          "lead_day": 1, "official_forecast_gwh": 55}, ... ] },
    "wind_onshore": { ... }, "wind_offshore": { ... } },
  "model_version": "2026-12-01", "trained_until": "2026-11-30",
  "weather_run": {"dwd_icon_d2": "2026-12-02T21:00Z", "dwd_icon": "2026-12-02T18:00Z"},
  "skill": {"solar": {"mae_pct_by_lead_day": [2.1, 2.6, 3.0, 3.4, 3.8, 4.1],
                      "coverage_last_30_days": 0.79}},
  "notes": ["Tag 6 stammt aus ICON global (13 km)."],
  "warnings": [],
  "source": "Bundesnetzagentur | SMARD.de (CC BY 4.0); Wetterdaten: Open-Meteo.com (CC BY 4.0), "
            "Modelle des DWD",
  "server_time": "2026-12-02T23:10:04+01:00" }
""")
h2("Verhalten am Rand")
tabelle(["Fall", "Verhalten"], [
    ["Zeitraum über 6 Tage hinaus", "Fehler, der den letzten möglichen Zeitpunkt nennt"],
    ["Zeitraum in der Vergangenheit", "Fehler mit Hinweis auf get_generation_mix"],
    ["Open-Meteo nicht erreichbar", "zuletzt gespeicherte Vorhersage mit warnings und Alter; ab "
     "12 Stunden Alter ein Fehler"],
    ["Netzbetreiber-Prognose fehlt", "official_forecast weggelassen, Hinweis in notes"],
    ["Feiertag, sonniges Wochenende", "Hinweis auf mögliche Abregelung in notes"],
], [2.4, 5], "Grenzfälle")

# 12 ----------------------------------------------------------------------------
h1("Phase 5 und 6: Monitoring, Neu-Training, Ausrollen (geplant)")
h2("Monitoring")
p("Ein täglicher Job (geplant 06:00 UTC) nimmt die archivierten Vorhersagen, rechnet mit dem "
  "aktuellen Modell die Prognose, die das Tool damals ausgegeben hätte, und vergleicht sie mit "
  "den inzwischen veröffentlichten SMARD-Werten. Der Fehler der letzten 30 Tage je Vorlauftag "
  "erscheint in der Tool-Ausgabe. So sieht jeder Nutzer, wie verlässlich die Zahlen gerade sind, "
  "und nicht nur, wie gut sie im Test waren.")
h2("Monatliches Neu-Training")
bild("workflow", "Automatisch bis zum Pull Request, gemergt wird nur von Hand.")
p("Ein GitHub-Workflow lädt am Monatsanfang den letzten Monat nach, trainiert neu, misst gegen "
  "die Messlatten und gegen das bisherige Modell und öffnet einen Pull Request mit neuen "
  "Modelldateien und Fehlerbericht. Ist das neue Modell schlechter, steht das im Bericht; "
  "gemergt wird nie automatisch.")
h2("Ausrollen und Prüfpunkt C")
liste([
    "Tool auf einem Branch in smard-mcp, Tests grün, TS gegen Python geprüft.",
    "Ausrollen nur mit " + c("npm run deploy") + " (sauberer, gepushter Stand, Tests, Sicherung, "
    "Health-Check, automatisches Zurückrollen).",
    "2 bis 4 Wochen den Fehler im Betrieb beobachten (Monitoring).",
    "<b>Prüfpunkt C:</b> Fehler im Betrieb ähnlich wie im Abschlusstest? Dann Tag und "
    "npm-Release, sonst nachbessern.",
], nummern=True)

# 13 ----------------------------------------------------------------------------
h1("Betrieb und Kosten")
tabelle(["Was", "Wie oft", "Kosten"], [
    ["Archiv-Job", "stündlich prüfen, etwa 8 Abrufe am Tag", "320 Einheiten am Tag, 300 MB im Jahr"],
    ["Wetter für das Tool", "wenn neuer Lauf, etwa 8 Abrufe am Tag", "320 Einheiten am Tag"],
    ["Tool-Anfrage", "je Anfrage", "Millisekunden Rechenzeit"],
    ["Monitoring", "täglich", "Sekunden"],
    ["Neu-Training", "monatlich, GitHub Actions", "Minuten CPU, unter 1 GB RAM"],
    ["Erstdownload", "einmalig", "10.460 Einheiten, 2 Tage"],
], [1.8, 3, 2.6], "Laufende Kosten")
p("Alles zusammen bleibt weit unter 10.000 Einheiten am Tag. Es fallen keine Geldkosten an.")
h2("Wo man nachsieht")
tabelle(["Frage", "Befehl"], [
    ["Läuft der Download?", c("systemctl status smard-forecast-download")],
    ["Fortschritt Download", c("tail -5 /root/smard-forecast/data/logs/download.log")],
    ["Archiv-Timer (Web-Maschine)", c("systemctl list-timers smard-forecast-archiv.timer")],
    ["Letzte Archiv-Läufe", c("journalctl -u smard-forecast-archiv -n 20")],
    ["Archiv-Dateien", c("ls /var/lib/smard-forecast/archiv/2026/11/")],
    ["Bericht neu bauen", c("docs/bericht/abbildungen.py") + " dann " + c("bericht.py")],
], [2.4, 5], "Nützliche Befehle")

# 14 ----------------------------------------------------------------------------
h1("Risiken und offene Fragen")
tabelle(["Risiko", "Folge", "Gegenmaßnahme"], [
    ["Lücken im ICON-Archiv", "weniger Trainingsdaten", "geprüft: nur ein Ausfall; eigenes Archiv"],
    ["Abregelung bei negativen Preisen", "Erzeugung unter dem Wetterwert, vor allem Solar an "
     "Feiertagen", "Wochentag und Feiertag als Merkmal, Hinweis in notes"],
    ["Zubau", "systematischer Versatz", "Monatswerte statt SMARD-Jahreswerte"],
    ["Seltene Wetterlagen (Dunkelflaute, Sturm)", "grobe Ausreißer", "Quantile, Winter getrennt "
     "bewertet"],
    ["Open-Meteo ändert Bedingungen oder fällt aus", "keine Prognose", "Zwischenspeicher mit "
     "warnings, langfristig DWD Open Data als zweite Quelle"],
    ["Wechsel in icon_seamless (z. B. D2-RUC)", "Verteilung der Eingaben ändert sich",
     "Laufzeitpunkte im Archiv, Monitoring zeigt Brüche"],
    ["Lizenz Energy-Charts", "Nenner fehlt", "Rückfall Marktstammdatenregister"],
    ["Lizenz Open-Meteo", "nur nicht-kommerziell frei", "smard-mcp bleibt kostenlos und "
     "werbefrei, sonst API-Key-Tarif"],
], [2.2, 2.4, 2.8], "Risiken")
h2("Offene Fragen")
liste([
    "Lizenz der Energy-Charts-Daten.",
    "Welche Lauffolge liefert icon_seamless in den ersten 48 Stunden genau (D2 oder D2-RUC)?",
    "Bundesweite Feiertage oder gewichtet nach Bundesländern?",
    "Ab wann Tag 7 aus dem eigenen Archiv (frühestens November 2027)?",
])

# 15 ----------------------------------------------------------------------------
h1("Entstehung: das Projekttagebuch")
p("Das vollständige Tagebuch steht in " + c("docs/journal.md") + ". Hier die Fehlschläge und was "
  "daraus gelernt wurde, weil man daraus am meisten mitnimmt.")
tabelle(["Zeit (UTC)", "Was passiert ist", "Ursache", "Lösung, Lehre"], [
    ["02.11. 08:00", "Doku sagt „ab Januar 2024“, Tag 7 fehlt aber ganz", "ICON global reicht "
     "nur 180 h", "Riskanteste Annahme zuerst gegen die echte Quelle prüfen"],
    ["02.11. 08:20", "Tag 1 passt zu keinem Einzellauf", "vermutlich ICON-D2-RUC", "Laufzeitpunkte "
     "aller Modelle archivieren"],
    ["02.11. 08:25", "Single Runs API wäre ideal, beginnt aber erst Mai 2026", "Archivtiefe",
     "nur für Prüfungen nutzen"],
    ["02.11. 08:35", "Auslastung zeigt Scheintrend", "SMARD-Leistung zu niedrig",
     "Plausibilität über Jahre prüfen; Monatswerte"],
    ["02.11. 08:50", "Lückenprüfung bricht nach 11 Orten ab (leere Antwort)",
     "Minutenlimit: 3 s Abstand ergab rund 620 Einheiten/min", "Gewichte rechnen, 10 s Abstand, "
     "jede Antwort speichern"],
    ["02.11. 18:30", "Ausrollen auf die Web-Maschine abgelehnt", "Freigabe-Prüfung von "
     "Claude Code", "Betreuer rollt selbst aus (18:41)"],
    ["02.11. 18:28", "Download startet eine Stunde später als nötig", "zu vorsichtig "
     "vorgebucht", "harmlos; Buchführung genauer schätzen"],
], [1.3, 2.6, 2.2, 2.6], "Fehlschläge und Lehren")
h2("Zeitleiste")
tabelle(["Zeit (UTC)", "Schritt", "Commit"], [
    ["02.11. 08:00", "Konzept geprüft, Tag 7 fehlt", ""],
    ["02.11. 08:14", "Deploy-Key, Plan ins Repo", "f151cfd"],
    ["02.11. 08:20 bis 09:15", "Phase 0: Vorlaufzeit, SMARD, Orte, Lückenprüfung", ""],
    ["02.11. 09:16", "Phase 0 abgeschlossen", "163d455"],
    ["02.11. 18:28", "Download gestartet, Archiv-Job geschrieben", "552f040"],
    ["02.11. 18:37", "Protokollierung und Tagebuch, Download neu gestartet", "109c6f3"],
    ["02.11. 18:41", "Archiv-Job auf der Web-Maschine live", "b0783a5"],
    ["02.11. abends", "dieser Bericht", ""],
], [1.8, 4.4, 1.2], "Zeitleiste")

# 16 ----------------------------------------------------------------------------
h1("Glossar")
tabelle(["Begriff", "Bedeutung"], [
    ["Auslastung", "Erzeugung geteilt durch installierte Leistung (0 bis 1)"],
    ["Abregelung", "Netzbetreiber oder Betreiber drosseln Anlagen, z. B. bei negativen Preisen"],
    ["Bandbreite", "Bereich zwischen p10 und p90"],
    ["Gradient Boosting", "viele kleine Bäume, jeder korrigiert die vorherigen"],
    ["ICON", "Wettermodell des DWD (D2, EU, global)"],
    ["icon_seamless", "Zusammenstellung von Open-Meteo aus D2, EU und global"],
    ["Klimatologie", "Messlatte aus Mittelwerten der Vorjahre"],
    ["Lauf", "eine Rechnung des Wettermodells mit festem Startzeitpunkt"],
    ["MAE", "mittlerer absoluter Fehler"],
    ["MCP", "Model Context Protocol, Schnittstelle zwischen KI-Assistenten und Werkzeugen"],
    ["p10, p50, p90", "10-, 50- und 90-%-Quantil der Vorhersage"],
    ["Persistenz", "Messlatte „wie gestern“"],
    ["Pinball-Verlust", "Fehlermaß, mit dem man Quantile lernt"],
    ["Previous Runs API", "Open-Meteo-Archiv mit Vorhersagen früherer Läufe"],
    ["Prüfpunkt", "Entscheidung, ob das Projekt weitergeht"],
    ["Trefferquote", "Anteil Stunden, in denen der echte Wert in der Bandbreite liegt"],
    ["Vorlaufzeit", "Zielstunde minus Startzeitpunkt des Laufs"],
], [2, 5.4], "Glossar")
p("")
klein("Quellen: Bundesnetzagentur | SMARD.de (CC BY 4.0). Wetterdaten: Open-Meteo.com (CC BY 4.0), "
      "Modelle des DWD. Installierte Leistung: Energy-Charts, Fraunhofer ISE. Kartenumrisse: "
      "Natural Earth (gemeinfrei). Alle Diagramme ohne den Zusatz „Schema“ zeigen echte Werte, "
      "erzeugt mit docs/bericht/abbildungen.py am " + dt.date.today().strftime("%d.%m.%Y") + ".")


def main():
    doc = Bericht(ZIEL)
    doc.multiBuild(story)
    print(ZIEL, ZIEL.stat().st_size)


if __name__ == "__main__":
    sys.exit(main())
