"""Abbildungen fuer den Projektbericht (docs/bericht/). Liest echte Daten aus data/.

Aufruf: .venv/bin/python -I docs/bericht/abbildungen.py
Schreibt PNGs nach docs/bericht/abb/. Schematische Abbildungen sind im Titel als
"Schema" gekennzeichnet; alle anderen zeigen echte Werte.
"""

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Polygon, Rectangle  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from sf.orte import lade_orte  # noqa: E402

AUS = Path(__file__).resolve().parent / "abb"
AUS.mkdir(exist_ok=True)
DATA = ROOT / "data"

# Farben: Referenzpalette (dataviz), feste Reihenfolge je Quelle, ueberall gleich
TEXT, TEXT2, MUTED, GRID, FLAECHE = "#0b0b0b", "#52514e", "#8a8984", "#e6e5e1", "#f3f3f1"
QUELLE = {"wind_onshore": "#2a78d6", "solar": "#eb6834", "wind_offshore": "#1baf7a"}
NAME = {"wind_onshore": "Wind an Land", "solar": "Solar", "wind_offshore": "Wind auf See"}
NEUTRAL = "#9a9994"

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 8.5, "text.color": TEXT,
    "axes.edgecolor": GRID, "axes.labelcolor": TEXT2, "axes.titlesize": 9.5,
    "axes.titleweight": "normal", "axes.titlelocation": "left", "axes.titlecolor": TEXT,
    "xtick.color": TEXT2, "ytick.color": TEXT2, "axes.grid": True, "grid.color": GRID,
    "grid.linewidth": 0.6, "axes.spines.top": False, "axes.spines.right": False,
    "legend.frameon": False, "lines.linewidth": 1.6, "savefig.dpi": 220,
    "figure.dpi": 110,
})


