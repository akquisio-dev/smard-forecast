"""Projektbericht smard-forecast als PDF (Lehrbuch-Fassung).

Aufruf (aus dem Repo-Wurzelverzeichnis):
    .venv/bin/python -I docs/bericht/abbildungen.py    # Projektgrafiken
    .venv/bin/python -I docs/bericht/lehrgrafiken.py   # Lehrgrafiken und zahlen.json
    .venv/bin/python -I docs/bericht/ergebnisse.py     # Ergebnisse Phase 2 bis 4
    .venv/bin/python -I docs/bericht/bericht.py        # PDF bauen

Der Text steht in docs/bericht/kapitel/*.txt in einer kleinen Auszeichnungssprache:

    @teil Titel                 Trennseite fuer einen Teil (Folgezeilen: Beschreibung)
    # Titel / ## Titel / ### Titel   Kapitel, Abschnitt, Unterabschnitt
    @anhang                     ab hier Kapitel mit Buchstaben
    Absatz                      Leerzeile trennt Absaetze; **fett**, `code`
    {{z:schluessel:2}}          Zahl aus abb/zahlen.json (2 Nachkommastellen, deutsches Komma)
    - Punkt / 1. Punkt          Listen (Fortsetzungszeilen mit zwei Leerzeichen einruecken)
    $$ LaTeX                    abgesetzte Formel (matplotlib mathtext), wird nummeriert
    [abb name | Unterschrift]   Abbildung aus abb/name.png, optional [abb name 0.7 | ...]
    | a | b |                   Tabelle (erste Zeile Kopf); davor optional "Tabelle: Titel"
    !begriff Name: Erklaerung   Begriffskasten, landet auch im Glossar
    !merke / !rechnen T / !warum T / !achtung T / !praxis T ... !ende   Kaesten
    ```                         Codeblock
    @orte  @glossar  @literatur eingebaute Tabellen und Verzeichnisse
    #* Titel                    Kapitel ohne Nummer (Vorspann, Literaturverzeichnis)
    [@key] [@key, S. 3] [@a; @b] [@!key]   Zitat aus literatur.toml (Autor-Jahr)

Vorspann: kapitel/00a-*.txt steht vor dem Inhaltsverzeichnis (Kurzfassung, Abstract),
kapitel/00b-*.txt nach Abbildungs- und Tabellenverzeichnis (Abkuerzungen).

Ergebnis: docs/bericht/smard-forecast-projektbericht.pdf (nicht im Git).
"""

import hashlib
import json
import re
import sys
import tomllib
from pathlib import Path
from xml.sax.saxutils import escape

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from PIL import Image as PILImage  # noqa: E402
from reportlab.lib import colors  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.styles import ParagraphStyle  # noqa: E402
from reportlab.lib.units import cm  # noqa: E402
from reportlab.pdfbase import pdfmetrics  # noqa: E402
from reportlab.pdfbase.ttfonts import TTFont  # noqa: E402
from reportlab.platypus import (BaseDocTemplate, CondPageBreak, Frame, Image,  # noqa: E402
                                KeepTogether, NextPageTemplate, PageBreak, PageTemplate,
                                Paragraph, Preformatted, Spacer, Table, TableStyle)
from reportlab.platypus.tableofcontents import TableOfContents  # noqa: E402

HIER = Path(__file__).resolve().parent
ROOT = HIER.parents[1]
ABB = HIER / "abb"
FORMELN = ABB / "formeln"
FORMELN.mkdir(parents=True, exist_ok=True)
KAPITEL = HIER / "kapitel"
ZIEL = HIER / "smard-forecast-projektbericht.pdf"
STAND = "3. November 2026"
ZAHLEN = json.loads((ABB / "zahlen.json").read_text())
LIT = tomllib.loads((HIER / "literatur.toml").read_text())
ZITIERT: list[str] = []


