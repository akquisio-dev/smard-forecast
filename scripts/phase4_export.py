"""Phase 4: Betriebsmodelle trainieren und fuer smard-mcp exportieren.

Je Quelle (solar, wind_onshore, wind_offshore) und Quantil ein LightGBM-Modell mit den
Startwerten, trainiert auf ALLEN vorhandenen Daten. Dazu:
  * Kalibrierung (CQR) je Vorlauftag aus allen bisherigen Vorhersagen ausserhalb der Stichprobe
    (rollierend und Abschluss), Ziel 80 %,
  * Kennzahlen und Guetestufe je Vorlauftag fuer die Modellbeschreibung (aus den Dateien von
    Phase 2 und 3, nie von Hand),
  * Orte, Variablen, Merkmalsreihenfolge, Kapazitaet je Monat.

Ausgabe: data/modell/<version>/ mit modell.json und <quelle>_p<q>.json (kompakte Baeume).
Aufruf: scripts/als-dienst.sh scripts/phase4_export.py [--nur-meta <version>]
"""

import datetime as dt
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
from sf.merkmale import tabelle_solar, tabelle_wind  # noqa: E402
from sf.openmeteo import MODELL, VARIABLEN  # noqa: E402
from sf.orte import ROOT, lade_orte  # noqa: E402

QUELLEN = ("solar", "wind_onshore", "wind_offshore")
PH = ROOT / "data" / "phase2"
GRENZEN = {"high": 0.4, "medium": 0.2}  # Guetestufen nach Skill gegen die einfache Messlatte


def tabelle(quelle):
    d, merk = tabelle_solar() if quelle == "solar" else tabelle_wind(quelle)
    if quelle == "solar":
        d = d[d.sonne_max > 0]
    d = d[d.a.notna() & d.kap_mw.notna()]
    d = d[~d[[c for c in merk if "__" in c]].isna().all(axis=1)]
    return d, merk


def kompakt(booster: lgb.Booster, merk: list[str]) -> dict:
    """Baeume als parallele Listen; Schwellen exakt (float64), Reihenfolge der Merkmale fest."""
    dump = booster.dump_model()
    assert dump["feature_names"] == merk
    baeume = []
    for t in dump["tree_info"]:
        knoten = {k: [] for k in ("f", "t", "m", "d", "l", "r")}
        blaetter = []

        def lauf(n):
            if "leaf_index" in n or "leaf_value" in n and "split_index" not in n:
                blaetter.append(n["leaf_value"])
                return -len(blaetter)  # Blatt i -> -(i+1)
            assert n["decision_type"] == "<=", n["decision_type"]
            i = len(knoten["f"])
            for k in knoten:
                knoten[k].append(None)
            knoten["f"][i] = n["split_feature"]
            knoten["t"][i] = n["threshold"]
            knoten["m"][i] = {"None": 0, "Zero": 1, "NaN": 2}[n["missing_type"]]
            knoten["d"][i] = 1 if n["default_left"] else 0
            knoten["l"][i] = lauf(n["left_child"])
            knoten["r"][i] = lauf(n["right_child"])
            return i

        lauf(t["tree_structure"])
        baeume.append({**knoten, "v": blaetter})
    return {"merkmale": merk, "baeume": baeume}


def cqr_betrieb(quelle) -> dict:
    """Breitenzuschlag je Vorlauftag aus allen Vorhersagen ausserhalb der Stichprobe."""
    if quelle == "solar":
        e = pd.concat([pd.read_parquet(PH / "solar_rollierend_bester.parquet"),
                       pd.read_parquet(PH / "solar_vorhersagen.parquet").query("teil == 'abschluss'")])
        e["s"] = np.maximum(e.p10 - e.a, e.a - e.p90)
    else:
        e = pd.read_parquet(PH / f"{quelle}_vorhersagen.parquet")  # s = Rohabstand, vor CQR
    aus = {}
    for n, g in e.groupby("vorlauf_tag"):
        k = len(g)
        aus[int(n)] = float(np.quantile(g.s, min(1, 0.8 * (1 + 1 / k))))
    return aus


def pruefung(quelle) -> dict:
    """Wie die Kennzahlen entstanden sind (fuer die Modellbeschreibung, nicht von Hand)."""
    if quelle == "solar":
        e = pd.read_parquet(PH / "solar_rollierend_bester.parquet")
        monate = sorted(e.monat.unique())[1:]  # der erste Monat dient nur der Kalibrierung
        return {"rollierend_von": monate[0], "rollierend_bis": monate[-1], "abstand_tage": 7,
                "abschluss_von": P.ABSCHLUSS[0], "abschluss_bis": P.ABSCHLUSS[-1],
                "abschluss_kalibriert": False, "abschluss_abstand_tage": 0}
    e = pd.read_parquet(PH / f"{quelle}_vorhersagen.parquet")
    monate = sorted(e[e.teil == "rollierend"].monat.unique())
    return {"rollierend_von": monate[0], "rollierend_bis": monate[-1], "abstand_tage": 7,
            "abschluss_von": P.ABSCHLUSS[0], "abschluss_bis": P.ABSCHLUSS[-1],
            "abschluss_kalibriert": True, "abschluss_abstand_tage": 7}


