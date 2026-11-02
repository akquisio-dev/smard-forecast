"""Lehrgrafiken und Kennzahlen fuer den Bericht, aus echten Daten.

Liest data/phase0/roh (Wetter, Tag 1 bis 6, alle 40 Orte), data/smard und data/kapazitaet.parquet.
Schreibt PNGs nach docs/bericht/abb/ und alle im Text genannten Zahlen nach
docs/bericht/abb/zahlen.json, damit kein Wert im Bericht von Hand eingetragen ist.

Grafiken mit "Schema" im Titel sind Veranschaulichungen; alle anderen zeigen echte Werte.
Die Lernbeispiele mit LightGBM sind bewusst vereinfacht und NICHT das Projektmodell.
"""

import glob
import json
import math
import re
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
HIER = Path(__file__).resolve().parent
sys.path.insert(0, str(HIER))
sys.path.insert(0, str(HIER.parents[1]))

import abbildungen as A  # noqa: E402  (Stil, Farben, speichern)
from abbildungen import (FLAECHE, GRID, MUTED, NAME, NEUTRAL, QUELLE, TEXT, TEXT2,  # noqa: E402
                         kasten, leer, pfeil, plt, speichern)
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from sf.orte import lade_orte  # noqa: E402

ROOT = HIER.parents[1]
DATA = ROOT / "data"
CACHE = DATA / "lehr"
CACHE.mkdir(exist_ok=True)
Z = {}  # Zahlen fuer den Text
BLAU, ORANGE, GRUEN = QUELLE["wind_onshore"], QUELLE["solar"], QUELLE["wind_offshore"]
SEQ = LinearSegmentedColormap.from_list("seq", ["#f4f8fd", "#a9c8ef", "#2a78d6", "#123f78"])


def zahl(k, v, nach=3):
    Z[k] = round(float(v), nach) if isinstance(v, (float, np.floating)) else v
    return v


# Daten -----------------------------------------------------------------------
def wetter(var, typ):
    """Mittel ueber alle Orte eines Typs, je Vorlauftag 1..6 (UTC, Zeitstempel wie Open-Meteo)."""
    datei = CACHE / f"{var}_{typ}.parquet"
    if datei.exists():
        return pd.read_parquet(datei)
    spalten = {}
    for o in lade_orte():
        if typ not in o.typ:
            continue
        for f in sorted(glob.glob(str(DATA / "phase0" / "roh" / f"{o.name}_*.json"))):
            h = json.load(open(f))
            t = pd.to_datetime(h["time"], utc=True)
            for n in range(1, 7):
                k = f"{var}_previous_day{n}"
                if k in h:
                    spalten.setdefault((o.name, n), []).append(pd.Series(h[k], index=t))
    df = {}
    for n in range(1, 7):
        orte = [pd.concat(v).sort_index() for (o, m), v in spalten.items() if m == n]
        df[n] = pd.concat(orte, axis=1).mean(axis=1)
    out = pd.DataFrame(df)
    out.columns = [f"tag{n}" for n in out.columns]
    out.to_parquet(datei)
    return out


def auslastung(q):
    k = pd.read_parquet(DATA / "kapazitaet.parquet").set_index("monat")[q]
    g = pd.read_parquet(DATA / "smard" / f"generation_{q}.parquet").dropna().set_index("zeit")
    monat = g.index.tz_convert("Europe/Berlin").strftime("%Y-%m")
    return (g.mwh / monat.map(k).values).rename("a")


def sonnenhoehe(zeit_utc: pd.DatetimeIndex, lat=51.0, lon=10.0):
    """Sonnenhoehe in Grad (Naeherung nach Spencer/Cooper, genau auf etwa 0,5 Grad)."""
    doy = zeit_utc.dayofyear.values
    stunde = zeit_utc.hour.values + zeit_utc.minute.values / 60
    g = 2 * np.pi / 365 * (doy - 1 + (stunde - 12) / 24)
    dekl = (0.006918 - 0.399912 * np.cos(g) + 0.070257 * np.sin(g) - 0.006758 * np.cos(2 * g)
            + 0.000907 * np.sin(2 * g) - 0.002697 * np.cos(3 * g) + 0.00148 * np.sin(3 * g))
    zgl = 229.18 * (0.000075 + 0.001868 * np.cos(g) - 0.032077 * np.sin(g)
                    - 0.014615 * np.cos(2 * g) - 0.040849 * np.sin(2 * g))  # Minuten
    sonnenzeit = stunde * 60 + zgl + 4 * lon
    w = np.radians(sonnenzeit / 4 - 180)
    phi = np.radians(lat)
    sin_h = np.sin(phi) * np.sin(dekl) + np.cos(phi) * np.cos(dekl) * np.cos(w)
    return np.degrees(np.arcsin(np.clip(sin_h, -1, 1)))


def solar_tabelle():
    """Strahlung (auf SMARD-Stunde ausgerichtet) und Auslastung, Tag 1 bis 6."""
    w = wetter("shortwave_radiation", "solar").shift(-1)  # Wert bei T+1 = Mittel T..T+1
    a = auslastung("solar")
    d = w.join(a, how="inner").dropna()
    d["sonne"] = sonnenhoehe(d.index + pd.Timedelta(minutes=30))
    return d


def wind_tabelle(typ, q):
    w = wetter("wind_speed_100m", typ) / 3.6  # km/h -> m/s
    d = w.join(auslastung(q), how="inner").dropna()
    return d