def _nachnamen(e):
    namen = [a.split(",")[0] for a in e["autoren"]]
    if len(namen) == 1 and not e.get("weitere"):
        return namen[0]
    if len(namen) == 2 and not e.get("weitere"):
        return f"{namen[0]} und {namen[1]}"
    return f"{namen[0]} u. a."


def _jahre():
    """Autor-Jahr-Marken; gleiche Marken bekommen a, b, ... in Schluesselreihenfolge."""
    gruppen = {}
    for k in sorted(LIT):
        gruppen.setdefault((_nachnamen(LIT[k]), LIT[k]["jahr"]), []).append(k)
    aus = {}
    for (_, jahr), keys in gruppen.items():
        for i, k in enumerate(keys):
            aus[k] = f"{jahr}{'abcdefgh'[i] if len(keys) > 1 else ''}"
    return aus


JAHR = _jahre()


def zitat(m):
    """[@a; @b, S. 3] -> (A 2001; B 2002, S. 3); [@!a] -> A (2001)."""
    teile = []
    erzaehlend = m.group(1) == "!"
    for t in m.group(2).split(";"):
        t = t.strip().lstrip("@")
        key, _, stelle = t.partition(",")
        key = key.strip()
        if key not in LIT:
            raise KeyError(f"Zitat ohne Literatureintrag: {key}")
        if key not in ZITIERT:
            ZITIERT.append(key)
        stelle = f", {stelle.strip()}" if stelle.strip() else ""
        if erzaehlend:
            teile.append(f"{_nachnamen(LIT[key])} ({JAHR[key]}{stelle})")
        else:
            teile.append(f"{_nachnamen(LIT[key])} {JAHR[key]}{stelle}")
    return "; ".join(teile) if erzaehlend else "(" + "; ".join(teile) + ")"


def literatureintrag(key):
    e = LIT[key]
    a = e["autoren"]
    autoren = "; ".join(a[:-1]) + " und " + a[-1] if len(a) > 1 else a[0]
    if e.get("weitere"):
        autoren = "; ".join(a) + " u. a."
    t = f"<b>{escape(autoren)}</b> ({JAHR[key]}): "
    if e["typ"] == "artikel":
        t += f"{escape(e['titel'])}. In: <i>{escape(e['zeitschrift'])}</i>"
        if e.get("band"):
            t += f" {escape(e['band'])}"
        if e.get("heft"):
            t += f" ({escape(e['heft'])})"
        if e.get("seiten"):
            t += f", {'S. ' if e['seiten'][0].isdigit() else ''}{escape(e['seiten'])}"
    elif e["typ"] == "konferenz":
        t += f"{escape(e['titel'])}. In: <i>{escape(e['buchtitel'])}</i>"
        if e.get("seiten"):
            t += f", S. {escape(e['seiten'])}"
    elif e["typ"] in ("buch", "norm"):
        t += f"<i>{escape(e['titel'])}</i>"
        if e.get("auflage"):
            t += f". {e['auflage']}. Aufl"
        t += f". {escape(e['ort'])}: {escape(e['verlag'])}" if e.get("ort") else f". {escape(e['verlag'])}"
    elif e["typ"] == "web":
        t += f"<i>{escape(e['titel'])}</i>"
    t += "."
    if e.get("doi"):
        t += f" DOI: <font face=\"Mono\" size=\"7.5\">{escape(e['doi'])}</font>."
    if e.get("url"):
        t += f" URL: <font face=\"Mono\" size=\"7.5\">{escape(e['url'])}</font>"
        if e.get("abgerufen"):
            t += f" (abgerufen am {e['abgerufen']})"
        t += "."
    if e.get("hinweis"):
        t += f" {escape(e['hinweis'])}."
    return t


if (ABB / "zahlen_ergebnisse.json").exists():  # aus ergebnisse.py (Phasen 2 bis 4)
    ZAHLEN.update(json.loads((ABB / "zahlen_ergebnisse.json").read_text()))

