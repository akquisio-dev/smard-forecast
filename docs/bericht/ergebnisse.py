"""Ergebnisgrafiken und Kennzahlen der Phasen 2 bis 4 fuer den Projektbericht.

Liest nur Dateien aus data/phase2, data/phase4 und data/modell; schreibt PNGs nach
docs/bericht/abb/ (Praefix e_) und alle im Text zitierten Werte nach
abb/zahlen_ergebnisse.json. Kein Wert im Text wird von Hand eingetragen.

Aufruf: .venv/bin/python -I docs/bericht/ergebnisse.py
"""

import json
import sys
from pathlib import Path

import lightgbm as lgb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

HIER = Path(__file__).resolve().parent
sys.path.insert(0, str(HIER))
from abbildungen import GRID, MUTED, NAME, NEUTRAL, QUELLE, TEXT2, speichern  # noqa: E402

ROOT = HIER.parents[1]
PH = ROOT / "data" / "phase2"
P4 = ROOT / "data" / "phase4"
QUELLEN = ("solar", "wind_onshore", "wind_offshore")
TAGE = range(1, 7)
Z: dict = {}


def modellordner() -> Path:
    return sorted((ROOT / "data" / "modell").iterdir())[-1]


def lade():
    """Kennzahlen je Quelle: rollierend (mit CQR), ohne CQR, Abschluss, Winter."""
    a = json.loads((PH / "solar_abstimmung.json").read_text())
    s1 = json.loads((PH / "solar_kennzahlen_lauf1_startwerte.json").read_text())
    w = json.loads((PH / "wind_kennzahlen.json").read_text())
    k = {"solar": {"roll": a["mit_cqr"], "ohne": a["ohne_cqr"], "abschluss": s1["abschluss"],
                   "winter": a["mit_cqr_winter"]}}
    for q in ("wind_onshore", "wind_offshore"):
        k[q] = {"roll": w[q]["rollierend"], "ohne": w[q]["ohne_cqr_rollierend"],
                "abschluss": w[q]["abschluss"], "winter": w[q]["rollierend_winter"]}
    return k, a, s1


def zahlen(k, a, s1):
    kurz = {"solar": "sol", "wind_onshore": "won", "wind_offshore": "wof"}
    for q in QUELLEN:
        for teil, t in (("roll", "r"), ("ohne", "o"), ("abschluss", "a"), ("winter", "w")):
            for n in TAGE:
                r = k[q][teil][str(n)]
                for feld, f in (("mae_pct", "mae"), ("mae_gw", "maegw"), ("treffer_pct", "tr"),
                                ("skill_einfach", "sk"), ("pinball", "pin"),
                                ("klima_mae_pct", "kl"), ("pers_mae_pct", "pe"),
                                ("tagesenergie_mae_gwh", "te")):
                    Z[f"{kurz[q]}_{t}_{f}_{n}"] = r[feld]
            r1 = k[q][teil]["1"]
            Z[f"{kurz[q]}_{t}_nb_1"] = r1["nb_mae_pct"]
            Z[f"{kurz[q]}_{t}_mnb_1"] = r1["modell_mae_pct_nb_stunden"]
            Z[f"{kurz[q]}_{t}_sknb_1"] = r1["skill_nb"]
            Z[f"{kurz[q]}_{t}_stunden"] = sum(k[q][teil][str(n)]["stunden"] for n in TAGE)
    for q in QUELLEN:
        r = k[q]["roll"]
        Z[f"{kurz[q]}_faktor"] = r["6"]["mae_pct"] / r["1"]["mae_pct"]
        a_ = k[q]["abschluss"]
        Z[f"{kurz[q]}_a_trmin"] = min(a_[str(n)]["treffer_pct"] for n in TAGE)
        Z[f"{kurz[q]}_a_trmax"] = max(a_[str(n)]["treffer_pct"] for n in TAGE)
        Z[f"{kurz[q]}_r_trmin"] = min(r[str(n)]["treffer_pct"] for n in TAGE)
        Z[f"{kurz[q]}_r_trmax"] = max(r[str(n)]["treffer_pct"] for n in TAGE)
        o = k[q]["ohne"]
        Z[f"{kurz[q]}_o_trmin"] = min(o[str(n)]["treffer_pct"] for n in TAGE)
        Z[f"{kurz[q]}_o_trmax"] = max(o[str(n)]["treffer_pct"] for n in TAGE)
        w = k[q]["winter"]
        Z[f"{kurz[q]}_w_trmin"] = min(w[str(n)]["treffer_pct"] for n in TAGE)
        Z[f"{kurz[q]}_w_trmax"] = max(w[str(n)]["treffer_pct"] for n in TAGE)
    Z["sol_diag_train"] = a["diagnose_training_treffer"]
    Z["sol_diag_test"] = a["diagnose_test_treffer"]
    for name, r in a["raster"].items():
        kn = name.split("_")[0]
        Z[f"raster_{kn}_mae_1"] = r["1"]["mae_pct"]
        Z[f"raster_{kn}_mae_6"] = r["6"]["mae_pct"]
        Z[f"raster_{kn}_tr_1"] = r["1"]["treffer_pct"]
        Z[f"raster_{kn}_tr_6"] = r["6"]["treffer_pct"]
        Z[f"raster_{kn}_pin_m"] = float(np.mean([r[str(n)]["pinball"] for n in TAGE]))
    Z["sol_zeilen"] = s1["zeilen"]
    Z["sol_merkmale"] = s1["merkmale"]
    Z["sol_nacht_pct"] = s1["nacht_ausgeschlossen_energie_pct"]
    meta = json.loads((modellordner() / "modell.json").read_text())
    Z["modell_version"] = meta["version"]
    for q in QUELLEN:
        Z[f"{kurz[q]}_merkmale"] = len(meta["quellen"][q]["merkmale"])
        for n in TAGE:
            Z[f"{kurz[q]}_cqr_{n}"] = meta["quellen"][q]["cqr"][str(n)] * 100
    groesse = sum(f.stat().st_size for f in modellordner().glob("*.json")) / 1e6
    Z["modell_mb"] = groesse