def speichern(fig, name):
    fig.savefig(AUS / f"{name}.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("abb", name)


def kapazitaet_monatlich() -> pd.Series:
    k = pd.read_parquet(DATA / "kapazitaet.parquet").set_index("monat")
    return k


def erzeugung(quelle):
    g = pd.read_parquet(DATA / "smard" / f"generation_{quelle}.parquet").dropna()
    g["lokal"] = g.zeit.dt.tz_convert("Europe/Berlin")
    return g


# 1 Karte der Wetterorte ------------------------------------------------------
def karte():
    laender = json.loads((Path(__file__).parent / "assets" / "laender.geo.json").read_text())
    fig, ax = plt.subplots(figsize=(6.2, 7.2))
    for f in laender["features"]:
        polys = f["geometry"]["coordinates"]
        if f["geometry"]["type"] == "Polygon":
            polys = [polys]
        for p in polys:
            xy = np.array(p[0])
            de = f["properties"]["a3"] == "DEU"
            ax.add_patch(Polygon(xy, closed=True, facecolor=FLAECHE if de else "#fafaf9",
                                 edgecolor="#c9c8c2" if de else GRID, linewidth=0.8 if de else 0.5,
                                 zorder=1))
    orte = lade_orte()
    reihen = [("wind_onshore", "wind"), ("solar", "solar"), ("wind_offshore", "offshore")]
    for q, typ in reihen:
        o = [x for x in orte if typ in x.typ]
        dx = 0.06 if (typ == "wind") else (-0.06 if typ == "solar" else 0)
        xs = [x.lon + (dx if len(x.typ) > 1 else 0) for x in o]
        ax.scatter(xs, [x.lat for x in o], s=46, color=QUELLE[q], edgecolor="white",
                   linewidth=1.2, zorder=3, label=f"{NAME[q]} ({len(o)})")
    for x in orte:
        versatz = {"nordsee_borkum": (-4, -10), "nordsee_godewind": (5, 2)}.get(x.name, (5, -3))
        ax.annotate(x.name.replace("nordsee_", "").replace("ostsee_", "").replace("_", " "),
                    (x.lon, x.lat), xytext=versatz, textcoords="offset points", fontsize=6,
                    color=TEXT2, zorder=4)
    ax.text(6.2, 54.85, "Nordsee", color=MUTED, fontsize=8, style="italic")
    ax.text(12.6, 55.15, "Ostsee", color=MUTED, fontsize=8, style="italic")
    ax.set_xlim(5.4, 15.4)
    ax.set_ylim(47.1, 55.6)
    ax.set_aspect(1 / np.cos(np.radians(51)))
    ax.grid(False)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.legend(loc="lower right", fontsize=7.5, handletextpad=0.3)
    ax.set_title("40 Wetterorte aus config/orte.toml (Magdeburg und Cottbus zählen doppelt)")
    ax.text(5.45, 47.15, "Umrisse: Natural Earth (gemeinfrei)", fontsize=5.5, color=MUTED)
    speichern(fig, "karte")


# 2 Installierte Leistung: SMARD-Jahreswert gegen Monatswert -------------------
def kapazitaet():
    k = kapazitaet_monatlich()
    k = k[k.index >= "2024-01"]
    fig, axs = plt.subplots(1, 3, figsize=(7.4, 2.5), sharex=False)
    for ax, q in zip(axs, ["solar", "wind_onshore", "wind_offshore"]):
        s = pd.read_parquet(DATA / "smard" / f"capacity_{q}.parquet").set_index("jahr").mw
        x = pd.to_datetime(k.index + "-01")
        ax.plot(x, k[q] / 1000, color=QUELLE[q], label="Energy-Charts, monatlich")
        sx, sy = [], []
        for j in (2024, 2025, 2026):
            sx += [pd.Timestamp(f"{j}-01-01"), pd.Timestamp(f"{j}-12-31")]
            sy += [s[j] / 1000] * 2
        sx_arr = pd.to_datetime(sx)
        msk = sx_arr <= x.max()
        ax.plot(np.array(sx_arr)[msk], np.array(sy)[msk], color=NEUTRAL, linestyle=(0, (3, 2)),
                label="SMARD, Jahreswert")
        ax.set_title(NAME[q])
        ax.set_ylabel("GW")
        ax.tick_params(axis="x", labelsize=6.5)
        ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%m.%y"))
        ax.xaxis.set_major_locator(matplotlib.dates.MonthLocator(bymonth=[1, 7]))
        ax.annotate(f"{k[q].iloc[-1]/1000:.1f}", (x[-1], k[q].iloc[-1] / 1000), xytext=(-12, 5),
                    textcoords="offset points", fontsize=7, color=TEXT)
    axs[0].legend(loc="upper left", fontsize=6.5)
    fig.tight_layout()
    speichern(fig, "kapazitaet")


# 3 Auslastung mit beiden Nennern ---------------------------------------------
def auslastung_nenner():
    k = kapazitaet_monatlich()
    fig, axs = plt.subplots(1, 3, figsize=(7.4, 2.4))
    for ax, q in zip(axs, ["solar", "wind_onshore", "wind_offshore"]):
        g = erzeugung(q)
        g["jahr"] = g.lokal.dt.year
        g["monat"] = g.lokal.dt.strftime("%Y-%m")
        cap_j = pd.read_parquet(DATA / "smard" / f"capacity_{q}.parquet").set_index("jahr").mw
        g["a_smard"] = g.mwh / g.jahr.map(cap_j)
        g["a_monat"] = g.mwh / g.monat.map(k[q])
        r = g.groupby("jahr")[["a_smard", "a_monat"]].quantile(0.99)
        x = np.arange(len(r))
        ax.bar(x - 0.19, r.a_smard, width=0.36, color=NEUTRAL, label="Nenner SMARD-Jahreswert")
        ax.bar(x + 0.19, r.a_monat, width=0.36, color=QUELLE[q], label="Nenner Monatswert")
        for i, (a, b) in enumerate(zip(r.a_smard, r.a_monat)):
            ax.text(i - 0.19, a + 0.01, f"{a:.2f}", ha="center", fontsize=6, color=TEXT2)
            ax.text(i + 0.19, b + 0.01, f"{b:.2f}", ha="center", fontsize=6, color=TEXT)
        ax.set_xticks(x, [str(j) for j in r.index])
        ax.set_ylim(0, 1.05)
        ax.set_title(NAME[q])
        ax.grid(axis="x", visible=False)
    axs[0].set_ylabel("99%-Quantil der Auslastung")
    from matplotlib.patches import Patch
    fig.legend(handles=[Patch(color=NEUTRAL, label="Nenner: SMARD-Jahreswert"),
                        Patch(color="#5a5955", label="Nenner: Monatswert (Farbe der Quelle)")],
               loc="lower center", ncol=2, fontsize=6.8, bbox_to_anchor=(0.5, -0.06))
    fig.tight_layout()
    speichern(fig, "auslastung_nenner")


# 4 Datenverfuegbarkeit im ICON-Archiv ----------------------------------------
def verfuegbarkeit():
    fig, ax = plt.subplots(figsize=(7.4, 3.0))
    start = pd.Timestamp("2024-01-01")
    ende = pd.Timestamp("2026-11-01")
    zeilen = []
    for n in range(1, 8):
        zeilen.append((f"Temperatur, Tag {n}", None if n == 7 else pd.Timestamp(2024, 1, 18 + n)))
    for n in (1, 6):
        zeilen.append((f"Wind 100 m, Tag {n}", pd.Timestamp("2024-02-16") if n == 1
                       else pd.Timestamp("2024-02-21")))
    for i, (name, ab) in enumerate(zeilen):
        y = len(zeilen) - i
        if ab is None:
            ax.text(pd.Timestamp("2024-03-10"), y, "im Archiv nie vorhanden", va="center",
                    fontsize=7, color=TEXT2)
        else:
            ax.barh(y, (ende - ab).days, left=ab, height=0.55, color=QUELLE["wind_onshore"])
        ax.text(start - pd.Timedelta(days=8), y, name, ha="right", va="center", fontsize=7)
    # Ausfall April 2026 (Tag 2, 4, 5, 6)
    for n in (2, 4, 5, 6):
        y = len(zeilen) - (n - 1)
        ax.barh(y, 4, left=pd.Timestamp("2026-04-10"), height=0.75, color="white")
    ax.axvline(pd.Timestamp("2024-02-22"), color=TEXT, linewidth=1)
    ax.text(pd.Timestamp("2024-02-26"), len(zeilen) + 0.75, "Trainingsbeginn 22.02.2024",
            fontsize=7)
    ax.text(pd.Timestamp("2026-04-12"), len(zeilen) - 6, "Lücke oben: Ausfall 10. bis 13.04.2026",
            ha="center", va="center", fontsize=6.5, color=TEXT2)
    ax.set_yticks([])
    ax.set_xlim(start, ende)
    ax.set_ylim(0.3, len(zeilen) + 1.2)
    ax.grid(axis="y", visible=False)
    ax.set_title("Previous Runs API, icon_seamless: ab wann gibt es Werte je Vorlauftag")
    speichern(fig, "verfuegbarkeit")


# 5 Vorlaufzeit: Previous Runs gegen Historical Forecast (Schema) --------------
def vorlauf_schema():
    fig, axs = plt.subplots(2, 1, figsize=(7.4, 3.6), sharex=True)
    T = 96  # Zielstunde (h)
    for ax, titel in zip(axs, ["Historical Forecast API: setzt die ersten Stunden jedes Laufs "
                               "zusammen (Schema)",
                               "Previous Runs API, Tag 3: Wert aus dem Lauf mindestens 72 h vorher "
                               "(Schema)"]):
        ax.set_title(titel, fontsize=8.5)
        ax.set_ylim(0, 3)
        ax.set_yticks([])
        ax.grid(False)
        for r in range(0, 121, 6):
            ax.plot([r], [0.5], marker="o", color=NEUTRAL, markersize=4)
    ax = axs[0]
    for r in range(0, 120, 6):
        ax.add_patch(Rectangle((r, 1.1), 6, 0.8, facecolor=QUELLE["wind_onshore"] if r == 90
                               else "#d5e4f6", edgecolor="white", linewidth=1))
    ax.annotate("Zielstunde: Vorlauf 0 bis 5 h", (T, 1.9), xytext=(T - 40, 2.6), fontsize=7,
                arrowprops=dict(arrowstyle="->", color=TEXT2, linewidth=0.8))
    ax = axs[1]
    lauf = 24
    ax.add_patch(Rectangle((lauf, 1.1), 168, 0.8, facecolor="#d5e4f6", edgecolor="none"))
    ax.add_patch(Rectangle((T, 1.1), 1.5, 0.8, facecolor=QUELLE["wind_onshore"]))
    ax.add_patch(FancyArrowPatch((lauf, 0.5), (T, 1.1), arrowstyle="->", mutation_scale=10,
                                 color=TEXT, linewidth=1, connectionstyle="arc3,rad=-0.25"))
    ax.text(lauf + 2, 2.3, f"Lauf bei {lauf} h, Vorhersage reicht 180 h", fontsize=7)
    ax.text(T + 3, 2.3, f"Zielstunde {T} h: Vorlauf {T - lauf} h", fontsize=7)
    axs[1].set_xlabel("Stunden; graue Punkte: Startzeitpunkte der Läufe (alle 6 h)")
    axs[1].set_xlim(-2, 124)
    fig.tight_layout()
    speichern(fig, "vorlauf_schema")


# 6 Eine Woche Ist gegen Netzbetreiber-Prognose -------------------------------
def woche():
    von, bis = pd.Timestamp("2026-06-15", tz="Europe/Berlin"), pd.Timestamp("2026-06-22",
                                                                          tz="Europe/Berlin")
    fig, axs = plt.subplots(1, 2, figsize=(7.4, 2.5), sharey=False)
    for ax, q in zip(axs, ["solar", "wind_onshore"]):
        g = erzeugung(q)
        f = pd.read_parquet(DATA / "smard" / f"forecast_generation_{q}.parquet").dropna()
        f["lokal"] = f.zeit.dt.tz_convert("Europe/Berlin")
        g = g[(g.lokal >= von) & (g.lokal < bis)]
        f = f[(f.lokal >= von) & (f.lokal < bis)]
        ax.plot(g.lokal, g.mwh / 1000, color=QUELLE[q], label="Ist (SMARD)")
        ax.plot(f.lokal, f.mwh / 1000, color=TEXT2, linewidth=1.1, linestyle=(0, (3, 2)),
                label="Prognose Netzbetreiber (Vortag)")
        mae = (g.set_index("zeit").mwh - f.set_index("zeit").mwh).abs().mean() / 1000
        ax.set_title(f"{NAME[q]}, 15. bis 21.06.2026 (MAE {mae:.1f} GW)")
        ax.set_ylabel("GW")
        ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%d.%m", tz="Europe/Berlin"))
        ax.tick_params(axis="x", labelsize=6.5)
    from matplotlib.lines import Line2D
    fig.legend(handles=[Line2D([], [], color="#5a5955", label="Ist (SMARD, Farbe der Quelle)"),
                        Line2D([], [], color=TEXT2, linestyle=(0, (3, 2)), linewidth=1.1,
                               label="Prognose der Netzbetreiber (Vortag)")],
               loc="lower center", ncol=2, fontsize=6.8, bbox_to_anchor=(0.5, -0.07))
    fig.tight_layout()
    speichern(fig, "woche")


# 7 Klimatologie-Messlatte Solar: Auslastung je Monat und Stunde ---------------
def klimatologie():
    k = kapazitaet_monatlich()
    g = erzeugung("solar")
    g = g[g.lokal < pd.Timestamp("2026-01-01", tz="Europe/Berlin")]
    g["a"] = g.mwh / g.lokal.dt.strftime("%Y-%m").map(k["solar"])
    m = g.groupby([g.lokal.dt.month, g.lokal.dt.hour]).a.mean().unstack()
    cmap = LinearSegmentedColormap.from_list("seq", ["#fdf3ee", "#f6b694", "#eb6834", "#8a3412"])
    fig, ax = plt.subplots(figsize=(7.4, 2.9))
    im = ax.imshow(m.values, aspect="auto", cmap=cmap, vmin=0, origin="upper")
    ax.set_yticks(range(12), ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep",
                              "Okt", "Nov", "Dez"], fontsize=7)
    ax.set_xticks(range(0, 24, 2), [f"{h}" for h in range(0, 24, 2)], fontsize=7)
    ax.set_xlabel("Stunde (Ortszeit)")
    ax.grid(False)
    cb = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.01)
    cb.set_label("mittlere Auslastung", fontsize=7)
    cb.ax.tick_params(labelsize=6.5)
    cb.outline.set_visible(False)
    peak = m.values.max()
    i, j = np.unravel_index(m.values.argmax(), m.shape)
    ax.text(j, i, f"{peak:.2f}", ha="center", va="center", fontsize=6.5, color="white")
    ax.set_title("Solar 2024 und 2025: mittlere Auslastung je Monat und Stunde "
                 "(so sieht die Messlatte Klimatologie aus)")
    speichern(fig, "klimatologie")