F = "/usr/share/fonts/truetype/dejavu/"
for n, d in (("Sans", "DejaVuSans"), ("Sans-Bold", "DejaVuSans-Bold"), ("Serif", "DejaVuSerif"),
             ("Serif-Bold", "DejaVuSerif-Bold"), ("Mono", "DejaVuSansMono")):
    pdfmetrics.registerFont(TTFont(n, F + d + ".ttf"))
pdfmetrics.registerFontFamily("Sans", normal="Sans", bold="Sans-Bold", italic="Sans",
                              boldItalic="Sans-Bold")

TEXT = colors.HexColor("#0b0b0b")
TEXT2 = colors.HexColor("#52514e")
GRID = colors.HexColor("#e6e5e1")
FLAECHE = colors.HexColor("#f3f3f1")
AKZENT = colors.HexColor("#2a78d6")
WARM = colors.HexColor("#eb6834")
GRUEN = colors.HexColor("#1baf7a")

P = dict(fontName="Sans", textColor=TEXT)
S = {
    "titel": ParagraphStyle("titel", fontName="Serif", fontSize=34, leading=40, textColor=TEXT),
    "untertitel": ParagraphStyle("ut", fontName="Sans", fontSize=13, leading=19,
                                 textColor=TEXT2),
    "teil": ParagraphStyle("teil", fontName="Serif", fontSize=30, leading=36, textColor=TEXT),
    "h1": ParagraphStyle("h1", fontName="Serif", fontSize=20, leading=25, spaceAfter=10,
                         textColor=TEXT),
    "h2": ParagraphStyle("h2", fontName="Serif", fontSize=13.5, leading=17.5, spaceBefore=11,
                         spaceAfter=5, textColor=TEXT),
    "h3": ParagraphStyle("h3", fontName="Sans-Bold", fontSize=9.6, leading=13, spaceBefore=8,
                         spaceAfter=3, textColor=TEXT),
    "p": ParagraphStyle("p", fontSize=9.2, leading=13.8, spaceAfter=5.5, **P),
    "klein": ParagraphStyle("klein", fontSize=7.8, leading=10.5, spaceAfter=3, fontName="Sans",
                            textColor=TEXT2),
    "zelle": ParagraphStyle("zelle", fontSize=7.8, leading=10.2, **P),
    "zellek": ParagraphStyle("zellek", fontName="Sans-Bold", fontSize=7.8, leading=10.2,
                             textColor=TEXT),
    "bild": ParagraphStyle("bild", fontName="Sans", fontSize=7.6, leading=10, textColor=TEXT2,
                           spaceBefore=3, spaceAfter=10),
    "code": ParagraphStyle("code", fontName="Mono", fontSize=7.1, leading=9.3, textColor=TEXT),
    "liste": ParagraphStyle("liste", fontSize=9.2, leading=13.4, leftIndent=13, bulletIndent=2,
                            spaceAfter=2.5, **P),
    "kasten": ParagraphStyle("kasten", fontSize=8.8, leading=12.8, spaceAfter=3, **P),
    "kastenliste": ParagraphStyle("kastenliste", fontSize=8.8, leading=12.6, leftIndent=12,
                                  bulletIndent=2, spaceAfter=2, **P),
    "toc0": ParagraphStyle("toc0", fontName="Serif", fontSize=10.5, leading=17,
                           textColor=TEXT, spaceBefore=6),
    "toc1": ParagraphStyle("toc1", fontName="Sans", fontSize=9.0, leading=13.2,
                           textColor=TEXT, leftIndent=8),
    "toc2": ParagraphStyle("toc2", fontName="Sans", fontSize=7.9, leading=11,
                           textColor=TEXT2, leftIndent=22),
    "literatur": ParagraphStyle("literatur", fontName="Sans", fontSize=8.6, leading=12.2,
                                leftIndent=16, firstLineIndent=-16, spaceAfter=5,
                                textColor=TEXT),
    "fnr": ParagraphStyle("fnr", fontName="Sans", fontSize=8, leading=10, textColor=TEXT2,
                          alignment=2),
}
S["h1u"] = ParagraphStyle("h1u", parent=S["h1"])
BREITE = A4[0] - 4.2 * cm


