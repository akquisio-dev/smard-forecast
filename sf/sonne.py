"""Sonnenstand (Naeherung nach Spencer 1971, genau auf etwa 0,5 Grad)."""

import numpy as np
import pandas as pd


def sonnenhoehe(zeit_utc: pd.DatetimeIndex, lat: float, lon: float) -> np.ndarray:
    """Sonnenhoehe in Grad fuer die gegebenen UTC-Zeitpunkte an einem Ort."""
    doy = zeit_utc.dayofyear.values
    stunde = zeit_utc.hour.values + zeit_utc.minute.values / 60
    g = 2 * np.pi / 365 * (doy - 1 + (stunde - 12) / 24)
    dekl = (0.006918 - 0.399912 * np.cos(g) + 0.070257 * np.sin(g) - 0.006758 * np.cos(2 * g)
            + 0.000907 * np.sin(2 * g) - 0.002697 * np.cos(3 * g) + 0.00148 * np.sin(3 * g))
    zgl = 229.18 * (0.000075 + 0.001868 * np.cos(g) - 0.032077 * np.sin(g)
                    - 0.014615 * np.cos(2 * g) - 0.040849 * np.sin(2 * g))
    w = np.radians((stunde * 60 + zgl + 4 * lon) / 4 - 180)
    phi = np.radians(lat)
    sin_h = np.sin(phi) * np.sin(dekl) + np.cos(phi) * np.cos(dekl) * np.cos(w)
    return np.degrees(np.arcsin(np.clip(sin_h, -1, 1)))


def max_sonnenhoehe(zeit_utc: pd.DatetimeIndex, orte) -> np.ndarray:
    """Hoechste Sonnenhoehe ueber alle Orte. Unter 0 = an keinem Ort ist die Sonne auf.

    Ersetzt die fruehere Nachtgrenze an einem einzigen Punkt (51 N, 10 O), die die
    Daemmerung im Osten und Westen abschnitt (563 Stunden mit Solarstrom bei Sonne < 0).
    """
    return np.max([sonnenhoehe(zeit_utc, o.lat, o.lon) for o in orte], axis=0)