# 8 Rollierende Validierung (Schema mit echten Monaten) -----------------------
def validierung():
    monate = pd.period_range("2024-03", "2026-10", freq="M")
    fig, ax = plt.subplots(figsize=(7.4, 3.0))
    abschluss = monate[-3:]
    tests = monate[12:-3]
    zeige = list(tests[::3]) + [tests[-1]]
    for i, t in enumerate(zeige):
        y = len(zeige) - i
        n_train = list(monate).index(t)
        ax.barh(y, n_train, left=0, height=0.6, color="#d9d8d3")
        ax.barh(y, 1, left=n_train, height=0.6, color=QUELLE["wind_onshore"])
        ax.text(-0.5, y, f"Test {t.strftime('%m.%Y')}", ha="right", va="center", fontsize=6.5)
    y = 0
    ax.barh(y, len(monate) - 3, left=0, height=0.6, color="#d9d8d3")
    ax.barh(y, 3, left=len(monate) - 3, height=0.6, color="white", edgecolor=TEXT, hatch="////",
            linewidth=0.8)
    ax.text(-0.5, y, "Abschluss", ha="right", va="center", fontsize=6.5)
    ax.set_xticks(range(0, len(monate), 6), [monate[i].strftime("%m.%y")
                                             for i in range(0, len(monate), 6)], fontsize=6.5)
    ax.set_yticks([])
    ax.grid(axis="y", visible=False)
    ax.set_xlim(-0.2, len(monate) + 0.2)
    ax.set_title("Validierung nur zeitlich: grau Training, blau Testmonat, schraffiert "
                 "unberührter Abschlusstest (jede 3. Runde gezeigt)")
    speichern(fig, "validierung")