class Verzeichnis(TableOfContents):
    """Abbildungs- oder Tabellenverzeichnis: hoert auf eine eigene Benachrichtigung."""

    def __init__(self, art):
        super().__init__()
        self.art = art
        self.dotsMinLevel = 0

    def notify(self, kind, stuff):
        if kind == self.art:
            self.addEntry(*stuff)


def kurztitel(text, n=92):
    """Unterschrift fuer ein Verzeichnis: erster Satz, hoechstens n Zeichen."""
    t = re.split(r"(?<=[a-zäöüß)])\. ", text, maxsplit=1)[0].rstrip(".")
    return t if len(t) <= n else t[:n].rsplit(" ", 1)[0] + " …"


class Bericht(BaseDocTemplate):
    def __init__(self, ziel):
        super().__init__(str(ziel), pagesize=A4, leftMargin=2.1 * cm, rightMargin=2.1 * cm,
                         topMargin=2.2 * cm, bottomMargin=2.0 * cm,
                         title="smard-forecast | Projektbericht", author="akquisio-dev",
                         subject="Prognose der Erneuerbaren für smard-mcp")
        rahmen = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="f")
        self.addPageTemplates([
            PageTemplate("titel", [rahmen], onPage=self.flaeche),
            PageTemplate("teil", [rahmen], onPage=self.flaeche),
            PageTemplate("normal", [rahmen], onPageEnd=self.seite)])

    def beforeDocument(self):
        self.kapitel = ""

    def flaeche(self, c, doc):
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
        c.drawRightString(A4[0] - 2.1 * cm, A4[1] - 1.3 * cm, self.kapitel[:80])
        c.setStrokeColor(GRID)
        c.setLineWidth(0.6)
        c.line(2.1 * cm, A4[1] - 1.5 * cm, A4[0] - 2.1 * cm, A4[1] - 1.5 * cm)
        c.drawString(2.1 * cm, 1.1 * cm, f"Stand {STAND}")
        c.drawRightString(A4[0] - 2.1 * cm, 1.1 * cm, f"Seite {doc.page}")
        c.restoreState()

    def afterFlowable(self, fl):
        if isinstance(fl, Paragraph) and fl.style.name == "inh":
            self.kapitel = fl.getPlainText()
            return
        if isinstance(fl, Paragraph) and fl.style.name == "bild":
            text = fl.getPlainText()
            m = re.match(r"^(Abbildung|Tabelle) (\d+): (.*)$", text, re.S)
            if m:
                key = f"v{id(fl)}"
                self.canv.bookmarkPage(key)
                art = "LOF" if m.group(1) == "Abbildung" else "LOT"
                self.notify(art, (0, f"{m.group(2)}  {kurztitel(m.group(3))}", self.page, key))
            return
        if isinstance(fl, Paragraph) and fl.style.name in ("teil", "h1u", "h1", "h2"):
            text = fl.getPlainText()
            stufe = {"teil": 0, "h1u": 0, "h1": 1, "h2": 2}[fl.style.name]
            if fl.style.name in ("h1", "h1u"):
                self.kapitel = text
            key = f"k{id(fl)}"
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(text, key, level=stufe, closed=stufe > 0)
            self.notify("TOCEntry", (stufe, text, self.page, key))


# Hilfen ------------------------------------------------------------------------
NR = {"teil": 0, "kap": 0, "abs": 0, "abb": 0, "tab": 0, "formel": 0, "anhang": False,
      "kapnr": ""}
GLOSSAR = {}
ROEMISCH = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII"]


