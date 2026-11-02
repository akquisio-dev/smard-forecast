"""Liste der Wetterorte aus config/orte.toml."""

import tomllib
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Ort:
    name: str
    lat: float
    lon: float
    typ: tuple[str, ...]


def lade_orte(pfad: Path = ROOT / "config" / "orte.toml") -> list[Ort]:
    daten = tomllib.loads(pfad.read_text())
    return [Ort(o["name"], o["lat"], o["lon"], tuple(o["typ"])) for o in daten["ort"]]