# Abbildungen ----------------------------------------------------------------

def skill(k):
    fig, ax = plt.subplots(figsize=(6.4, 3.1))
    for q in QUELLEN:
        ax.plot(TAGE, [k[q]["roll"][str(n)]["skill_einfach"] for n in TAGE], "-o", ms=3.5,
                color=QUELLE[q], label=f"{NAME[q]}, rollierend")
        ax.plot(TAGE, [k[q]["abschluss"][str(n)]["skill_einfach"] for n in TAGE], "--",
                color=QUELLE[q], alpha=0.75, label=f"{NAME[q]}, Abschlusstest")
    ax.axhline(0.2, color=TEXT2, lw=0.9, ls=":")
    ax.text(6.05, 0.2, "Schwelle 0,2", va="center", fontsize=7, color=TEXT2)
    ax.axhspan(-0.05, 0.2, color="#f3f3f1", zorder=0)
    ax.set_xlabel("Vorlauftag")
    ax.set_ylabel("Skill gegen die bessere\neinfache Messlatte")
    ax.set_ylim(0, 0.85)
    ax.set_title("Skill je Vorlauftag, Quelle und Prüfung")
    ax.legend(fontsize=6.6, ncol=2, loc="upper right")
    speichern(fig, "e_skill_vorlauf")


def mae(k):
    fig, axs = plt.subplots(1, 3, figsize=(7.2, 2.6), sharey=False)
    for ax, q in zip(axs, QUELLEN):
        r = k[q]["roll"]
        ax.plot(TAGE, [r[str(n)]["mae_pct"] for n in TAGE], "-o", ms=3, color=QUELLE[q],
                label="Modell (p50)")
        ax.plot(TAGE, [r[str(n)]["klima_mae_pct"] for n in TAGE], color=NEUTRAL, ls="--",
                label="Klimatologie")
        ax.plot(TAGE, [r[str(n)]["pers_mae_pct"] for n in TAGE], color=MUTED, ls=":",
                label="Persistenz")
        ax.plot([1], [r["1"]["nb_mae_pct"]], "s", color=TEXT2, ms=4, label="Netzbetreiber")
        ax.set_title(NAME[q])
        ax.set_xlabel("Vorlauftag")
        ax.set_ylim(0, None)
    axs[0].set_ylabel("MAE in % der Leistung")
    h, lab = axs[0].get_legend_handles_labels()
    fig.tight_layout(rect=(0, 0.1, 1, 1))
    fig.legend(h, lab, loc="lower center", ncol=4, fontsize=6.6)
    speichern(fig, "e_mae_vorlauf")


