"""Phase 2: Solar-Modell, rollierende Validierung, Abschlusstest, Pruefpunkt A.

Aufruf: scripts/als-dienst.sh scripts/phase2_solar.py
Ergebnisse: data/phase2/ (Vorhersagen, Kennzahlen, Modelle), Protokoll data/logs/phase2_solar.log.
Hyperparameter sind die Startwerte aus docs/PLAN.md; sie werden hier NICHT an den Testdaten
eingestellt, damit Validierung und Abschlusstest ehrlich bleiben.
"""

import json
import sys
import time
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sf.log import log  # noqa: E402
from sf.merkmale import tabelle_solar  # noqa: E402
from sf.orte import ROOT  # noqa: E402

AUS = ROOT / "data" / "phase2"
AUS.mkdir(parents=True, exist_ok=True)
QUANTILE = (0.1, 0.5, 0.9)
PARAM = dict(objective="quantile", num_leaves=15, learning_rate=0.05, n_estimators=300,
             min_child_samples=50, colsample_bytree=0.8, subsample=0.8, subsample_freq=1,
             max_bin=255, n_jobs=6, verbose=-1, random_state=1)
ERSTER_TEST = "2025-03"
ABSCHLUSS = ["2026-08", "2026-09", "2026-10"]


def monat(d):
    return pd.DatetimeIndex(d.index.get_level_values("zeit")).tz_convert(
        "Europe/Berlin").strftime("%Y-%m")


def trainieren(tr, merk):
    modelle = {}
    for q in QUANTILE:
        m = lgb.LGBMRegressor(alpha=q, **PARAM)
        m.fit(tr[merk], tr.a)
        modelle[q] = m
    return modelle


def vorhersagen(modelle, te, merk):
    p = np.column_stack([modelle[q].predict(te[merk]) for q in QUANTILE])
    p = np.clip(np.sort(p, axis=1), 0, 1)  # gegen gekreuzte Quantile, Bereich 0..1
    return pd.DataFrame(p, index=te.index, columns=["p10", "p50", "p90"])


def messlatten(d, tr, te):
    """Klimatologie (aus den Trainingsdaten), Persistenz (letzter voller Tag), Netzbetreiber."""
    z_tr = pd.DatetimeIndex(tr.index.get_level_values("zeit"))
    basis = tr[tr.vorlauf_tag == 1]
    zb = pd.DatetimeIndex(basis.index.get_level_values("zeit"))
    klima = basis.a.groupby([zb.month, zb.hour]).mean()
    z = pd.DatetimeIndex(te.index.get_level_values("zeit"))
    k = pd.Series(list(zip(z.month, z.hour)), index=te.index).map(klima)
    # Persistenz: gleiche Stunde am letzten vollstaendigen Tag vor der Vorhersage
    ist = d[d.vorlauf_tag == 1].a.droplevel("vorlauf")
    n = te.vorlauf_tag.to_numpy().astype("int64")  # int8 liefe bei (n+1)*24 ueber
    vorher = z - pd.to_timedelta((n + 1) * 24, unit="h")
    pers = pd.Series(ist.reindex(vorher).to_numpy(), index=te.index)
    del z_tr
    return k, pers


def kennzahlen(e: pd.DataFrame) -> dict:
    """e: Spalten a, p10, p50, p90, klima, pers, a_nb, kap_mw, vorlauf_tag, datum."""
    aus = {}
    for n, g in e.groupby("vorlauf_tag"):
        fehler = (g.a - g.p50).abs()
        pin = np.mean([np.mean(np.maximum(q * (g.a - g[c]), (q - 1) * (g.a - g[c])))
                       for q, c in zip(QUANTILE, ("p10", "p50", "p90"))])
        tage = g.groupby("datum").apply(
            lambda x: abs(((x.a - x.p50) * x.kap_mw).sum()) / 1000, include_groups=False)
        r = {"stunden": int(len(g)),
             "mae_pct": float(fehler.mean() * 100),
             "mae_gw": float((fehler * g.kap_mw).mean() / 1000),
             "treffer_pct": float(((g.a >= g.p10) & (g.a <= g.p90)).mean() * 100),
             "pinball": float(pin * 100),
             "tagesenergie_mae_gwh": float(tage.mean()),
             "klima_mae_pct": float((g.a - g.klima).abs().mean() * 100),
             "pers_mae_pct": float((g.a - g.pers).abs().mean() * 100)}
        r["skill_einfach"] = 1 - r["mae_pct"] / min(r["klima_mae_pct"], r["pers_mae_pct"])
        if n == 1:
            nb = g.dropna(subset=["a_nb"])
            r["nb_mae_pct"] = float((nb.a - nb.a_nb).abs().mean() * 100)
            r["modell_mae_pct_nb_stunden"] = float((nb.a - nb.p50).abs().mean() * 100)
            r["skill_nb"] = 1 - r["modell_mae_pct_nb_stunden"] / r["nb_mae_pct"]
        aus[int(n)] = r
    return aus