# 9 Quantile und Pinball-Verlust ----------------------------------------------
def pinball():
    fig, axs = plt.subplots(1, 2, figsize=(7.4, 2.5))
    e = np.linspace(-1, 1, 201)
    for tau, farbe in ((0.1, QUELLE["wind_onshore"]), (0.5, TEXT2), (0.9, QUELLE["solar"])):
        axs[0].plot(e, np.maximum(tau * e, (tau - 1) * e), color=farbe, label=f"τ = {tau}")
    axs[0].set_xlabel("Fehler y minus Vorhersage")
    axs[0].set_ylabel("Verlust")
    axs[0].legend(fontsize=6.5)
    axs[0].set_title("Pinball-Verlust je Quantil")
    h = np.arange(0, 24, 0.25)
    p50 = np.clip(np.sin((h - 6) / 14 * np.pi), 0, None) * 45
    breite = 0.22 * p50 + 1.5 * (p50 > 0)
    axs[1].fill_between(h, np.clip(p50 - breite, 0, None), p50 + breite * 1.1,
                        color="#f9d2be", linewidth=0, label="p10 bis p90")
    axs[1].plot(h, p50, color=QUELLE["solar"], label="p50")
    axs[1].set_xlabel("Stunde")
    axs[1].set_ylabel("GW")
    axs[1].legend(fontsize=6.5, loc="upper left")
    axs[1].set_title("Ausgabe eines Tages (Schema, keine echten Werte)")
    fig.tight_layout()
    speichern(fig, "pinball")