def abdeckung(k):
    fig, axs = plt.subplots(1, 3, figsize=(7.2, 2.5), sharey=True)
    for ax, q in zip(axs, QUELLEN):
        ax.axhspan(75, 85, color="#f3f3f1", zorder=0)
        ax.axhline(80, color=GRID, lw=0.8)
        ax.plot(TAGE, [k[q]["ohne"][str(n)]["treffer_pct"] for n in TAGE], "-o", ms=3,
                color=NEUTRAL, label="ohne Kalibrierung")
        ax.plot(TAGE, [k[q]["roll"][str(n)]["treffer_pct"] for n in TAGE], "-o", ms=3,
                color=QUELLE[q], label="mit CQR")
        ax.set_title(NAME[q])
        ax.set_xlabel("Vorlauftag")
        ax.set_ylim(55, 92)
    axs[0].set_ylabel("Trefferquote p10 bis p90 in %")
    axs[0].legend(fontsize=6.4, loc="lower left")
    fig.tight_layout()
    speichern(fig, "e_abdeckung")


def monate():
    fig, ax = plt.subplots(figsize=(6.6, 2.8))
    teile = {"solar": pd.read_parquet(PH / "solar_rollierend_bester.parquet"),
             "wind_onshore": pd.read_parquet(PH / "wind_onshore_vorhersagen.parquet"),
             "wind_offshore": pd.read_parquet(PH / "wind_offshore_vorhersagen.parquet")}
    for q, e in teile.items():
        if "teil" in e:
            e = e[e.teil == "rollierend"]
        for n, ls in ((1, "-"), (6, "--")):
            g = e[e.vorlauf_tag == n]
            m = (g.a - g.p50).abs().groupby(g.monat).mean() * 100
            ax.plot(pd.to_datetime(m.index), m.values, ls, color=QUELLE[q], lw=1.3,
                    label=f"{NAME[q]}, Tag {n}")
    ax.set_ylabel("MAE in % der Leistung")
    ax.set_title("Fehler je Testmonat (rollierend, Tag 1 und Tag 6)")
    ax.legend(fontsize=6.2, ncol=3, loc="upper left")
    ax.set_ylim(0, None)
    speichern(fig, "e_monate")


def wichtigkeit():
    fig, axs = plt.subplots(1, 3, figsize=(7.4, 3.4))
    for ax, q in zip(axs, QUELLEN):
        b = lgb.Booster(model_file=str(modellordner() / f"{q}_p50.txt"))
        w = pd.Series(b.feature_importance("gain"), index=b.feature_name())
        w = (w / w.sum() * 100).sort_values().tail(10)
        Z[f"wicht_{q}_top"] = w.index[-1]
        Z[f"wicht_{q}_top_pct"] = float(w.iloc[-1])
        ax.barh(range(len(w)), w.values, color=QUELLE[q])
        ax.set_yticks(range(len(w)), [n.replace("__", ": ").replace("_", " ") for n in w.index],
                      fontsize=5.6)
        ax.set_title(NAME[q])
        ax.set_xlabel("Anteil am Gewinn in %")
        ax.grid(axis="y", visible=False)
    fig.tight_layout()
    speichern(fig, "e_wichtigkeit")


def beispielwoche():
    e = pd.read_parquet(PH / "wind_onshore_vorhersagen.parquet")
    e = e[e.teil == "abschluss"]
    z = pd.DatetimeIndex(e.index.get_level_values("zeit"))
    start = pd.Timestamp("2026-10-12", tz="UTC")
    fig, axs = plt.subplots(2, 1, figsize=(6.8, 4.0), sharex=True)
    for ax, n in zip(axs, (1, 5)):
        sel = (e.vorlauf_tag == n) & (z >= start) & (z < start + pd.Timedelta(days=7))
        g = e[sel].copy()
        t = pd.DatetimeIndex(g.index.get_level_values("zeit")).tz_convert("Europe/Berlin")
        gw = g.kap_mw / 1000
        ax.fill_between(t, g.p10 * gw, g.p90 * gw, color=QUELLE["wind_onshore"], alpha=0.18,
                        lw=0, label="p10 bis p90")
        ax.plot(t, g.p50 * gw, color=QUELLE["wind_onshore"], lw=1.2, label="p50")
        ax.plot(t, g.a * gw, color="#0b0b0b", lw=0.9, label="gemessen (SMARD)")
        ax.set_title(f"Wind an Land, Vorlauftag {n} (Abschlusstest)")
        ax.set_ylabel("GW")
        ax.set_ylim(0, None)
    axs[0].legend(fontsize=6.4, ncol=3, loc="upper left")
    fig.autofmt_xdate()
    fig.tight_layout()
    speichern(fig, "e_beispielwoche")