# Kapitel Strom -----------------------------------------------------------------
def leistung_energie():
    g = pd.read_parquet(DATA / "smard" / "generation_solar.parquet").dropna().set_index("zeit")
    g.index = g.index.tz_convert("Europe/Berlin")
    tag = g.loc["2026-06-20"].mwh / 1000
    fig, ax = plt.subplots(figsize=(7.4, 2.6))
    x = np.arange(len(tag))
    ax.bar(x + 0.5, tag.values, width=0.94, color="#f9d2be", edgecolor="white", linewidth=0.6)
    ax.plot(x + 0.5, tag.values, color=ORANGE, marker="o", markersize=3)
    i = int(np.argmax(tag.values))
    ax.annotate(f"Höchstwert {tag.values[i]:.1f} GW\n(Leistung in der Stunde {i}:00 bis {i+1}:00)",
                (i + 0.5, tag.values[i]), xytext=(i + 3.5, tag.values[i] - 4), fontsize=7,
                arrowprops=dict(arrowstyle="->", color=TEXT2, linewidth=0.8))
    energie = tag.sum()
    ax.text(0.5, tag.max() * 0.85, f"Fläche = Energie des Tages\n= Summe der Stundenwerte × 1 h\n"
            f"= {energie:.0f} GWh", fontsize=7.5, color=TEXT)
    ax.set_xlim(0, 24)
    ax.set_xticks(range(0, 25, 3))
    ax.set_xlabel("Stunde (Ortszeit)")
    ax.set_ylabel("GW")
    ax.set_title("Solar am 20.06.2026: Leistung (Linie) und Energie (Fläche)")
    speichern(fig, "l_leistung_energie")
    zahl("tag_energie_gwh", energie, 1)
    zahl("tag_spitze_gw", tag.values[i], 1)
    zahl("tag_spitze_stunde", i)