# Diagramme aus Kaesten -------------------------------------------------------
def kasten(ax, x, y, w, h, text, farbe="#ffffff", rand="#c9c8c2", fs=7, fett=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.01,rounding_size=0.12",
                                facecolor=farbe, edgecolor=rand, linewidth=0.9))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs,
            fontweight="bold" if fett else "normal", color=TEXT, linespacing=1.35)


def pfeil(ax, a, b, text=None, rad=0.0, fs=6.2):
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle="->", mutation_scale=9, color=TEXT2,
                                 linewidth=0.9, connectionstyle=f"arc3,rad={rad}"))
    if text:
        ax.text((a[0] + b[0]) / 2, (a[1] + b[1]) / 2 + 0.12, text, ha="center", fontsize=fs,
                color=TEXT2)


def leer(figsize, xlim, ylim):
    fig, ax = plt.subplots(figsize=figsize)
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.axis("off")
    return fig, ax


def architektur():
    fig, ax = leer((7.4, 5.3), (0, 14), (-0.4, 10))
    for x, y, w, h, t in [(0.2, 7.0, 13.6, 2.8, "Externe Quellen"),
                          (0.2, 3.4, 6.6, 3.2, "Große Maschine (Training)"),
                          (7.2, 3.4, 6.6, 3.2, "Web-Maschine (Betrieb)"),
                          (0.2, -0.3, 13.6, 3.0, "GitHub und npm")]:
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.2",
                                    facecolor=FLAECHE, edgecolor="none"))
        if t.startswith("Große"):
            ax.text(x + w - 0.2, y + 0.12, t, fontsize=7, color=TEXT2, ha="right")
        else:
            ax.text(x + 0.2, y + 0.12, t, fontsize=7, color=TEXT2)
    kasten(ax, 0.6, 7.7, 4.0, 1.6, "Open-Meteo\nPrevious Runs API\nForecast API, meta.json")
    kasten(ax, 5.0, 7.7, 4.0, 1.6, "SMARD (Bundesnetzagentur)\nErzeugung, Prognose,\nLeistung")
    kasten(ax, 9.4, 7.7, 4.0, 1.6, "Energy-Charts\ninstallierte Leistung\nmonatlich")
    kasten(ax, 0.6, 3.8, 2.9, 2.4, "scripts/\ndownload.py\nsmard_laden.py\nkapazitaet.py\n"
                                   "Training (Phase 2)", fs=6.6)
    kasten(ax, 3.8, 3.8, 2.7, 2.4, "data/\nwetter/*.parquet\nsmard/*.parquet\nlogs/\n"
                                   "(nicht im Git)", fs=6.6)
    kasten(ax, 7.6, 3.8, 2.9, 2.4, "Archiv-Timer\nstündlich :35\n/var/lib/\nsmard-forecast",
           fs=6.6)
    kasten(ax, 10.8, 3.8, 2.7, 2.4, "smard-mcp\nTool forecast_\nrenewables\n(ab Phase 4)",
           fs=6.6)
    kasten(ax, 0.6, 0.3, 4.0, 1.9, "akquisio-dev/\nsmard-forecast\nPlan, Code, Modelle,\n"
                                   "monatlicher Workflow", fs=6.6)
    kasten(ax, 5.0, 0.3, 4.0, 1.9, "akquisio-dev/smard-mcp\nmodels/*.json\nTS-Auswertung", fs=6.6)
    kasten(ax, 9.4, 0.3, 4.0, 1.9, "npm-Paket smard-mcp\nund energie.akquisio.eu/mcp\n"
                                   "für KI-Clients", fs=6.6)
    pfeil(ax, (2.0, 7.7), (2.0, 6.2))
    pfeil(ax, (6.0, 7.7), (3.0, 6.2))
    pfeil(ax, (10.4, 7.7), (3.3, 6.2))
    pfeil(ax, (4.2, 7.7), (8.6, 6.2))
    pfeil(ax, (12.2, 7.7), (12.2, 6.2))
    ax.text(12.3, 6.85, "live im Betrieb", fontsize=6.2, color=TEXT2)
    pfeil(ax, (3.5, 5.0), (3.8, 5.0))
    pfeil(ax, (2.0, 3.8), (2.6, 2.2))
    ax.text(2.45, 3.0, "Modelle als PR", fontsize=6.2, color=TEXT2)
    pfeil(ax, (4.6, 1.25), (5.0, 1.25))
    pfeil(ax, (9.0, 1.25), (9.4, 1.25))
    pfeil(ax, (12.1, 2.2), (12.1, 3.8))
    ax.text(12.2, 3.0, "ausrollen", fontsize=6.2, color=TEXT2)
    speichern(fig, "architektur")