def betrieb():
    """Erste echte Vorhersage des Betriebsmodells (Vergleichsdatei, 3. November 2026)."""
    datei = sorted(P4.glob("vergleich_*.json"))[-1]
    v = json.loads(datei.read_text())
    meta = json.loads((modellordner() / "modell.json").read_text())
    glob = next(lf for lf in v["laeufe"] if lf["model"] == "dwd_icon")
    ende = pd.Timestamp(glob["init"] + 148 * 3600, unit="s", tz="UTC")  # Horizont wie im Tool
    fig, ax = plt.subplots(figsize=(6.8, 2.9))
    for q in QUELLEN:
        e = v["erwartet"][q]
        t = pd.to_datetime(e["zeit"])
        p = np.array(e["p"])[t < ende]
        t = t[t < ende].tz_convert("Europe/Berlin")
        monat = t[0].strftime("%Y-%m")
        gw = meta["kapazitaet"][q]["monate"][monat] / 1000
        ax.fill_between(t, p[:, 0] * gw, p[:, 2] * gw, color=QUELLE[q], alpha=0.18, lw=0)
        ax.plot(t, p[:, 1] * gw, color=QUELLE[q], lw=1.2, label=NAME[q])
    for lf in v["laeufe"]:
        if lf["model"] == "dwd_icon":
            Z["betrieb_lauf_global"] = pd.Timestamp(lf["init"], unit="s", tz="UTC").tz_convert(
                "Europe/Berlin").strftime("%d.%m.%Y %H:%M")
    ax.set_ylabel("GW")
    ax.set_title("Vorhersage aus den Läufen vom 3. November 2026 (p50 und p10 bis p90)")
    ax.legend(fontsize=6.6, loc="upper right")
    fig.autofmt_xdate()
    speichern(fig, "e_betrieb")


def interpolation():
    datei = P4 / "interpolation.json"
    if not datei.exists():
        Z["interp_laeufe"] = 0
        return
    r = json.loads(datei.read_text())
    Z["interp_laeufe"] = len(r["laeufe"])
    if len(r["laeufe"]) < 12:  # Download noch nicht fertig: keine Grafik aus Teildaten
        return
    fig, axs = plt.subplots(1, 3, figsize=(7.2, 2.5), sharey=True)
    for ax, q in zip(axs, QUELLEN):
        b = r[q]["je_band"]
        x = sorted(int(k) for k in b)
        for art, farbe, ls in (("abgerundet", NEUTRAL, "--"), ("interpoliert", QUELLE[q], "-")):
            ax.plot(x, [b[str(i)][f"treffer_{art}"] for i in x], ls, color=farbe, lw=1.2,
                    label=art)
        ax.axhspan(75, 85, color="#f3f3f1", zorder=0)
        ax.set_title(NAME[q])
        ax.set_xlabel("Vorlauf in Stunden")
        for art in ("abgerundet", "interpoliert"):
            Z[f"interp_{q}_tr_{art}"] = r[q]["gesamt"]["treffer"][art]
            Z[f"interp_{q}_mae_{art}"] = r[q]["gesamt"]["fehler"][art]
    axs[0].set_ylabel("Trefferquote in %")
    axs[0].legend(fontsize=6.4)
    fig.tight_layout()
    speichern(fig, "e_interpolation")


def literaturvergleich():
    """RMSE und MAE fuer den Vergleich mit Studien (scripts/literaturvergleich.py)."""
    datei = ROOT / "data" / "betrieb" / "literaturvergleich.json"
    if not datei.exists():
        return
    kurz = {"solar": "sol", "wind_onshore": "won", "wind_offshore": "wof"}
    for q, r in json.loads(datei.read_text()).items():
        for n in range(1, 7):
            Z[f"lit_{kurz[q]}_rmse_{n}"] = r[f"tag{n}"]["rmse"]
        Z[f"lit_{kurz[q]}_nb_rmse"] = r["nb"]["rmse"]


def main():
    k, a, s1 = lade()
    zahlen(k, a, s1)
    skill(k)
    mae(k)
    abdeckung(k)
    monate()
    wichtigkeit()
    beispielwoche()
    betrieb()
    interpolation()
    literaturvergleich()
    (HIER / "abb" / "zahlen_ergebnisse.json").write_text(
        json.dumps(Z, indent=1, ensure_ascii=False, default=float))
    print(len(Z), "Zahlen")


if __name__ == "__main__":
    main()