def zahl(schluessel, stellen=None):
    v = ZAHLEN
    teile = schluessel.split(".")
    while teile:
        if isinstance(v, list):
            v = v[int(teile.pop(0))]
            continue
        for k in range(len(teile), 0, -1):  # laengsten passenden Schluessel nehmen
            if ".".join(teile[:k]) in v:
                v = v[".".join(teile[:k])]
                teile = teile[k:]
                break
        else:
            raise KeyError(schluessel)
    if isinstance(v, (int, float)) and stellen is not None:
        s = f"{v:,.{int(stellen)}f}"
    elif isinstance(v, (int, float)):
        s = f"{v:,}"
    else:
        return str(v)
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def inline(t):
    t = re.sub(r"\{\{z:([\w.\-]+)(?::(\d))?\}\}", lambda m: zahl(m.group(1), m.group(2)), t)
    t = re.sub(r"\[@(!?)([^\]]+)\]", zitat, t)
    teile = re.split(r"(`[^`]+`)", t)
    aus = []
    for x in teile:
        if x.startswith("`") and x.endswith("`") and len(x) > 1:
            aus.append(f'<font face="Mono" size="8">{escape(x[1:-1])}</font>')
        else:
            x = escape(x)
            x = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", x)
            aus.append(x)
    return "".join(aus)


def formel_bild(tex, groesse=12.5):
    key = hashlib.sha1(f"{tex}{groesse}".encode()).hexdigest()[:16]
    pfad = FORMELN / f"{key}.png"
    if not pfad.exists():
        fig = plt.figure(figsize=(0.01, 0.01))
        fig.text(0, 0, f"${tex}$", fontsize=groesse, color="#0b0b0b")
        fig.savefig(pfad, dpi=300, bbox_inches="tight", pad_inches=0.04, transparent=True)
        plt.close(fig)
    w, h = PILImage.open(pfad).size
    return pfad, w / 300 * 72, h / 300 * 72


def formel(tex):
    NR["formel"] += 1
    pfad, w, h = formel_bild(tex)
    if w > BREITE - 2 * cm:
        f = (BREITE - 2 * cm) / w
        w, h = w * f, h * f
    img = Image(str(pfad), width=w, height=h)
    tab = Table([[img, Paragraph(f"({NR['formel']})", S["fnr"])]],
                colWidths=[BREITE - 1.4 * cm, 1.4 * cm])
    tab.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                             ("ALIGN", (0, 0), (0, 0), "CENTER"),
                             ("TOPPADDING", (0, 0), (-1, -1), 3),
                             ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    return tab


def bild(name, text, breite=1.0):
    NR["abb"] += 1
    pfad = ABB / f"{name}.png"
    w, h = PILImage.open(pfad).size
    bw = BREITE * breite
    bh = bw * h / w
    if bh > 19 * cm:
        bh = 19 * cm
        bw = bh * w / h
    return KeepTogether([Spacer(1, 3), Image(str(pfad), width=bw, height=bh),
                         Paragraph(f"<b>Abbildung {NR['abb']}:</b> {inline(text)}", S["bild"])])


def code(t):
    pre = Preformatted(t.strip("\n"), S["code"])
    tab = Table([[pre]], colWidths=[BREITE])
    tab.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), FLAECHE),
                             ("LEFTPADDING", (0, 0), (-1, -1), 8),
                             ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                             ("TOPPADDING", (0, 0), (-1, -1), 6),
                             ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    return [tab, Spacer(1, 7)]


def tabelle(zeilen, titel=None, breite=BREITE):
    NR["tab"] += 1
    kopf, *rest = zeilen
    daten = [[Paragraph(inline(k), S["zellek"]) for k in kopf]]
    for z in rest:
        z = list(z) + [""] * (len(kopf) - len(z))
        daten.append([Paragraph(inline(str(x)), S["zelle"]) for x in z])
    laengen = [max(len(str(z[i])) if i < len(z) else 0 for z in zeilen)
               for i in range(len(kopf))]
    gew = [min(max(l, 9), 60) for l in laengen]
    breiten = [breite * g / sum(gew) for g in gew]
    tab = Table(daten, colWidths=breiten, repeatRows=1)
    tab.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, 0), 0.9, TEXT), ("LINEBELOW", (0, 1), (-1, -1), 0.4, GRID),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    aus = []
    if titel:
        aus.append(Paragraph(f"<b>Tabelle {NR['tab']}:</b> {inline(titel)}", S["bild"]))
    aus.append(tab)
    if len(rest) < 16:
        return [KeepTogether(aus), Spacer(1, 9)]
    return aus + [Spacer(1, 9)]


