"""Phase 2, Abstimmung NUR auf rollierenden Monaten (der Abschlusstest ist verbraucht).

1. Diagnose: Trefferquote auf den Trainingsdaten selbst (konvergiert das Quantil-Modell?).
2. Kleines Raster an Hyperparametern auf jedem dritten rollierenden Monat.
3. Kalibrierung der Bandbreite (konforme Quantilregression, CQR), leckfrei: fuer Monat M
   wird die Korrektur nur aus den Vorhersagen der rollierenden Monate VOR M gelernt.
Zwischen Trainingsende und Testmonat liegen 7 Tage Abstand (Vorlauf bis 6 Tage).

Aufruf: scripts/als-dienst.sh scripts/phase2_abstimmung.py
"""

import json
import sys
import time
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import phase2_solar as P  # noqa: E402
from sf.log import log  # noqa: E402
from sf.merkmale import tabelle_solar  # noqa: E402

AUS = P.AUS
RASTER = {
    "A_start": dict(num_leaves=15, learning_rate=0.05, n_estimators=300, min_child_samples=50),
    "B_31x800": dict(num_leaves=31, learning_rate=0.05, n_estimators=800, min_child_samples=50),
    "C_63x800": dict(num_leaves=63, learning_rate=0.05, n_estimators=800, min_child_samples=100),
    "D_31x800_lr01": dict(num_leaves=31, learning_rate=0.1, n_estimators=800,
                          min_child_samples=50),
}
ABSTAND = pd.Timedelta(days=7)


def vorbereiten():
    d, merk = tabelle_solar()
    d = d[(d.sonne_max > 0) & d.a.notna() & d.kap_mw.notna()]
    d = d[~d[[c for c in merk if "__" in c]].isna().all(axis=1)].copy()
    z = pd.DatetimeIndex(d.index.get_level_values("zeit"))
    d["monat"] = z.tz_convert("Europe/Berlin").strftime("%Y-%m")
    d["datum"] = z.tz_convert("Europe/Berlin").date
    d["zeit_utc"] = z
    return d, merk


def fold(d, merk, tm, param):
    start = pd.Timestamp(f"{tm}-01", tz="Europe/Berlin").tz_convert("UTC")
    tr = d[d.zeit_utc < start - ABSTAND]
    te = d[d.monat == tm]
    full = {**P.PARAM, **param}
    mod = {}
    for q in P.QUANTILE:
        m = lgb.LGBMRegressor(alpha=q, **full)
        m.fit(tr[merk], tr.a)
        mod[q] = m
    return tr, te, mod


def treffer(df):
    return float(((df.a >= df.p10) & (df.a <= df.p90)).mean() * 100)


def cqr(e: pd.DataFrame, ziel=0.8) -> pd.DataFrame:
    """Leckfreie konforme Korrektur je Vorlauftag: Monat M nutzt nur Monate vor M."""
    e = e.copy()
    e["s"] = np.maximum(e.p10 - e.a, e.a - e.p90)  # >0: ausserhalb der Bandbreite
    monate = sorted(e.monat.unique())
    for i, mo in enumerate(monate):
        if i == 0:
            continue
        vorher = e[e.monat.isin(monate[:i])]
        for n, g in vorher.groupby("vorlauf_tag"):
            k = len(g)
            q = np.quantile(g.s, min(1, ziel * (1 + 1 / k)))
            sel = (e.monat == mo) & (e.vorlauf_tag == n)
            e.loc[sel, "p10"] = (e.loc[sel, "p10"] - q).clip(0, 1)
            e.loc[sel, "p90"] = (e.loc[sel, "p90"] + q).clip(0, 1)
    return e[e.monat != monate[0]]


def main():
    t0 = time.time()
    d, merk = vorbereiten()
    alle_monate = [m for m in sorted(d.monat.unique()) if P.ERSTER_TEST <= m < P.ABSCHLUSS[0]]
    raster_monate = alle_monate[::3]
    log(f"{len(d)} Zeilen; Raster auf {raster_monate}")
    erg = {}

    # 1. Diagnose: Trefferquote im Training gegen Test, Startwerte, ein Monat
    tr, te, mod = fold(d, merk, "2026-03", RASTER["A_start"])
    for name, df in (("training", tr.sample(40000, random_state=1)), ("test", te)):
        p = P.vorhersagen(mod, df, merk)
        log(f"Diagnose Startwerte, {name}: Treffer {treffer(df[['a']].join(p)):.1f} %")
        erg[f"diagnose_{name}_treffer"] = treffer(df[["a"]].join(p))

    # 2. Raster
    raster = {}
    for name, param in RASTER.items():
        teile = []
        for tm in raster_monate:
            tr, te, mod = fold(d, merk, tm, param)
            p = P.vorhersagen(mod, te, merk)
            k, pers = P.messlatten(d, tr, te)
            teile.append(te[["a", "a_nb", "kap_mw", "vorlauf_tag", "datum", "monat"]].join(p)
                         .assign(klima=k, pers=pers))
        e = pd.concat(teile)
        kz = P.kennzahlen(e)
        raster[name] = {n: {k: round(v, 3) for k, v in r.items()} for n, r in kz.items()}
        log(f"Raster {name}: MAE Tag1 {kz[1]['mae_pct']:.3f} Tag6 {kz[6]['mae_pct']:.3f} | "
            f"Treffer Tag1 {kz[1]['treffer_pct']:.1f} Tag6 {kz[6]['treffer_pct']:.1f} | "
            f"Pinball Tag1 {kz[1]['pinball']:.3f} | NB-Skill {kz[1]['skill_nb']:.2f} "
            f"({time.time() - t0:.0f} s)")
    erg["raster"] = raster
    bester = min(raster, key=lambda n: np.mean([raster[n][t]["pinball"] for t in range(1, 7)]))
    log(f"bester nach mittlerem Pinball-Verlust ueber Tag 1 bis 6: {bester}")
    erg["bester"] = bester

    # 3. alle rollierenden Monate mit dem besten Satz, dann leckfreie CQR
    teile = []
    for tm in alle_monate:
        tr, te, mod = fold(d, merk, tm, RASTER[bester])
        p = P.vorhersagen(mod, te, merk)
        k, pers = P.messlatten(d, tr, te)
        teile.append(te[["a", "a_nb", "kap_mw", "vorlauf_tag", "datum", "monat"]].join(p)
                     .assign(klima=k, pers=pers))
    roh = pd.concat(teile)
    roh.to_parquet(AUS / "solar_rollierend_bester.parquet")
    kal = cqr(roh)
    vergleich = roh[roh.monat != alle_monate[0]]
    erg["ohne_cqr"] = P.kennzahlen(vergleich)
    erg["mit_cqr"] = P.kennzahlen(kal)
    winter = kal.monat.str[5:].isin(["12", "01", "02"])
    erg["mit_cqr_winter"] = P.kennzahlen(kal[winter])
    for teil in ("ohne_cqr", "mit_cqr", "mit_cqr_winter"):
        for n, r in erg[teil].items():
            log(f"{teil} Tag {n}: MAE {r['mae_pct']:.2f} % Treffer {r['treffer_pct']:.1f} % "
                f"Pinball {r['pinball']:.3f} Skill {r['skill_einfach']:.2f}"
                + (f" NB {r['nb_mae_pct']:.2f} Skill_NB {r['skill_nb']:.2f}" if n == 1 else ""))
    erg["laufzeit_s"] = round(time.time() - t0)
    (AUS / "solar_abstimmung.json").write_text(json.dumps(erg, indent=1, default=str))
    log(f"fertig in {erg['laufzeit_s']} s")


if __name__ == "__main__":
    main()
