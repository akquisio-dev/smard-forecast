"""Trainingstabelle und Merkmale (Phase 2).

Eine Zeile = eine SMARD-Stunde S (Zeitstempel = Anfang der Stunde, UTC) und ein Vorlauftag N.

Zeitliche Ausrichtung (docs/phase0.md, Nachtrag):
  * Strahlungsgroessen sind bei Open-Meteo Mittel der VORANGEGANGENEN Stunde: der Wert bei
    S+1h gehoert zur SMARD-Stunde S.
  * Momentanwerte (Temperatur, Wolken, Wind) werden auf die Stundenmitte gemittelt:
    (x(S) + x(S+1h)) / 2.
"""

import glob
from pathlib import Path

import numpy as np
import pandas as pd

from sf.kalender import feiertage
from sf.orte import ROOT, lade_orte
from sf.sonne import max_sonnenhoehe, sonnenhoehe

STRAHLUNG = {"shortwave_radiation", "direct_radiation", "diffuse_radiation"}


def wetter_ort(name: str, variablen: list[str]) -> pd.DataFrame:
    """Lange Form eines Ortes, zeitlich auf SMARD-Stunden ausgerichtet."""
    teile = [pd.read_parquet(f) for f in sorted(glob.glob(str(ROOT / "data" / "wetter" / name /
                                                                "*.parquet")))]
    df = pd.concat(teile).sort_values(["vorlauf", "zeit"]).reset_index(drop=True)
    aus = []
    for n, g in df.groupby("vorlauf"):
        g = g.set_index("zeit").asfreq("h")
        neu = pd.DataFrame(index=g.index)
        for v in variablen:
            x = g[v].astype("float32")
            if v.startswith("wind_direction"):
                # Richtung ist ein Kreis (359 Grad liegt neben 1 Grad): erst in Sinus und
                # Kosinus zerlegen, dann auf die Stundenmitte mitteln
                r = np.radians(x)
                for f, name in ((np.sin, "sin"), (np.cos, "cos")):
                    y = f(r).astype("float32")
                    neu[f"{v}_{name}"] = (y + y.shift(-1)) / 2
                continue
            nach = x.shift(-1)
            neu[v] = nach if v in STRAHLUNG else (x + nach) / 2
        neu["vorlauf"] = np.int8(n)
        aus.append(neu.reset_index())
    return pd.concat(aus, ignore_index=True)


def wetter_breit(typ: str, variablen: list[str]) -> pd.DataFrame:
    orte = [o for o in lade_orte() if typ in o.typ]
    breit = None
    for o in orte:
        d = wetter_ort(o.name, variablen).set_index(["zeit", "vorlauf"])
        d.columns = [f"{o.name}__{c}" for c in d.columns]
        breit = d if breit is None else breit.join(d, how="outer")
    spalten = sorted({c.split("__", 1)[1] for c in breit.columns})
    for v in spalten:
        breit[f"mittel__{v}"] = breit[[f"{o.name}__{v}" for o in orte]].mean(axis=1)
    return breit


def kalender(zeit: pd.DatetimeIndex, orte) -> pd.DataFrame:
    mitte = zeit + pd.Timedelta(minutes=30)
    lokal = mitte.tz_convert("Europe/Berlin")
    h = mitte.hour + 0.5
    doy = mitte.dayofyear
    tage = set()
    for j in range(lokal.year.min(), lokal.year.max() + 1):
        tage |= feiertage(j)
    return pd.DataFrame({
        "stunde_sin": np.sin(2 * np.pi * h / 24), "stunde_cos": np.cos(2 * np.pi * h / 24),
        "jahr_sin": np.sin(2 * np.pi * doy / 365.25), "jahr_cos": np.cos(2 * np.pi * doy / 365.25),
        "sonne_mitte": sonnenhoehe(mitte, 51.0, 10.0),
        "sonne_max": max_sonnenhoehe(mitte, orte),
        "wochentag": lokal.dayofweek.astype("int8"),
        "feiertag": np.array([d in tage for d in lokal.date], dtype="int8"),
    }, index=zeit)


def kapazitaet(quelle: str, zeit: pd.DatetimeIndex) -> np.ndarray:
    k = pd.read_parquet(ROOT / "data" / "kapazitaet.parquet").set_index("monat")[quelle]
    monat = zeit.tz_convert("Europe/Berlin").strftime("%Y-%m")
    return monat.map(k).to_numpy(dtype="float64")


def smard(schluessel: str) -> pd.Series:
    s = pd.read_parquet(ROOT / "data" / "smard" / f"{schluessel}.parquet").dropna()
    return s.set_index("zeit").mwh


def tabelle_solar() -> tuple[pd.DataFrame, list[str]]:
    from sf.openmeteo import VARIABLEN
    orte = [o for o in lade_orte() if "solar" in o.typ]
    w = wetter_breit("solar", VARIABLEN["solar"])
    zeit = w.index.get_level_values("zeit")
    kal = kalender(pd.DatetimeIndex(zeit.unique()), orte)
    d = w.join(kal, on="zeit")
    d["vorlauf_tag"] = d.index.get_level_values("vorlauf").astype("int8")
    ist = smard("generation_solar")
    d = d.join(ist.rename("ist_mwh"), on="zeit")
    nb = smard("forecast_generation_solar")
    d = d.join(nb.rename("nb_mwh"), on="zeit")
    zt = pd.DatetimeIndex(d.index.get_level_values("zeit"))
    d["kap_mw"] = kapazitaet("solar", zt)
    d["a"] = d.ist_mwh / d.kap_mw
    d["a_nb"] = d.nb_mwh / d.kap_mw
    merkmale = [c for c in d.columns if "__" in c] + list(kal.columns) + ["vorlauf_tag"]
    return d, merkmale


def tabelle_wind(quelle: str) -> tuple[pd.DataFrame, list[str]]:
    """quelle: wind_onshore (Orte vom Typ wind) oder wind_offshore (Typ offshore)."""
    from sf.openmeteo import VARIABLEN
    typ = "wind" if quelle == "wind_onshore" else "offshore"
    orte = [o for o in lade_orte() if typ in o.typ]
    w = wetter_breit(typ, VARIABLEN[typ])
    zeit = w.index.get_level_values("zeit")
    kal = kalender(pd.DatetimeIndex(zeit.unique()), orte).drop(columns=["sonne_max"])
    d = w.join(kal, on="zeit")
    d["vorlauf_tag"] = d.index.get_level_values("vorlauf").astype("int8")
    d = d.join(smard(f"generation_{quelle}").rename("ist_mwh"), on="zeit")
    d = d.join(smard(f"forecast_generation_{quelle}").rename("nb_mwh"), on="zeit")
    zt = pd.DatetimeIndex(d.index.get_level_values("zeit"))
    d["kap_mw"] = kapazitaet(quelle, zt)
    d["a"] = d.ist_mwh / d.kap_mw
    d["a_nb"] = d.nb_mwh / d.kap_mw
    merkmale = [c for c in d.columns if "__" in c] + list(kal.columns) + ["vorlauf_tag"]
    return d, merkmale