KASTEN = {"begriff": ("Begriff", AKZENT), "merke": ("Merke", GRUEN),
          "rechnen": ("Rechenbeispiel", WARM), "warum": ("Hintergrund", TEXT2),
          "achtung": ("Achtung", WARM), "praxis": ("Im Projekt", AKZENT)}


def kasten(art, titel, inhalt_flows):
    name, farbe = KASTEN[art]
    kopf = f"<b>{name}{': ' + inline(titel) if titel else ''}</b>"
    # eine Zeile je Baustein, damit lange Kaesten ueber Seiten umbrechen koennen
    teile = [Paragraph(kopf, S["kasten"])]
    for f in inhalt_flows:
        if isinstance(f, KeepTogether):
            teile += f._content
        elif not isinstance(f, Spacer):
            teile.append(f)
    tab = Table([[t] for t in teile], colWidths=[BREITE])
    tab.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), FLAECHE),
                             ("LINEBEFORE", (0, 0), (0, -1), 2.4, farbe),
                             ("LEFTPADDING", (0, 0), (-1, -1), 10),
                             ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                             ("TOPPADDING", (0, 0), (-1, -1), 2),
                             ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                             ("TOPPADDING", (0, 0), (-1, 0), 7),
                             ("BOTTOMPADDING", (0, -1), (-1, -1), 7)]))
    if len(teile) <= 3:
        return [KeepTogether([tab]), Spacer(1, 8)]
    return [tab, Spacer(1, 8)]


BLOCKSTART = re.compile(r"^\s*(#|- |\d+\. |\||\$\$|\[abb|```|!|@|Tabelle:)")


