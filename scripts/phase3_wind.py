"""Phase 3: Wind an Land und Wind auf See, mit dem Verfahren, das sich bei Solar bewaehrt hat.

Startwerte der Hyperparameter (bei Solar blieben sie die besten), 7 Tage Abstand zwischen
Training und Testmonat, rollierend 03/2025 bis 07/2026, leckfreie Kalibrierung der Bandbreite.
Fuer Wind ist der Abschlusstest (08 bis 10/2026) noch unberuehrt: Er wird hier genau einmal
benutzt, mit einer Kalibrierung, die nur aus den rollierenden Monaten gelernt ist.

Aufruf: scripts/als-dienst.sh scripts/phase3_wind.py
"""

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import phase2_abstimmung as A  # noqa: E402
import phase2_solar as P  # noqa: E402
from sf.log import log  # noqa: E402
from sf.merkmale import tabelle_wind  # noqa: E402

AUS = P.AUS


def vorbereiten(quelle):
    d, merk = tabelle_wind(quelle)
    d = d[d.a.notna() & d.kap_mw.notna()]
    d = d[~d[[c for c in merk if "__" in c]].isna().all(axis=1)].copy()
    z = pd.DatetimeIndex(d.index.get_level_values("zeit"))
    d["monat"] = z.tz_convert("Europe/Berlin").strftime("%Y-%m")
    d["datum"] = z.tz_convert("Europe/Berlin").date
    d["zeit_utc"] = z
    return d, merk


def abschnitt(d, merk, tm_liste, teil):
    teile = []
    for tm in tm_liste:
        tr, te, mod = A.fold(d, merk, tm, A.RASTER["A_start"])
        p = P.vorhersagen(mod, te, merk)
        k, pers = P.messlatten(d, tr, te)
        teile.append(te[["a", "a_nb", "kap_mw", "vorlauf_tag", "datum", "monat"]].join(p)
                     .assign(klima=k, pers=pers, teil=teil))
        log(f"  {tm} fertig")
    return teile


def main():
    t0 = time.time()
    erg = {}
    for quelle in ("wind_onshore", "wind_offshore"):
        d, merk = vorbereiten(quelle)
        log(f"{quelle}: {len(d)} Zeilen, {len(merk)} Merkmale")
        monate = [m for m in sorted(d.monat.unique()) if P.ERSTER_TEST <= m < P.ABSCHLUSS[0]]
        roll = pd.concat(abschnitt(d, merk, monate, "rollierend"))
        # Abschluss 08 bis 10/2026: wie im Betrieb monatlich neu trainiert (je Monat bis 7 Tage
        # vor Monatsbeginn); keine Einstellung wird an diesen Monaten gewaehlt
        abschl = pd.concat(abschnitt(d, merk, P.ABSCHLUSS, "abschluss"))
        abschl["monat_test"] = abschl.monat
        # leckfreie Kalibrierung: rollierend Monat fuer Monat aus den Monaten davor,
        # Abschluss aus allen rollierenden Monaten (als ein "spaeterer Monat" behandelt)
        beide = pd.concat([roll, abschl.assign(monat="2026-08~10")])
        kal = A.cqr(beide)
        res = {"ohne_cqr_rollierend": P.kennzahlen(roll[roll.monat != monate[0]]),
               "rollierend": P.kennzahlen(kal[kal.teil == "rollierend"]),
               "abschluss": P.kennzahlen(kal[kal.teil == "abschluss"]),
               "abschluss_ohne_cqr": P.kennzahlen(abschl)}
        winter = kal.monat.str[5:].isin(["12", "01", "02"]) & (kal.teil == "rollierend")
        res["rollierend_winter"] = P.kennzahlen(kal[winter])
        erg[quelle] = res
        kal.to_parquet(AUS / f"{quelle}_vorhersagen.parquet")
        for teil in ("ohne_cqr_rollierend", "rollierend", "rollierend_winter", "abschluss"):
            for n, r in res[teil].items():
                log(f"{quelle} {teil} Tag {n}: MAE {r['mae_pct']:.2f} % ({r['mae_gw']:.2f} GW) "
                    f"Treffer {r['treffer_pct']:.1f} % Klima {r['klima_mae_pct']:.2f} Pers "
                    f"{r['pers_mae_pct']:.2f} Skill {r['skill_einfach']:.2f}"
                    + (f" NB {r['nb_mae_pct']:.2f} Skill_NB {r['skill_nb']:.2f}" if n == 1 else ""))
    erg["laufzeit_s"] = round(time.time() - t0)
    (AUS / "wind_kennzahlen.json").write_text(json.dumps(erg, indent=1, default=str))
    log(f"fertig in {erg['laufzeit_s']} s")


if __name__ == "__main__":
    main()