def main():
    t0 = time.time()
    d, merk = tabelle_solar()
    log(f"Tabelle: {len(d)} Zeilen, {len(merk)} Merkmale")
    # Nachtgrenze: an keinem Solar-Ort steht die Sonne ueber dem Horizont -> Erzeugung 0,
    # nicht trainiert, nicht bewertet. Wie viel Energie faellt dadurch heraus?
    tag = d.sonne_max > 0
    eins = d[d.vorlauf_tag == 1]
    weg = eins[~(eins.sonne_max > 0)].ist_mwh.sum() / eins.ist_mwh.sum() * 100
    log(f"Nachtgrenze ueber alle Orte: {weg:.3f} % der Solarenergie liegt in ausgeschlossenen "
        f"Stunden (vorher, Landesmitte: 0,126 %)")
    d = d[tag & d.a.notna() & d.kap_mw.notna()]
    voll_leer = d[[c for c in merk if "__" in c]].isna().all(axis=1)
    d = d[~voll_leer]
    log(f"nach Nachtgrenze und Ausfaellen: {len(d)} Zeilen")
    m = monat(d)
    d = d.assign(monat=m, datum=pd.DatetimeIndex(d.index.get_level_values("zeit")).tz_convert(
        "Europe/Berlin").date)

    test_monate = [x for x in sorted(m.unique()) if ERSTER_TEST <= x < ABSCHLUSS[0]]
    ergebnisse = []
    for tm in test_monate:
        tr, te = d[d.monat < tm], d[d.monat == tm]
        mod = trainieren(tr, merk)
        p = vorhersagen(mod, te, merk)
        k, pers = messlatten(d, tr, te)
        ergebnisse.append(te[["a", "a_nb", "kap_mw", "vorlauf_tag", "datum", "monat"]]
                          .join(p).assign(klima=k, pers=pers, teil="rollierend"))
        r = kennzahlen(ergebnisse[-1])
        log(f"Test {tm}: Tag1 MAE {r[1]['mae_pct']:.2f} % Treffer {r[1]['treffer_pct']:.1f} % | "
            f"Tag6 MAE {r[6]['mae_pct']:.2f} % Treffer {r[6]['treffer_pct']:.1f} %")

    tr = d[d.monat < ABSCHLUSS[0]]
    te = d[d.monat.isin(ABSCHLUSS)]
    mod = trainieren(tr, merk)
    p = vorhersagen(mod, te, merk)
    k, pers = messlatten(d, tr, te)
    ergebnisse.append(te[["a", "a_nb", "kap_mw", "vorlauf_tag", "datum", "monat"]]
                      .join(p).assign(klima=k, pers=pers, teil="abschluss"))
    for q, mm in mod.items():
        mm.booster_.save_model(str(AUS / f"solar_p{int(q * 100)}_abschluss.txt"))
    wichtig = pd.Series(mod[0.5].booster_.feature_importance("gain"), index=merk)
    wichtig = (wichtig / wichtig.sum() * 100).sort_values(ascending=False)

    alle = pd.concat(ergebnisse)
    alle.to_parquet(AUS / "solar_vorhersagen.parquet")
    winter = alle.monat.str[5:].isin(["12", "01", "02"])
    res = {"rollierend": kennzahlen(alle[alle.teil == "rollierend"]),
           "rollierend_winter": kennzahlen(alle[(alle.teil == "rollierend") & winter]),
           "abschluss": kennzahlen(alle[alle.teil == "abschluss"]),
           "je_monat_tag1": {mo: kennzahlen(g)[1] for mo, g in alle.groupby("monat")},
           "wichtigkeit_top20": wichtig.head(20).round(2).to_dict(),
           "zeilen": int(len(d)), "merkmale": len(merk), "parameter": PARAM,
           "nacht_ausgeschlossen_energie_pct": float(weg),
           "laufzeit_s": round(time.time() - t0)}
    (AUS / "solar_kennzahlen.json").write_text(json.dumps(res, indent=1, default=str))
    for teil in ("rollierend", "rollierend_winter", "abschluss"):
        for n, r in res[teil].items():
            log(f"{teil} Tag {n}: MAE {r['mae_pct']:.2f} % ({r['mae_gw']:.2f} GW), Treffer "
                f"{r['treffer_pct']:.1f} %, Klima {r['klima_mae_pct']:.2f}, Pers "
                f"{r['pers_mae_pct']:.2f}, Skill {r['skill_einfach']:.2f}"
                + (f", NB {r['nb_mae_pct']:.2f} (Skill {r['skill_nb']:.2f})" if n == 1 else ""))
    log(f"fertig in {res['laufzeit_s']} s")


if __name__ == "__main__":
    main()