# Parser ------------------------------------------------------------------------
def bloecke(text, im_kasten=False):
    zeilen = text.split("\n")
    aus = []
    i = 0
    stil_p = S["kasten"] if im_kasten else S["p"]
    stil_l = S["kastenliste"] if im_kasten else S["liste"]
    tab_titel = None
    while i < len(zeilen):
        s = zeilen[i].strip()
        if not s or s.startswith("%"):
            i += 1
            continue
        if s.startswith("```"):
            j = i + 1
            while not zeilen[j].strip().startswith("```"):
                j += 1
            aus += code("\n".join(zeilen[i + 1:j]))
            i = j + 1
            continue
        if s.startswith("!begriff"):
            m = re.match(r"!begriff\s+([^:]+):\s*(.*)", s)
            name, erkl = m.group(1).strip(), m.group(2)
            j = i + 1
            while j < len(zeilen) and zeilen[j].strip() and not BLOCKSTART.match(zeilen[j]):
                erkl += " " + zeilen[j].strip()
                j += 1
            GLOSSAR.setdefault(name, erkl)
            aus += kasten("begriff", name, [Paragraph(inline(erkl), S["kasten"])])
            i = j
            continue
        if s.startswith("!") and not s.startswith("!ende"):
            m = re.match(r"!(\w+)\s*(.*)", s)
            art, titel = m.group(1), m.group(2)
            j = i + 1
            while not zeilen[j].strip().startswith("!ende"):
                j += 1
            aus += kasten(art, titel, bloecke("\n".join(zeilen[i + 1:j]), True))
            i = j + 1
            continue
        if s.startswith("@teil"):
            NR["teil"] += 1
            aus += [NextPageTemplate("teil"), PageBreak(), Spacer(1, 6 * cm),
                    Paragraph(f"Teil {ROEMISCH[NR['teil'] - 1]}", S["untertitel"]),
                    Spacer(1, 8), Paragraph(inline(s[5:].strip()), S["teil"])]
            j = i + 1
            beschr = []
            while j < len(zeilen) and zeilen[j].strip():
                beschr.append(zeilen[j].strip())
                j += 1
            if beschr:
                aus += [Spacer(1, 18), Paragraph(inline(" ".join(beschr)), S["untertitel"])]
            aus += [NextPageTemplate("normal")]
            i = j
            continue
        if s == "@anhang":
            NR["anhang"] = True
            NR["kap"] = 0
            i += 1
            continue
        if s.startswith("#* "):
            aus += [PageBreak(), Paragraph(inline(s[3:]), S["h1u"])]
            NR["kapnr"] = ""
            i += 1
            continue
        if s == "@literatur":
            aus.append(("LITERATUR",))
            i += 1
            continue
        if s.startswith("# "):
            NR["kap"] += 1
            NR["abs"] = 0
            nr = chr(64 + NR["kap"]) if NR["anhang"] else str(NR["kap"])
            NR["kapnr"] = nr
            aus += [PageBreak(), Paragraph(f"{nr}  {inline(s[2:])}", S["h1"])]
            i += 1
            continue
        if s.startswith("## "):
            NR["abs"] += 1
            nummer = f"{NR['kapnr']}.{NR['abs']}  " if NR["kapnr"] else ""
            aus += [CondPageBreak(5 * cm), Paragraph(f"{nummer}{inline(s[3:])}", S["h2"])]
            i += 1
            continue
        if s.startswith("### "):
            aus += [CondPageBreak(3 * cm), Paragraph(inline(s[4:]), S["h3"])]
            i += 1
            continue
        if s.startswith("$$"):
            aus.append(formel(s[2:].strip()))
            i += 1
            continue
        if s.startswith("[abb"):
            m = re.match(r"\[abb\s+(\S+)(?:\s+([\d.]+))?\s*\|\s*(.*)\]$", s)
            aus.append(bild(m.group(1), m.group(3), float(m.group(2) or 1)))
            i += 1
            continue
        if s.startswith("Tabelle:"):
            tab_titel = s[8:].strip()
            i += 1
            continue
        if s.startswith("|"):
            j = i
            rows = []
            while j < len(zeilen) and zeilen[j].strip().startswith("|"):
                r = [c.strip() for c in zeilen[j].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in r):
                    rows.append(r)
                j += 1
            aus += tabelle(rows, tab_titel, BREITE - (22 if im_kasten else 0))
            tab_titel = None
            i = j
            continue
        if s == "@orte":
            orte = tomllib.loads((ROOT / "config" / "orte.toml").read_text())["ort"]
            rows = [["Name", "Breite", "Länge", "Typ"]] + [
                [o["name"], f"{o['lat']:.2f}".replace(".", ","),
                 f"{o['lon']:.2f}".replace(".", ","), ", ".join(o["typ"])] for o in orte]
            aus += tabelle(rows, "Alle 40 Wetterorte aus config/orte.toml")
            i += 1
            continue
        if s == "@glossar":
            aus.append(("GLOSSAR",))
            i += 1
            continue
        if re.match(r"^(- |\d+\. )", s):
            j = i
            while j < len(zeilen) and re.match(r"^(- |\d+\. )", zeilen[j].strip()) \
                    and not zeilen[j].startswith("  "):
                t = zeilen[j].strip()
                k = j + 1
                while k < len(zeilen) and zeilen[k].startswith("  ") and zeilen[k].strip():
                    t += " " + zeilen[k].strip()
                    k += 1
                m = re.match(r"^(- |(\d+)\. )(.*)", t)
                aus.append(Paragraph(inline(m.group(3)), stil_l,
                                     bulletText="•" if m.group(1) == "- " else f"{m.group(2)}."))
                j = k
            aus.append(Spacer(1, 4))
            i = j
            continue
        j = i
        teile = []
        while j < len(zeilen) and zeilen[j].strip() and (j == i or not BLOCKSTART.match(
                zeilen[j])):
            teile.append(zeilen[j].strip())
            j += 1
        aus.append(Paragraph(inline(" ".join(teile)), stil_p))
        i = j
    return aus