def pipeline():
    fig, ax = leer((7.4, 1.9), (0, 15), (0, 3))
    schritte = ["Rohdaten\nParquet", "Merkmale\nje Stunde", "Zielgröße\nAuslastung",
                "LightGBM\n3 Quantile", "Bewertung\nMesslatten", "Export\nJSON", "smard-mcp\nTool"]
    w = 1.75
    for i, s in enumerate(schritte):
        x = 0.15 + i * 2.12
        kasten(ax, x, 0.8, w, 1.4, s, farbe="#ffffff" if i < 6 else FLAECHE)
        if i:
            pfeil(ax, (x - 0.37, 1.5), (x, 1.5))
    ax.text(0.15, 2.55, "Datenfluss von den Rohdaten bis zum Tool", fontsize=8.5)
    speichern(fig, "pipeline")


def phasen():
    fig, ax = leer((7.4, 2.3), (0, 14), (0, 3.4))
    ph = [("0", "Datenprüfung", "fertig"), ("1", "Download\nArchiv", "läuft"),
          ("2", "Solar-\nModell", "geplant"), ("3", "Wind-\nModelle", "geplant"),
          ("4", "Tool im\nBranch", "geplant"), ("5", "Monitoring\nWorkflow", "geplant"),
          ("6", "Ausrollen\nRelease", "geplant")]
    farbe = {"fertig": QUELLE["wind_onshore"], "läuft": "#d5e4f6", "geplant": "#ffffff"}
    for i, (n, t, st) in enumerate(ph):
        x = 0.1 + i * 1.98
        kasten(ax, x, 1.0, 1.75, 1.5, f"Phase {n}\n{t}", farbe=farbe[st],
               rand=QUELLE["wind_onshore"] if st != "geplant" else "#c9c8c2")
        if st == "fertig":
            ax.texts[-1].set_color("white")
        ax.text(x + 0.87, 0.7, st, ha="center", fontsize=6.5, color=TEXT2)
    for i, name in ((2, "Prüfpunkt A"), (3, "Prüfpunkt B"), (6, "Prüfpunkt C")):
        x = 0.1 + i * 1.98 + 1.75 if i < 6 else 0.1 + 6 * 1.98 + 0.87
        ax.text(x, 2.85, f"◆ {name}", ha="center", fontsize=6.5, color=TEXT)
    ax.text(0.1, 0.15, "Stand 02.11.2026. Erst wenn Prüfpunkt A (Solar schlägt die Messlatten) "
                       "bestanden ist, wird Code in smard-mcp eingebaut.", fontsize=6.5,
            color=TEXT2)
    speichern(fig, "phasen")


