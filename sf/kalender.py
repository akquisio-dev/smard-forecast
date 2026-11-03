"""Bundesweite gesetzliche Feiertage (ohne Feiertage einzelner Laender)."""

import datetime as dt


def ostersonntag(jahr: int) -> dt.date:
    """Gausssche Osterformel in der Fassung von Lichtenberg/Meeus fuer den Gregorianischen Kalender."""
    a = jahr % 19
    b, c = divmod(jahr, 100)
    d, e = divmod(b, 4)
    g = (8 * b + 13) // 25
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    monat, tag = divmod(h + l - 7 * m + 114, 31)
    return dt.date(jahr, monat, tag + 1)


def feiertage(jahr: int) -> set[dt.date]:
    o = ostersonntag(jahr)
    return {dt.date(jahr, 1, 1), o - dt.timedelta(days=2), o + dt.timedelta(days=1),
            dt.date(jahr, 5, 1), o + dt.timedelta(days=39), o + dt.timedelta(days=50),
            dt.date(jahr, 10, 3), dt.date(jahr, 12, 25), dt.date(jahr, 12, 26)}