def kennzahlen(quelle) -> dict:
    """Gemessene Fehler: rollierend mit Kalibrierung und Abschlusstest (erster Blick)."""
    if quelle == "solar":
        roll = json.loads((PH / "solar_abstimmung.json").read_text())["mit_cqr"]
        absch = json.loads((PH / "solar_kennzahlen_lauf1_startwerte.json").read_text())["abschluss"]
        absch_cqr = False
    else:
        w = json.loads((PH / "wind_kennzahlen.json").read_text())[quelle]
        roll, absch, absch_cqr = w["rollierend"], w["abschluss"], True
    tage = {}
    for n in range(1, 7):
        r, a = roll[str(n)], absch[str(n)]
        skill = min(r["skill_einfach"], a["skill_einfach"])
        stufe = "high" if skill >= GRENZEN["high"] else "medium" if skill >= GRENZEN["medium"] else "low"
        tage[n] = {
            "mae_pct_of_capacity": round(r["mae_pct"], 2), "mae_gw": round(r["mae_gw"], 2),
            "coverage_p10_p90_pct": round(r["treffer_pct"], 1),
            "skill_vs_simple": round(r["skill_einfach"], 2),
            "holdout_mae_pct_of_capacity": round(a["mae_pct"], 2),
            "holdout_coverage_p10_p90_pct": round(a["treffer_pct"], 1),
            "holdout_skill_vs_simple": round(a["skill_einfach"], 2),
            "quality": stufe}
    r1 = roll["1"]
    return {"je_tag": tage, "holdout_calibrated": absch_cqr, "pruefung": pruefung(quelle),
            "guete_grenzen": GRENZEN,
            "day1_vs_tso": {"model_mae_pct": round(r1["modell_mae_pct_nb_stunden"], 2),
                            "tso_mae_pct": round(r1["nb_mae_pct"], 2)}}


def kapazitaet() -> dict:
    k = pd.read_parquet(ROOT / "data" / "kapazitaet.parquet").set_index("monat")
    aus = {}
    for q in QUELLEN:
        s = k[q].dropna()
        geschaetzt = k.get(f"geschaetzt_{q}", pd.Series(False, index=k.index))
        letzte = s.tail(7)
        trend = float((letzte.iloc[-1] - letzte.iloc[0]) / 6) if q != "wind_offshore" else 0.0
        aus[q] = {"monate": {m: round(float(v), 1) for m, v in s.items()},
                  "geschaetzt_ab": next((m for m in s.index if bool(geschaetzt.get(m, False))),
                                        None),
                  "trend_mw_je_monat": round(trend, 1)}
    return aus


def nur_meta(version: str):
    """Kennzahlen und Pruefangaben in modell.json neu schreiben, ohne neu zu trainieren."""
    datei = ROOT / "data" / "modell" / version / "modell.json"
    meta = json.loads(datei.read_text())
    for quelle in QUELLEN:
        meta["quellen"][quelle]["kennzahlen"] = kennzahlen(quelle)
    datei.write_text(json.dumps(meta, indent=1, default=str))
    log(f"modell.json von {version} aktualisiert (nur Beschreibung)")


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--nur-meta":
        return nur_meta(sys.argv[2])
    t0 = time.time()
    orte = lade_orte()
    trainiert_bis = None
    meta = {"modell_wetter": MODELL, "quantile": list(P.QUANTILE), "parameter": P.PARAM,
            "orte": [{"name": o.name, "lat": o.lat, "lon": o.lon, "typ": list(o.typ)}
                     for o in orte],
            "variablen": VARIABLEN, "quellen": {}}
    staende = []
    for quelle in QUELLEN:
        d, merk = tabelle(quelle)
        z = pd.DatetimeIndex(d.index.get_level_values("zeit"))
        staende.append(z.max())
        log(f"{quelle}: {len(d)} Zeilen bis {z.max()}, {len(merk)} Merkmale")
        modelle = {}
        for q in P.QUANTILE:
            m = lgb.LGBMRegressor(alpha=q, **P.PARAM)
            m.fit(d[merk], d.a)
            modelle[q] = kompakt(m.booster_, merk)
            modelle[q]["_booster"] = m.booster_
        meta["quellen"][quelle] = {"merkmale": merk, "cqr": cqr_betrieb(quelle),
                                   "kennzahlen": kennzahlen(quelle)}
        meta["quellen"][quelle]["_modelle"] = modelle
        log(f"  CQR je Tag: {meta['quellen'][quelle]['cqr']}")
    trainiert_bis = min(staende)
    version = f"{trainiert_bis:%Y.%m.%d}"
    aus = ROOT / "data" / "modell" / version
    aus.mkdir(parents=True, exist_ok=True)
    meta["version"] = version
    meta["trainiert_bis"] = f"{trainiert_bis:%Y-%m-%dT%H:%MZ}"
    meta["erstellt"] = f"{dt.datetime.now(dt.timezone.utc):%Y-%m-%dT%H:%MZ}"
    meta["kapazitaet"] = kapazitaet()
    for quelle in QUELLEN:
        for q, m in meta["quellen"][quelle].pop("_modelle").items():
            m.pop("_booster").save_model(str(aus / f"{quelle}_p{int(q * 100)}.txt"))
            (aus / f"{quelle}_p{int(q * 100)}.json").write_text(
                json.dumps(m, separators=(",", ":")))
    (aus / "modell.json").write_text(json.dumps(meta, indent=1, default=str))
    groesse = sum(f.stat().st_size for f in aus.glob("*.json")) / 1e6
    log(f"Version {version} in {aus}: {groesse:.1f} MB JSON, {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