def tagesablauf():
    fig, ax = plt.subplots(figsize=(7.4, 2.4))
    reihen = [("ICON-D2 Lauf", range(0, 24, 3)), ("ICON-EU Lauf", range(0, 24, 3)),
              ("ICON global Lauf", range(0, 24, 6)), ("Archiv prüft (:35)", range(0, 24, 1)),
              ("Dienste-Sicherung", [4]), ("Monitoring (geplant)", [6])]
    for i, (n, hs) in enumerate(reihen):
        y = len(reihen) - i
        ax.scatter([h + (0.58 if "Archiv" in n else 0) for h in hs], [y] * len(list(hs)),
                   s=22 if "Archiv" in n else 34,
                   color=QUELLE["wind_onshore"] if "ICON" in n else TEXT2, zorder=3)
        ax.text(-0.4, y, n, ha="right", va="center", fontsize=7)
    ax.set_yticks([])
    ax.set_xticks(range(0, 25, 3))
    ax.set_xlim(-0.2, 24.2)
    ax.set_ylim(0.4, len(reihen) + 0.6)
    ax.set_xlabel("Uhrzeit UTC (Laufstart; verfügbar ist ein Lauf jeweils 1 bis 4 h später)")
    ax.grid(axis="y", visible=False)
    ax.set_title("Ein Tag im Betrieb")
    speichern(fig, "tagesablauf")


