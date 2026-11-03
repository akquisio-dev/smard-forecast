"""Phase 5: monatliches Neu-Training (Python-Teil, laeuft in der Sandbox).

1. Daten nachladen: Wettervorhersagen (nur neue Tage), SMARD, installierte Leistung.
2. Rollierende Pruefung ueber ALLE Monate ab 03/2025 bis zum letzten vollstaendigen Monat,
   genau wie in Phase 2 und 3 (Startwerte, 7 Tage Abstand, leckfreie CQR). Ergebnis je Quelle
   in data/betrieb/<quelle>_rollierend.parquet (Rohwerte vor der Kalibrierung).
3. Schranke: Der neueste Monat muss im ueblichen Rahmen liegen (siehe pruefe()). Sonst wird
   kein neues Modell exportiert; Status und Gruende stehen in data/betrieb/status.json.
4. Export des Betriebsmodells (scripts/phase4_export.py) und der Vergleichsdaten fuer den
   TypeScript-Test (scripts/phase4_vergleich.py).

Exit-Code 0: neues Modell bereit (Version in status.json); 2: angehalten; 1: Fehler.
Aufruf: scripts/als-dienst.sh scripts/monatlich.py [--ohne-nachladen]
Den Git-Teil (Branch in smard-mcp) erledigt scripts/monatlich.sh ausserhalb der Sandbox.
"""

import datetime as dt
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HIER = Path(__file__).resolve().parent
sys.path.insert(0, str(HIER.parent))
sys.path.insert(0, str(HIER))
import phase2_abstimmung as A  # noqa: E402
import phase2_solar as P  # noqa: E402
import phase3_wind as W  # noqa: E402
from sf.log import log  # noqa: E402
from sf.orte import ROOT  # noqa: E402

QUELLEN = ("solar", "wind_onshore", "wind_offshore")
BETRIEB = ROOT / "data" / "betrieb"
# Schranke fuer den neuesten Monat, je Vorlauftag
TREFFER_MIN, TREFFER_MAX = 65.0, 95.0  # Trefferquote p10..p90 in %
MAE_FAKTOR = 1.6  # hoechstens so viel mal der mittlere MAE der Monate davor


def schritt(skript, *args):
    t0 = time.time()
    r = subprocess.run([sys.executable, "-I", str(HIER / skript), *args],
                       capture_output=True, text=True)
    zeilen = [z for z in (r.stdout + r.stderr).splitlines() if "Warning" not in z]
    for z in zeilen[-5:]:
        log(f"  {skript}: {z}")
    if r.returncode != 0:
        raise RuntimeError(f"{skript} endete mit {r.returncode}")
    log(f"{skript} fertig ({time.time() - t0:.0f} s)")


def letzter_voller_monat() -> str:
    """Letzter Monat (Berlin), fuer den SMARD alle drei Quellen bis zum Monatsende hat."""
    enden = []
    for q in QUELLEN:
        s = pd.read_parquet(ROOT / "data" / "smard" / f"generation_{q}.parquet").dropna()
        enden.append(s.zeit.max())
    ende = min(enden).tz_convert("Europe/Berlin") + pd.Timedelta(hours=1)
    monat = ende.to_period("M")
    if ende < (monat + 1).start_time.tz_localize("Europe/Berlin"):
        monat -= 1
    return str(monat)


def rollierend(quelle: str, bis: str) -> pd.DataFrame:
    d, merk = A.vorbereiten() if quelle == "solar" else W.vorbereiten(quelle)
    monate = [m for m in sorted(d.monat.unique()) if P.ERSTER_TEST <= m <= bis]
    teile = []
    for tm in monate:
        tr, te, mod = A.fold(d, merk, tm, A.RASTER["A_start"])
        p = P.vorhersagen(mod, te, merk)
        k, pers = P.messlatten(d, tr, te)
        teile.append(te[["a", "a_nb", "kap_mw", "vorlauf_tag", "datum", "monat"]].join(p)
                     .assign(klima=k, pers=pers))
    log(f"  {quelle}: {len(monate)} Monate {monate[0]} bis {monate[-1]}")
    return pd.concat(teile)


def pruefe(quelle: str, kal: pd.DataFrame) -> list[str]:
    """Gruende gegen ein neues Modell (leer = in Ordnung)."""
    gruende = []
    neu = kal.monat.max()
    for n in range(1, 7):
        g = kal[kal.vorlauf_tag == n]
        m = g[g.monat == neu]
        vorher = g[g.monat < neu]
        tr = float(((m.a >= m.p10) & (m.a <= m.p90)).mean() * 100)
        mae = float((m.a - m.p50).abs().mean() * 100)
        mae_v = float((vorher.a - vorher.p50).abs().groupby(vorher.monat).mean().mean() * 100)
        if not TREFFER_MIN <= tr <= TREFFER_MAX:
            gruende.append(f"{quelle} Tag {n}: Trefferquote {tr:.1f} % im Monat {neu}")
        if mae > MAE_FAKTOR * mae_v:
            gruende.append(f"{quelle} Tag {n}: MAE {mae:.2f} % im Monat {neu}, "
                           f"Mittel davor {mae_v:.2f} %")
    kz = P.kennzahlen(kal)
    for n, r in kz.items():
        if r["skill_einfach"] <= 0:
            gruende.append(f"{quelle} Tag {n}: Skill {r['skill_einfach']:.2f} ueber alle Monate")
    return gruende


def main():
    t0 = time.time()
    BETRIEB.mkdir(parents=True, exist_ok=True)
    status = {"start": f"{dt.datetime.now(dt.timezone.utc):%Y-%m-%dT%H:%MZ}"}
    if "--ohne-nachladen" not in sys.argv:
        gestern = (dt.date.today() - dt.timedelta(days=1)).isoformat()
        schritt("download.py", "--bis", gestern)
        schritt("smard_laden.py")
        schritt("kapazitaet.py")
    bis = letzter_voller_monat()
    status["letzter_monat"] = bis
    log(f"rollierende Pruefung bis {bis}")
    gruende, neueste = [], {}
    for q in QUELLEN:
        roh = rollierend(q, bis)
        roh.to_parquet(BETRIEB / f"{q}_rollierend.parquet")
        kal = A.cqr(roh)
        gruende += pruefe(q, kal)
        r = P.kennzahlen(kal[kal.monat == kal.monat.max()])
        neueste[q] = {n: {"mae_pct": round(v["mae_pct"], 3), "treffer_pct": round(v["treffer_pct"], 1),
                          "skill": round(v["skill_einfach"], 3)} for n, v in r.items()}
        for n, v in neueste[q].items():
            log(f"  {q} {bis} Tag {n}: MAE {v['mae_pct']:.2f} % Treffer {v['treffer_pct']:.1f} % "
                f"Skill {v['skill']:.2f}")
    status["neuester_monat"] = neueste
    if gruende:
        status.update(ergebnis="angehalten", gruende=gruende)
        (BETRIEB / "status.json").write_text(json.dumps(status, indent=1, ensure_ascii=False))
        for g in gruende:
            log(f"ANGEHALTEN: {g}")
        return 2
    schritt("phase4_export.py")
    version = sorted(p.name for p in (ROOT / "data" / "modell").iterdir())[-1]
    schritt("phase4_vergleich.py", version)
    status.update(ergebnis="bereit", version=version, laufzeit_s=round(time.time() - t0))
    (BETRIEB / "status.json").write_text(json.dumps(status, indent=1, ensure_ascii=False))
    log(f"neues Modell {version} bereit ({status['laufzeit_s']} s)")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001
        log(f"FEHLER: {type(e).__name__}: {e}")
        sys.exit(1)