def main():
    story = [NextPageTemplate("titel"), Spacer(1, 5.2 * cm),
             Paragraph("smard-forecast", S["titel"]), Spacer(1, 10),
             Paragraph("Wahrscheinlichkeits-Prognose für Solar, Wind an Land und Wind auf See "
                       "bis 6 Tage voraus, als neues Tool für smard-mcp", S["untertitel"]),
             Spacer(1, 1.2 * cm),
             Paragraph("Projektbericht und Lehrbuch: von Watt und Sonnenstand über Quantile "
                       "und Entscheidungsbäume bis zum laufenden Betrieb. Jeder Fachbegriff "
                       "wird bei seiner ersten Verwendung erklärt.", S["p"]),
             Spacer(1, 4.5 * cm)]
    for z in [f"Stand: {STAND}", "Repository: github.com/akquisio-dev/smard-forecast",
              "Zielprojekt: github.com/akquisio-dev/smard-mcp (v1.3.0)",
              "Status: Phasen 0 bis 4 abgeschlossen (Tool auf einem Nebenzweig, nicht ausgerollt); "
              "Prüfung der Vorlauf-Interpolation läuft",
              "Alle Diagramme ohne den Zusatz „Schema“ zeigen echte Daten."]:
        story.append(Paragraph(z, S["klein"]))
    story += [NextPageTemplate("normal")]
    for datei in sorted(KAPITEL.glob("00a-*.txt")):
        story += bloecke(datei.read_text())
    titel_stil = ParagraphStyle("inh", parent=S["h1"])
    story += [PageBreak(), Paragraph("Inhaltsverzeichnis", titel_stil)]
    toc = TableOfContents()
    toc.levelStyles = [S["toc0"], S["toc1"], S["toc2"]]
    story.append(toc)
    for art, titel in (("LOF", "Abbildungsverzeichnis"), ("LOT", "Tabellenverzeichnis")):
        v = Verzeichnis(art)
        v.levelStyles = [S["toc2"]]
        story += [PageBreak(), Paragraph(titel, titel_stil), v]
    for datei in sorted(KAPITEL.glob("00b-*.txt")):
        story += bloecke(datei.read_text())
    for datei in sorted(KAPITEL.glob("*.txt")):
        if datei.name.startswith("00"):
            continue
        story += bloecke(datei.read_text())
    fertig = []
    for f in story:
        if isinstance(f, tuple) and f[0] == "GLOSSAR":
            rows = [["Begriff", "Erklärung"]] + [[k, v] for k, v in
                                                  sorted(GLOSSAR.items(),
                                                         key=lambda x: x[0].lower())]
            fertig += tabelle(rows, f"Alle {len(GLOSSAR)} Begriffe aus den Begriffskästen")
        elif isinstance(f, tuple) and f[0] == "LITERATUR":
            reihe = sorted(ZITIERT, key=lambda k: (_nachnamen(LIT[k]).lower(), JAHR[k]))
            for k in reihe:
                fertig.append(Paragraph(literatureintrag(k), S["literatur"]))
        else:
            fertig.append(f)
    ungenutzt = sorted(set(LIT) - set(ZITIERT))
    if ungenutzt:
        print("nicht zitiert (nicht im Verzeichnis):", ", ".join(ungenutzt))
    Bericht(ZIEL).multiBuild(fertig)
    print(ZIEL, ZIEL.stat().st_size, "Abbildungen", NR["abb"], "Tabellen", NR["tab"],
          "Formeln", NR["formel"], "Begriffe", len(GLOSSAR))


if __name__ == "__main__":
    sys.exit(main())