def archiv_ablauf():
    fig, ax = leer((7.4, 2.4), (0, 16), (0, 4.2))
    kasten(ax, 0.1, 1.6, 2.2, 1.2, "Timer\nstündlich :35", fs=6.5)
    kasten(ax, 2.8, 1.6, 3.0, 1.2, "meta.json lesen\nD2, EU, global, RUC", fs=6.5)
    kasten(ax, 6.3, 1.6, 3.0, 1.2, "neuer Lauf von\nD2, EU oder global?", fs=6.5)
    kasten(ax, 10.0, 2.7, 2.8, 1.2, "1 Abruf: 40 Orte,\n10 Variablen, 8 Tage", fs=6.5)
    kasten(ax, 13.2, 2.7, 2.7, 1.2, "json.gz speichern,\nStand merken", fs=6.5)
    kasten(ax, 10.0, 0.3, 2.8, 1.2, "nichts tun\n(Log: kein neuer Lauf)", fs=6.2)
    pfeil(ax, (2.3, 2.2), (2.8, 2.2))
    pfeil(ax, (5.8, 2.2), (6.3, 2.2))
    pfeil(ax, (9.3, 2.5), (10.0, 3.2))
    ax.text(9.45, 3.05, "ja", fontsize=6.2, color=TEXT2)
    pfeil(ax, (9.3, 1.9), (10.0, 1.0))
    ax.text(9.0, 1.45, "nein", fontsize=6.2, color=TEXT2)
    pfeil(ax, (12.8, 3.3), (13.2, 3.3))
    speichern(fig, "archiv_ablauf")


def workflow():
    fig, ax = leer((7.4, 2.4), (0, 15), (0, 4))
    s = [("1. des Monats,\nGitHub Actions", "#ffffff"), ("letzten Monat\nnachladen", "#ffffff"),
         ("neu\ntrainieren", "#ffffff"), ("Vergleich mit\nMesslatten und\naltem Modell",
                                          "#ffffff"),
         ("Pull Request:\nModelle und\nBericht", "#ffffff"), ("Prüfen und\nmergen (Hand)", FLAECHE),
         ("Übernahme\nin smard-mcp", FLAECHE)]
    for i, (t, f) in enumerate(s):
        x = 0.1 + i * 2.13
        kasten(ax, x, 1.3, 1.85, 1.5, t, farbe=f, fs=6.2)
        if i:
            pfeil(ax, (x - 0.28, 2.05), (x, 2.05))
    ax.text(0.1, 3.3, "Monatliches Neu-Training (geplant ab Phase 5): automatisch bis zum PR, "
                      "gemergt wird nur von Hand", fontsize=8)
    speichern(fig, "workflow")


if __name__ == "__main__":
    for f in (karte, kapazitaet, auslastung_nenner, verfuegbarkeit, vorlauf_schema, woche,
              klimatologie, validierung, pinball, architektur, pipeline, phasen, tagesablauf,
              archiv_ablauf, workflow):
        f()