def sommerzeit():
    std = []
    for d in ["2026-03-28", "2026-03-29", "2026-03-30", "2026-10-24", "2026-10-25", "2026-10-26"]:
        a = pd.Timestamp(d, tz="Europe/Berlin")
        b = a + pd.DateOffset(days=1)
        std.append([d, int((b - a).total_seconds() // 3600)])
    Z["sommerzeit"] = std


# Kapitel Solar -----------------------------------------------------------------
def sonnenbahn():
    fig, ax = plt.subplots(figsize=(7.4, 2.7))
    for datum, farbe, name in (("2026-06-21", ORANGE, "21. Juni"), ("2026-03-20", TEXT2,
                                                                     "20. März"),
                               ("2026-12-21", BLAU, "21. Dezember")):
        lokal = pd.date_range(f"{datum} 00:00", periods=24 * 12 + 1, freq="5min",
                              tz="Europe/Berlin")
        h = sonnenhoehe(lokal.tz_convert("UTC"), 48.14, 11.58)
        x = np.arange(len(lokal)) * 5 / 60
        ax.plot(x, h, color=farbe, label=name)
        zahl(f"sonne_max_{datum}", h.max(), 1)
    ax.axhline(0, color=TEXT, linewidth=0.8)
    ax.set_xlim(0, 24)
    ax.set_xticks(range(0, 25, 3))
    ax.set_ylim(-70, 70)
    ax.set_xlabel("Uhrzeit (Ortszeit; im Juni Sommerzeit)")
    ax.set_ylabel("Sonnenhöhe in Grad")
    ax.legend(fontsize=7, loc="upper left")
    ax.set_title("Sonnenhöhe über München, berechnet mit den Formeln aus Abschnitt „Sonnenstand“")
    speichern(fig, "l_sonnenbahn")


def solar_streu():
    d = solar_tabelle()
    tag = d[d.sonne > 0]
    fig, axs = plt.subplots(1, 2, figsize=(7.4, 3.0))
    ax = axs[0]
    hb = ax.hexbin(tag.tag1, tag.a, gridsize=45, cmap=SEQ, mincnt=1, bins="log", linewidths=0)
    bins = np.arange(0, tag.tag1.max() + 50, 50)
    gr = tag.groupby(pd.cut(tag.tag1, bins)).a.median()
    mitten = [b.mid for b in gr.index]
    ax.plot(mitten, gr.values, color=ORANGE, linewidth=1.8, label="Median je 50 W/m²")
    ax.set_xlabel("mittlere Globalstrahlung, 21 Orte, Tag 1 (W/m²)")
    ax.set_ylabel("Auslastung Solar")
    ax.set_title("Strahlung gegen Erzeugung")
    ax.legend(fontsize=6.5, loc="upper left")
    r = np.corrcoef(tag.tag1, tag.a)[0, 1]
    zahl("solar_r_tag1", r)
    zahl("solar_r2_tag1", r * r)
    zahl("solar_n_stunden", len(tag))
    # Steigung: Auslastung je 100 W/m^2
    k = np.polyfit(tag.tag1, tag.a, 1)
    zahl("solar_steigung_100", k[0] * 100, 4)
    ax = axs[1]
    m = tag[(tag.tag1 > 150)]
    v = (m.a / m.tag1 * 1000).groupby(m.index.tz_convert("Europe/Berlin").month).median()
    ax.bar(v.index, v.values, color=ORANGE, width=0.7)
    ax.set_xticks(range(1, 13), ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"])
    ax.set_title("Auslastung je 1.000 W/m², nach Monat")
    ax.set_ylabel("Auslastung pro kW/m²")
    ax.grid(axis="x", visible=False)
    zahl("solar_eff_jun", v.loc[6])
    zahl("solar_eff_dez", v.loc[12])
    zahl("solar_eff_apr", v.loc[4])
    fig.tight_layout()
    speichern(fig, "l_solar_streu")


def zeitversatz():
    d = wetter("shortwave_radiation", "solar").tag1
    g = auslastung("solar")
    werte = {}
    for s in (-2, -1, 0, 1):
        x = pd.concat([d.shift(s), g], axis=1).dropna()
        werte[s] = np.corrcoef(x.iloc[:, 0], x.iloc[:, 1])[0, 1]
    Z["versatz"] = {str(k): round(v, 4) for k, v in werte.items()}
    fig, ax = plt.subplots(figsize=(7.4, 2.3))
    ks = list(werte)
    ax.bar([str(k) for k in ks], [werte[k] for k in ks],
           color=[ORANGE if k == -1 else NEUTRAL for k in ks], width=0.55)
    for i, k in enumerate(ks):
        ax.text(i, werte[k] + 0.005, f"{werte[k]:.3f}", ha="center", fontsize=7)
    ax.set_ylim(0.75, 1.0)
    ax.set_xlabel("Verschiebung der Strahlung in Stunden (−1: Wert von 12:00 gehört zur "
                  "SMARD-Stunde 11:00)")
    ax.set_ylabel("Korrelation r")
    ax.set_title("Welche Stunde gehört zusammen? Korrelation Strahlung zu Solarerzeugung")
    ax.grid(axis="x", visible=False)
    speichern(fig, "l_zeitversatz")


# Kapitel Wind ------------------------------------------------------------------
def wind_theorie():
    v = np.linspace(0, 30, 301)
    rho, r = 1.225, 60
    a = np.pi * r * r
    p_wind = 0.5 * rho * a * v ** 3 / 1e6
    p_betz = p_wind * 16 / 27
    nenn = 4.2
    p_anl = np.where(v < 3, 0, np.where(v < 12, nenn * ((v ** 3 - 27) / (12 ** 3 - 27)),
                                        np.where(v < 25, nenn, 0)))
    fig, axs = plt.subplots(1, 2, figsize=(7.4, 2.7))
    ax = axs[0]
    ax.plot(v, p_wind, color=NEUTRAL, label="Leistung im Wind ½ρAv³")
    ax.plot(v, p_betz, color=TEXT2, linestyle=(0, (3, 2)), label="Betz-Grenze (16/27)")
    ax.plot(v, p_anl, color=BLAU, label="Anlage (4,2 MW)")
    ax.set_ylim(0, 12)
    ax.set_xlim(0, 30)
    ax.set_xlabel("Windgeschwindigkeit (m/s)")
    ax.set_ylabel("MW")
    ax.legend(fontsize=6.3, loc="upper right")
    ax.set_title("Leistungskurve (Schema, Rotor 120 m)")
    for x, t in ((3, "Anlauf"), (12, "Nennleistung"), (25, "Abschaltung")):
        ax.axvline(x, color=GRID, linewidth=1)
        ax.text(x + 0.3, 5.0, t, fontsize=6, color=TEXT2, rotation=90, va="bottom")
    ax = axs[1]
    h = np.linspace(2, 200, 200)
    for alpha, farbe, n in ((0.10, GRUEN, "See, α = 0,10"), (0.14, BLAU, "flaches Land, α = 0,14"),
                            (0.25, ORANGE, "Wald, Stadt, α = 0,25")):
        ax.plot(6 * (h / 10) ** alpha, h, color=farbe, label=n)
    ax.axhline(100, color=GRID)
    ax.set_xlabel("Windgeschwindigkeit (m/s), 6 m/s in 10 m Höhe")
    ax.set_ylabel("Höhe (m)")
    ax.legend(fontsize=6.3, loc="upper left")
    ax.set_title("Höhenprofil (Schema, Potenzgesetz)")
    fig.tight_layout()
    speichern(fig, "l_wind_theorie")
    zahl("wind_p_10ms_mw", 0.5 * rho * a * 10 ** 3 / 1e6, 2)
    zahl("wind_p_5ms_mw", 0.5 * rho * a * 5 ** 3 / 1e6, 2)


def wind_streu():
    fig, axs = plt.subplots(1, 2, figsize=(7.4, 3.0), sharey=True)
    for ax, (typ, q) in zip(axs, (("wind", "wind_onshore"), ("offshore", "wind_offshore"))):
        d = wind_tabelle(typ, q)
        ax.hexbin(d.tag1, d.a, gridsize=45, cmap=SEQ, mincnt=1, bins="log", linewidths=0)
        bins = np.arange(0, d.tag1.max() + 0.5, 0.5)
        gr = d.groupby(pd.cut(d.tag1, bins)).a
        mitte = [b.mid for b in gr.median().index]
        ax.plot(mitte, gr.median().values, color=QUELLE[q], linewidth=1.8, label="Median")
        ax.plot(mitte, gr.quantile(0.1).values, color=QUELLE[q], linewidth=0.9,
                linestyle=(0, (3, 2)), label="10 % und 90 %")
        ax.plot(mitte, gr.quantile(0.9).values, color=QUELLE[q], linewidth=0.9,
                linestyle=(0, (3, 2)))
        ax.set_xlabel(f"mittlerer Wind 100 m, {len(d.columns) - 7 + 1 if False else ''}"
                      f"Tag 1 (m/s)")
        ax.set_title(NAME[q])
        ax.set_xlim(0, 18 if q == "wind_onshore" else 22)
        ax.legend(fontsize=6.3, loc="upper left")
        r = d[["tag1", "a"]].corr(method="spearman").iloc[0, 1]
        zahl(f"{q}_spearman_tag1", r)
    axs[0].set_ylabel("Auslastung")
    fig.tight_layout()
    speichern(fig, "l_wind_streu")


# Kapitel Wettervorhersage ------------------------------------------------------
def lorenz():
    def bahn(x0, n=4000, dt=0.01, s=10, r=28, b=8 / 3):
        x = np.array(x0, float)
        out = np.empty((n, 3))
        for i in range(n):
            dx = np.array([s * (x[1] - x[0]), x[0] * (r - x[2]) - x[1], x[0] * x[1] - b * x[2]])
            x = x + dt * dx
            out[i] = x
        return out
    a = bahn([1, 1, 1])
    b = bahn([1.0001, 1, 1])
    t = np.arange(len(a)) * 0.01
    fig, axs = plt.subplots(1, 2, figsize=(7.4, 2.6))
    axs[0].plot(t, a[:, 0], color=BLAU, linewidth=1, label="Start x = 1,0000")
    axs[0].plot(t, b[:, 0], color=ORANGE, linewidth=1, label="Start x = 1,0001")
    axs[0].set_xlabel("Zeit (Modelleinheiten)")
    axs[0].set_ylabel("x")
    axs[0].legend(fontsize=6.3, loc="lower left")
    axs[0].set_title("Lorenz-System: winziger Startunterschied")
    abst = np.linalg.norm(a - b, axis=1)
    axs[1].semilogy(t, abst, color=TEXT2)
    axs[1].set_xlabel("Zeit (Modelleinheiten)")
    axs[1].set_ylabel("Abstand (log)")
    axs[1].set_title("Abstand wächst exponentiell, dann gesättigt")
    fig.tight_layout()
    speichern(fig, "l_lorenz")
    idx = int(np.argmax(abst > 1))
    zahl("lorenz_t_abstand_1", t[idx], 1)


def guete_nach_vorlauf():
    """Einfaches Lernbeispiel: Median je Klasse aus 2024/25, getestet 2026, je Vorlauftag."""
    erg = {}
    fig, ax = plt.subplots(figsize=(7.4, 2.8))
    for q, (tab, schritt) in {"solar": (solar_tabelle(), 25),
                              "wind_onshore": (wind_tabelle("wind", "wind_onshore"), 0.5),
                              "wind_offshore": (wind_tabelle("offshore", "wind_offshore"),
                                                0.5)}.items():
        if q == "solar":
            tab = tab[tab.sonne > 0]
        train = tab[tab.index < "2026-01-01"]
        test = tab[tab.index >= "2026-01-01"]
        maes = []
        for n in range(1, 7):
            c = f"tag{n}"
            k_tr = (train[c] / schritt).round()
            tabelle = train.groupby(k_tr).a.median()
            k_te = (test[c] / schritt).round()
            vorh = k_te.map(tabelle).fillna(train.a.median())
            maes.append(float((vorh - test.a).abs().mean() * 100))
        erg[q] = maes
        ax.plot(range(1, 7), maes, color=QUELLE[q], marker="o", label=NAME[q])
        ax.annotate(f"{maes[0]:.1f}", (1, maes[0]), xytext=(-18, 0), textcoords="offset points",
                    fontsize=6.5)
        ax.annotate(f"{maes[-1]:.1f}", (6, maes[-1]), xytext=(5, 0), textcoords="offset points",
                    fontsize=6.5)
    ax.set_xticks(range(1, 7), [f"Tag {n}" for n in range(1, 7)])
    ax.set_ylabel("MAE in % der Leistung")
    ax.set_ylim(0, None)
    ax.legend(fontsize=6.8)
    ax.set_title("Lernbeispiel: einfachstes Modell (Median je Wetterklasse), Test 2026, "
                 "Fehler nach Vorlauftag")
    speichern(fig, "l_guete_vorlauf")
    Z["guete_vorlauf"] = {k: [round(x, 2) for x in v] for k, v in erg.items()}


# Kapitel Statistik ---------------------------------------------------------------
def netzbetreiber_fehler(q):
    g = pd.read_parquet(DATA / "smard" / f"generation_{q}.parquet").dropna().set_index("zeit")
    f = pd.read_parquet(DATA / "smard" / f"forecast_generation_{q}.parquet").dropna() \
        .set_index("zeit")
    d = pd.concat([g.mwh.rename("ist"), f.mwh.rename("prog")], axis=1).dropna() / 1000
    d["fehler"] = d.ist - d.prog
    if q == "solar":
        d = d[sonnenhoehe(d.index + pd.Timedelta(minutes=30)) > 0]
    return d


def fehler_histogramm():
    fig, axs = plt.subplots(1, 2, figsize=(7.4, 2.8))
    for ax, q in zip(axs, ("solar", "wind_onshore")):
        d = netzbetreiber_fehler(q)
        e = d.fehler
        ax.hist(e, bins=np.arange(-12, 12.25, 0.5), color=QUELLE[q], edgecolor="white",
                linewidth=0.4)
        qs = e.quantile([0.1, 0.5, 0.9])
        for (p, v), lab in zip(qs.items(), ("p10", "p50", "p90")):
            ax.axvline(v, color=TEXT, linewidth=0.9, linestyle=(0, (3, 2)))
            ax.text(v, ax.get_ylim()[1] * 0.92, f" {lab}\n {v:.2f}", fontsize=6.3)
        ax.set_xlim(-10, 10)
        ax.set_xlabel("Fehler: Ist minus Prognose (GW)")
        ax.set_title(f"{NAME[q]}, Prognose der Netzbetreiber")
        mae = e.abs().mean()
        rmse = math.sqrt((e ** 2).mean())
        zahl(f"nb_{q}_mae", mae, 3)
        zahl(f"nb_{q}_rmse", rmse, 3)
        zahl(f"nb_{q}_mittel", e.mean(), 3)
        zahl(f"nb_{q}_median", e.median(), 3)
        zahl(f"nb_{q}_p10", qs.loc[0.1], 3)
        zahl(f"nb_{q}_p90", qs.loc[0.9], 3)
        zahl(f"nb_{q}_n", len(e))
    axs[0].set_ylabel("Anzahl Stunden")
    fig.tight_layout()
    speichern(fig, "l_fehler_histogramm")


def pinball_minimum():
    e = netzbetreiber_fehler("wind_onshore").fehler.values
    qs = np.linspace(-6, 6, 241)
    fig, ax = plt.subplots(figsize=(7.4, 2.7))
    for tau, farbe in ((0.1, BLAU), (0.5, TEXT2), (0.9, ORANGE)):
        verl = [np.mean(np.maximum(tau * (e - q), (tau - 1) * (e - q))) for q in qs]
        i = int(np.argmin(verl))
        ax.plot(qs, verl, color=farbe, label=f"τ = {tau}")
        ax.plot(qs[i], verl[i], marker="o", color=farbe)
        ax.axvline(np.quantile(e, tau), color=farbe, linewidth=0.7, linestyle=(0, (1, 2)))
        zahl(f"pin_min_{tau}", qs[i], 2)
        zahl(f"pin_q_{tau}", np.quantile(e, tau), 2)
    ax.set_xlabel("konstante Vorhersage q für den Fehler (GW)")
    ax.set_ylabel("mittlerer Pinball-Verlust")
    ax.set_ylim(0, 3.2)
    ax.legend(fontsize=6.8, loc="upper right")
    ax.set_title("Echte Fehler (Wind an Land): wo der mittlere Pinball-Verlust am kleinsten ist")
    speichern(fig, "l_pinball_minimum")


def kalibrierung():
    d = netzbetreiber_fehler("wind_onshore")
    tr = d[d.index < "2026-01-01"]
    te = d[d.index >= "2026-01-01"].copy()
    # Bandbreite relativ zur Prognose: Fehlerquantile je Prognoseklasse (2 GW breit)
    kl_tr = (tr.prog / 2).round()
    lo = tr.groupby(kl_tr).fehler.quantile(0.1)
    hi = tr.groupby(kl_tr).fehler.quantile(0.9)
    kl = (te.prog / 2).round()
    te["p10"] = te.prog + kl.map(lo).fillna(tr.fehler.quantile(0.1))
    te["p90"] = te.prog + kl.map(hi).fillna(tr.fehler.quantile(0.9))
    te["drin"] = (te.ist >= te.p10) & (te.ist <= te.p90)
    mon = te.index.tz_convert("Europe/Berlin").strftime("%m.%y")
    voll = te.groupby(mon).size()
    m = te.groupby(mon).drin.mean() * 100
    m = m[voll[m.index] >= 24 * 20]
    m = m.reindex(sorted(m.index, key=lambda s: (s[3:], s[:2])))
    fig, axs = plt.subplots(1, 2, figsize=(7.4, 2.8), gridspec_kw={"width_ratios": [1.3, 1]})
    ax = axs[0]
    ax.bar(range(len(m)), m.values, color=BLAU, width=0.7)
    ax.axhline(80, color=TEXT, linewidth=0.9, linestyle=(0, (3, 2)))
    ax.text(len(m) - 0.5, 81, "Ziel 80 %", fontsize=6.5, ha="right")
    ax.set_xticks(range(len(m)), m.index, fontsize=6.3, rotation=0)
    ax.set_ylim(0, 100)
    ax.set_ylabel("Treffer in %")
    ax.set_title("Trefferquote je Monat 2026")
    ax.grid(axis="x", visible=False)
    ax = axs[1]
    w = te.loc["2026-03-10":"2026-03-16"]
    lokal = w.index.tz_convert("Europe/Berlin")
    ax.fill_between(lokal, w.p10, w.p90, color="#cfe0f5", linewidth=0, label="p10 bis p90")
    ax.plot(lokal, w.ist, color=BLAU, linewidth=1.2, label="Ist")
    ax.set_title("eine Woche im März 2026")
    ax.set_ylabel("GW")
    ax.xaxis.set_major_formatter(A.matplotlib.dates.DateFormatter("%d.", tz="Europe/Berlin"))
    ax.legend(fontsize=6.3, loc="upper right")
    fig.tight_layout()
    speichern(fig, "l_kalibrierung")
    zahl("kal_gesamt", te.drin.mean() * 100, 1)
    zahl("kal_min", m.min(), 1)
    zahl("kal_max", m.max(), 1)


# Kapitel Lernen -------------------------------------------------------------------
def lern_daten():
    """Solar, Tag 1, Tagesstunden: Merkmale = Strahlung je Ort + Sonnenhoehe + Stunde."""
    datei = CACHE / "lern_solar.parquet"
    if datei.exists():
        return pd.read_parquet(datei)
    spalten = {}
    for o in lade_orte():
        if "solar" not in o.typ:
            continue
        teile = []
        for f in sorted(glob.glob(str(DATA / "phase0" / "roh" / f"{o.name}_*.json"))):
            h = json.load(open(f))
            teile.append(pd.Series(h["shortwave_radiation_previous_day1"],
                                   index=pd.to_datetime(h["time"], utc=True)))
        spalten[o.name] = pd.concat(teile).sort_index().shift(-1)
    x = pd.DataFrame(spalten)
    d = x.join(auslastung("solar"), how="inner").dropna()
    d["sonne"] = sonnenhoehe(d.index + pd.Timedelta(minutes=30))
    d = d[d.sonne > 0]
    d.to_parquet(datei)
    return d


def overfitting():
    """Wenig Daten (6 Wochen Fruehling 2025), viele grosse Baeume: Ueberanpassung."""
    import lightgbm as lgb
    d = lern_daten()
    merk = [c for c in d.columns if c != "a"]
    tr = d.loc["2025-04-01":"2025-05-15"]
    te = d.loc["2026-04-01":"2026-05-31"]
    m = lgb.LGBMRegressor(n_estimators=600, learning_rate=0.3, num_leaves=64,
                          min_child_samples=2, verbose=-1, objective="l1")
    m.fit(tr[merk], tr.a)
    stufen = list(range(1, 601, 5))
    e_tr = [float(np.mean(np.abs(m.predict(tr[merk], num_iteration=k) - tr.a)) * 100)
            for k in stufen]
    e_te = [float(np.mean(np.abs(m.predict(te[merk], num_iteration=k) - te.a)) * 100)
            for k in stufen]
    fig, ax = plt.subplots(figsize=(7.4, 2.7))
    ax.plot(stufen, e_tr, color=NEUTRAL, label=f"Trainingsdaten (6 Wochen 2025, {len(tr)} h)")
    ax.plot(stufen, e_te, color=ORANGE, label=f"neue Daten (Apr. und Mai 2026, {len(te)} h)")
    i = int(np.argmin(e_te))
    ax.annotate(f"bester Punkt: {stufen[i]} Bäume", (stufen[i], e_te[i]), xytext=(25, 25),
                textcoords="offset points", fontsize=6.5,
                arrowprops=dict(arrowstyle="->", color=TEXT2, linewidth=0.8))
    ax.set_xlabel("Zahl der Bäume")
    ax.set_ylabel("MAE in % der Leistung")
    ax.set_ylim(0, None)
    ax.legend(fontsize=6.6)
    ax.set_title("Lernbeispiel Überanpassung: Trainingsfehler fällt gegen null, Fehler auf "
                 "neuen Daten bleibt stehen")
    speichern(fig, "l_overfitting")
    Z["overfit"] = {"bester": stufen[i], "test_best": round(e_te[i], 2),
                    "test_ende": round(e_te[-1], 2), "train_ende": round(e_tr[-1], 3),
                    "train_h": len(tr), "test_h": len(te)}


def baum_klein():
    import lightgbm as lgb
    d = lern_daten()
    d = d.assign(strahlung=d[[c for c in d.columns if c not in ("a", "sonne")]].mean(axis=1))
    tr = d[d.index < "2026-01-01"]
    m = lgb.LGBMRegressor(n_estimators=1, learning_rate=1.0, num_leaves=4, max_depth=2,
                          min_child_samples=200, verbose=-1)
    m.fit(tr[["strahlung", "sonne"]], tr.a)
    dump = m.booster_.dump_model()["tree_info"][0]["tree_structure"]
    namen = ["strahlung", "sonne"]

    def text(k):
        if "leaf_value" in k:
            return {"blatt": round(k["leaf_value"], 3), "n": k.get("leaf_count")}
        return {"merkmal": namen[k["split_feature"]], "schwelle": round(k["threshold"], 1),
                "n": k.get("internal_count"), "links": text(k["left_child"]),
                "rechts": text(k["right_child"])}
    baum = text(dump)
    Z["baum"] = baum
    fig, ax = leer((7.4, 2.9), (0, 16), (0, 6))

    def knoten(k, x, y, breite):
        if "blatt" in k:
            kasten(ax, x - 1.3, y - 0.45, 2.6, 0.9, f"Vorhersage\n{k['blatt']:.3f}\n({k['n']} h)",
                   farbe=FLAECHE, fs=6.3)
            return
        kasten(ax, x - 1.6, y - 0.45, 3.2, 0.9,
               f"{'Strahlung' if k['merkmal'] == 'strahlung' else 'Sonnenhöhe'} "
               f"≤ {k['schwelle']}{' W/m²' if k['merkmal'] == 'strahlung' else '°'} ?\n"
               f"({k['n']} h)", fs=6.5)
        for kind, dx, t in ((k["links"], -breite, "ja"), (k["rechts"], breite, "nein")):
            pfeil(ax, (x, y - 0.45), (x + dx, y - 1.8 + 0.45))
            ax.text(x + dx / 2 + (-0.3 if dx < 0 else 0.1), y - 1.0, t, fontsize=6.2,
                    color=TEXT2)
            knoten(kind, x + dx, y - 1.8, breite / 2)
    knoten(baum, 8, 5.3, 4)
    speichern(fig, "l_baum_klein")


def split_beispiel():
    d = lern_daten()
    d = d.assign(strahlung=d[[c for c in d.columns if c not in ("a", "sonne")]].mean(axis=1))
    probe = d.loc["2025-05-12 05:00":"2025-05-12 18:00"]
    probe = probe.iloc[::2][["strahlung", "a"]].round({"strahlung": 0, "a": 3})
    probe = probe.sort_values("strahlung")
    werte = list(zip(probe.strahlung.tolist(), probe.a.tolist()))
    y = np.array([w[1] for w in werte])
    gesamt = float(((y - y.mean()) ** 2).sum())
    zeilen = []
    for i in range(1, len(werte)):
        l, r = y[:i], y[i:]
        sse = float(((l - l.mean()) ** 2).sum() + ((r - r.mean()) ** 2).sum())
        schwelle = (werte[i - 1][0] + werte[i][0]) / 2
        zeilen.append([round(schwelle, 1), i, len(werte) - i, round(float(l.mean()), 3),
                       round(float(r.mean()), 3), round(sse, 4), round(gesamt - sse, 4)])
    Z["split"] = {"punkte": werte, "sse_gesamt": round(gesamt, 4), "zeilen": zeilen,
                  "mittel": round(float(y.mean()), 3)}


def boosting_stufen():
    import lightgbm as lgb
    d = lern_daten()
    d = d.assign(strahlung=d[[c for c in d.columns if c not in ("a", "sonne")]].mean(axis=1))
    tr = d[d.index < "2026-01-01"]
    xs = np.linspace(0, tr.strahlung.max(), 400).reshape(-1, 1)
    fig, ax = plt.subplots(figsize=(7.4, 2.9))
    probe = tr.sample(4000, random_state=1)
    ax.scatter(probe.strahlung, probe.a, s=2, color="#d9d8d3", rasterized=True)
    m = lgb.LGBMRegressor(n_estimators=200, learning_rate=0.1, num_leaves=4, verbose=-1,
                          min_child_samples=50)
    m.fit(tr[["strahlung"]], tr.a)
    farben = {1: "#a9c8ef", 3: "#6fa3e3", 10: BLAU, 200: "#123f78"}
    for k, f in farben.items():
        ax.plot(xs[:, 0], m.predict(pd.DataFrame(xs, columns=["strahlung"]), num_iteration=k),
                color=f, linewidth=1.5, label=f"nach {k} Baum" + ("" if k == 1 else "en"))
    ax.set_xlabel("mittlere Strahlung (W/m²)")
    ax.set_ylabel("Auslastung")
    ax.legend(fontsize=6.6, loc="upper left")
    ax.set_title("Lernbeispiel Gradient Boosting: jeder Baum korrigiert ein Stück des Restfehlers "
                 "(Lernrate 0,1)")
    speichern(fig, "l_boosting")
    Z["boost_basis"] = round(float(tr.a.mean()), 4)


def quantil_boosting():
    import lightgbm as lgb
    d = wind_tabelle("wind", "wind_onshore")
    tr = d[d.index < "2026-01-01"]
    te = d[d.index >= "2026-01-01"]
    xs = pd.DataFrame({"tag1": np.linspace(0, 16, 300)})
    fig, ax = plt.subplots(figsize=(7.4, 2.9))
    probe = tr.sample(5000, random_state=2)
    ax.scatter(probe.tag1, probe.a, s=2, color="#d9d8d3", rasterized=True)
    cover = {}
    preds = {}
    for tau, stil in ((0.1, (0, (3, 2))), (0.5, "-"), (0.9, (0, (3, 2)))):
        m = lgb.LGBMRegressor(objective="quantile", alpha=tau, n_estimators=150,
                              learning_rate=0.05, num_leaves=8, verbose=-1)
        m.fit(tr[["tag1"]], tr.a)
        ax.plot(xs.tag1, m.predict(xs), color=BLAU, linestyle=stil, linewidth=1.6,
                label=f"p{int(tau * 100)}")
        preds[tau] = m.predict(te[["tag1"]])
    drin = (te.a >= preds[0.1]) & (te.a <= preds[0.9])
    zahl("qb_cover", drin.mean() * 100, 1)
    ax.set_xlabel("mittlerer Wind 100 m, Tag 1 (m/s)")
    ax.set_ylabel("Auslastung Wind an Land")
    ax.set_xlim(0, 16)
    ax.legend(fontsize=6.6, loc="upper left")
    ax.set_title("Lernbeispiel: drei Quantile mit LightGBM, nur ein Merkmal")
    speichern(fig, "l_quantil_boosting")


def leakage():
    import lightgbm as lgb
    d = lern_daten()
    merk = [c for c in d.columns if c != "a"]
    rng = np.random.default_rng(0)
    zufall = rng.random(len(d)) < 0.8
    par = dict(n_estimators=200, learning_rate=0.05, num_leaves=31, verbose=-1)
    m = lgb.LGBMRegressor(**par).fit(d[zufall][merk], d[zufall].a)
    e_zufall = float(np.mean(np.abs(m.predict(d[~zufall][merk]) - d[~zufall].a)) * 100)
    tr, te = d[d.index < "2026-01-01"], d[d.index >= "2026-01-01"]
    m = lgb.LGBMRegressor(**par).fit(tr[merk], tr.a)
    e_zeit = float(np.mean(np.abs(m.predict(te[merk]) - te.a)) * 100)
    zahl("leak_zufall", e_zufall, 2)
    zahl("leak_zeit", e_zeit, 2)


def autokorrelation():
    fig, ax = plt.subplots(figsize=(7.4, 2.6))
    for q in ("solar", "wind_onshore", "wind_offshore"):
        a = auslastung(q)
        a = a[~a.index.duplicated()].asfreq("h")
        lags = range(0, 169)
        r = [a.autocorr(l) for l in lags]
        ax.plot(lags, r, color=QUELLE[q], label=NAME[q])
        zahl(f"acf_{q}_1", r[1])
        zahl(f"acf_{q}_24", r[24])
        zahl(f"acf_{q}_72", r[72])
    ax.axhline(0, color=TEXT, linewidth=0.7)
    ax.set_xticks(range(0, 169, 24))
    ax.set_xlabel("Abstand in Stunden")
    ax.set_ylabel("Autokorrelation")
    ax.legend(fontsize=6.8)
    ax.set_title("Wie ähnlich ist eine Stunde der Stunde k Stunden später?")
    speichern(fig, "l_autokorrelation")


def sincos():
    fig, axs = plt.subplots(1, 2, figsize=(7.4, 2.8))
    h = np.arange(24)
    w = 2 * np.pi * h / 24
    ax = axs[0]
    ax.plot(h, h, color=NEUTRAL, marker="o", markersize=3)
    ax.annotate("23 und 0 liegen\nhier weit auseinander", (23, 23), xytext=(8, 18), fontsize=6.5,
                arrowprops=dict(arrowstyle="->", color=TEXT2, linewidth=0.8))
    ax.set_xlabel("Stunde")
    ax.set_ylabel("Merkmal „Stunde“")
    ax.set_title("Stunde als Zahl")
    ax = axs[1]
    ax.plot(np.cos(w), np.sin(w), color=GRID, zorder=1)
    ax.scatter(np.cos(w), np.sin(w), color=BLAU, s=16, zorder=2)
    for k in (0, 6, 12, 18, 23):
        ax.annotate(f"{k}", (np.cos(w[k]), np.sin(w[k])), xytext=(6, 2),
                    textcoords="offset points", fontsize=7)
    ax.set_aspect("equal")
    ax.set_xlabel("cos(2π·h/24)")
    ax.set_ylabel("sin(2π·h/24)")
    ax.set_title("Stunde als Punkt auf dem Kreis")
    fig.tight_layout()
    speichern(fig, "l_sincos")


def budget():
    zeilen = []
    for z in open(DATA / "logs" / "download.log"):
        m = re.match(r"(\S+ \S+)Z \[(\d+)/\d+\].*Gewicht (\d+)", z)
        if m:
            zeilen.append((pd.Timestamp(m.group(1), tz="UTC"), int(m.group(3))))
    if not zeilen:
        return
    df = pd.DataFrame(zeilen, columns=["t", "w"]).set_index("t")
    kum = df.w.cumsum()
    fig, ax = plt.subplots(figsize=(7.4, 2.6))
    ax.step(kum.index, kum.values + 4500, where="post", color=BLAU,
            label="gebucht heute (inkl. 4.500 vorab)")
    ax.axhline(9000, color=TEXT, linestyle=(0, (3, 2)), linewidth=0.9)
    ax.text(kum.index[0], 9100, "Tagesgrenze 9.000", fontsize=6.5)
    ax.set_ylabel("Einheiten (UTC-Tag)")
    ax.xaxis.set_major_formatter(A.matplotlib.dates.DateFormatter("%H:%M"))
    ax.set_title(f"Download am 02.11.: gebuchte Einheiten über die Zeit ({len(df)} Stücke bis "
                 f"{df.index[-1]:%H:%M} UTC)")
    ax.legend(fontsize=6.6, loc="lower right")
    speichern(fig, "l_budget")
    zahl("budget_stuecke", len(df))
    zahl("budget_summe", int(df.w.sum()))


def spalten_zeilen():
    fig, ax = leer((7.4, 2.5), (0, 16), (0, 5))
    ax.text(0.2, 4.6, "zeilenweise (CSV, JSON): eine Zeile nach der anderen", fontsize=7.5)
    farben = ["#d5e4f6", "#f9d2be", "#c6ecdd", "#e6e5e1"]
    for i in range(4):
        for j in range(4):
            ax.add_patch(A.Rectangle((0.3 + (i * 4 + j) * 0.45, 3.4), 0.42, 0.8,
                                     facecolor=farben[j], edgecolor="white"))
    ax.text(0.2, 2.5, "spaltenweise (Parquet): erst alle Zeiten, dann alle Werte von Spalte 2 ...",
            fontsize=7.5)
    for j in range(4):
        for i in range(4):
            ax.add_patch(A.Rectangle((0.3 + (j * 4 + i) * 0.45, 1.3), 0.42, 0.8,
                                     facecolor=farben[j], edgecolor="white"))
    ax.text(0.2, 0.5, "Farbe = Spalte (zeit, vorlauf, strahlung, wind). Spaltenweise liegen "
            "gleichartige Werte nebeneinander: sie lassen sich gut komprimieren und einzeln lesen.",
            fontsize=6.6, color=TEXT2)
    speichern(fig, "l_parquet")


def mcp_ablauf():
    fig, ax = leer((7.4, 3.4), (0, 16), (0, 8))
    spalten = [("Mensch", 1.2), ("KI-Assistent", 4.8), ("smard-mcp", 8.6), ("Open-Meteo", 12.0),
               ("SMARD", 14.8)]
    for n, x in spalten:
        kasten(ax, x - 1.1, 7.0, 2.2, 0.7, n, fs=6.8)
        ax.plot([x, x], [0.3, 7.0], color=GRID, linewidth=1)
    schritte = [(1.2, 4.8, 6.4, "„Kommt am Wochenende viel Solarstrom?“"),
                (4.8, 8.6, 5.6, "tools/call forecast_renewables {from, to}"),
                (8.6, 12.0, 4.8, "Wetter (falls neuer Lauf)"),
                (8.6, 14.8, 4.0, "Netzbetreiber-Prognose"),
                (8.6, 8.6, 3.2, "Modelle auswerten"),
                (8.6, 4.8, 2.4, "JSON: p10, p50, p90, notes"),
                (4.8, 1.2, 1.6, "Antwort in Worten, mit Quelle")]
    for a, b, y, t in schritte:
        if a == b:
            ax.text(a + 0.2, y, "⟲ " + t, fontsize=6.4, color=TEXT2, va="center")
            continue
        pfeil(ax, (a, y), (b, y))
        ax.text((a + b) / 2, y + 0.15, t, fontsize=6.2, ha="center", color=TEXT)
    speichern(fig, "l_mcp")


def kompression():
    beispiel = sorted(glob.glob("/tmp/claude-0/-root/*/scratchpad/archivtest/**/*.json.gz",
                                recursive=True))
    if beispiel:
        import gzip
        roh = len(gzip.open(beispiel[0]).read())
        zahl("gzip_roh", roh)
        zahl("gzip_gz", Path(beispiel[0]).stat().st_size)


if __name__ == "__main__":
    for f in (leistung_energie, sommerzeit, sonnenbahn, solar_streu, zeitversatz, wind_theorie,
              wind_streu, lorenz, guete_nach_vorlauf, fehler_histogramm, pinball_minimum,
              kalibrierung, overfitting, baum_klein, split_beispiel, boosting_stufen,
              quantil_boosting, leakage, autokorrelation, sincos, budget, spalten_zeilen,
              mcp_ablauf, kompression):
        f()
    (HIER / "abb" / "zahlen.json").write_text(json.dumps(Z, indent=1, ensure_ascii=False))
    print(json.dumps(Z, ensure_ascii=False)[:3000])
