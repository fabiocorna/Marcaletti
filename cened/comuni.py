"""Comuni lombardi: codice catastale -> ISTAT, zona climatica, gradi giorno (DPR 412/93).

Il file dati (`comuni_istat.json`) si cerca in $MARCALETTI_RISORSE o in ./risorse; se manca
le funzioni restituiscono risultati vuoti e l'app continua a funzionare.
"""
import json
import os
from functools import lru_cache
from pathlib import Path


def _percorso() -> Path:
    base = os.environ.get("MARCALETTI_RISORSE", str(Path(__file__).resolve().parent.parent / "risorse"))
    return Path(base) / "comuni_istat.json"


@lru_cache(maxsize=1)
def tutti() -> dict[str, dict]:
    """nome in maiuscolo -> {istat, catastale, zc, gg, id_prov}"""
    p = _percorso()
    if not p.exists():
        return {}
    dati = json.loads(p.read_text(encoding="utf-8"))
    return {v["nome"].upper(): {**v, "catastale": k, "gg": float(v["gg"]) if v.get("gg") else None}
            for k, v in dati.items()}


def cerca(nome: str) -> dict | None:
    return tutti().get(nome.strip().upper())
