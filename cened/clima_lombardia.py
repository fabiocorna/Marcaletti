"""Dati climatici dei comuni lombardi secondo l'Allegato H del Decreto 6437/2026.

- Temperatura: quella del capoluogo di provincia corretta per l'altitudine,
  θe = θe,r − (z − z_r)/178  (3.14). Irradiazione e pressione di vapore del capoluogo.
- Irradiazione su superficie orientata (App. F, F.25): modello isotropo,
  H_T = H_bh·R_b + H_dh·(1+cos β)/2 + ρ·(H_bh+H_dh)·(1−cos β)/2, ρ = 0,2, con R_b calcolato
  sul giorno tipo del mese (Prospetto F.III) integrando cos θ fra alba e tramonto sulla superficie.
Verificato contro i valori mensili prodotti da CENED+2.0 (tests).
"""
import math

from .dati_allegato1 import CAPOLUOGHI
from .modello import AZIMUT, Clima

GRADIENTE = 1 / 178  # °C/m
ALBEDO = 0.2
DECLINAZIONE = (-20.9, -13.0, -2.4, 9.4, 18.8, 23.1, 21.2, 13.5, 2.2, -9.6, -18.9, -23.1)  # Prosp. F.III
PROVINCE = {  # codice ISTAT provincia -> capoluogo
    "012": "Varese", "013": "Como", "014": "Sondrio", "015": "Milano", "016": "Bergamo",
    "017": "Brescia", "018": "Pavia", "019": "Cremona", "020": "Mantova", "097": "Lecco",
    "098": "Lodi", "108": "Monza e Brianza",
}
SIGLE = {"Varese": "VA", "Como": "CO", "Sondrio": "SO", "Milano": "MI", "Bergamo": "BG", "Brescia": "BS",
         "Pavia": "PV", "Cremona": "CR", "Mantova": "MN", "Lecco": "LC", "Lodi": "LO", "Monza e Brianza": "MB"}


def r_b(lat: float, decl: float, beta: float, gamma: float, passi: int = 720) -> float:
    """Rapporto medio giornaliero tra radiazione diretta sulla superficie e sull'orizzontale."""
    phi, d, b, g = (math.radians(x) for x in (lat, decl, beta, gamma))
    ws = math.acos(max(-1.0, min(1.0, -math.tan(phi) * math.tan(d))))
    num = den = 0.0
    dw = 2 * ws / passi
    for k in range(passi):
        w = -ws + (k + 0.5) * dw
        cz = math.sin(d) * math.sin(phi) + math.cos(d) * math.cos(phi) * math.cos(w)
        ct = (math.sin(d) * math.sin(phi) * math.cos(b)
              - math.sin(d) * math.cos(phi) * math.sin(b) * math.cos(g)
              + math.cos(d) * math.cos(phi) * math.cos(b) * math.cos(w)
              + math.cos(d) * math.sin(phi) * math.sin(b) * math.cos(g) * math.cos(w)
              + math.cos(d) * math.sin(b) * math.sin(g) * math.sin(w))
        den += max(cz, 0.0)
        if cz > 0:
            num += max(ct, 0.0)
    return num / den if den else 0.0


def irradiazione(lat: float, hb: list[float], hd: list[float], beta: float, gamma: float,
                 albedo: float = ALBEDO) -> list[float]:
    """Irradiazione globale giornaliera media mensile sulla superficie (stesse unità di hb, hd)."""
    cb = math.cos(math.radians(beta))
    return [hb[m] * r_b(lat, DECLINAZIONE[m], beta, gamma) + hd[m] * (1 + cb) / 2
            + albedo * (hb[m] + hd[m]) * (1 - cb) / 2 for m in range(12)]


def _p_sat(t: float) -> float:
    if t >= 0:
        return 610.5 * math.exp(17.269 * t / (237.3 + t))
    return 610.5 * math.exp(21.875 * t / (265.5 + t))


def clima_comune(comune: str, quota: float | None = None, provincia_istat: str | None = None,
                 zona: str | None = None, gg: float | None = None, codice_istat: str | None = None) -> Clima:
    """Clima di un comune lombardo. Se `provincia_istat` manca si cerca il comune in comuni_istat."""
    from . import comuni
    info = comuni.cerca(comune) or {}
    prov = provincia_istat or info.get("id_prov")
    if prov is None and comune.strip().title() in CAPOLUOGHI:
        cap = comune.strip().title()
    else:
        cap = PROVINCE.get(prov)
    if cap is None:
        raise ValueError(f"comune '{comune}' non trovato: indicare la provincia")
    d = CAPOLUOGHI[cap]
    z = d["z"] if quota is None else quota
    te = [round(t - (z - d["z"]) * GRADIENTE, 3) for t in d["te"]]
    irr = {esp: [round(x, 3) for x in irradiazione(d["lat"], d["hb"], d["hd"], 90.0, az)]
           for esp, az in AZIMUT.items()}
    irr["ORIZ"] = [round(b + h, 3) for b, h in zip(d["hb"], d["hd"])]
    ur = [round(min(0.99, pv / _p_sat(t)), 3) for pv, t in zip(d["pv"], te)]
    zona = zona or info.get("zc", "E")
    return Clima(comune=comune.upper(), zona_climatica="F" if zona.startswith("F") else zona, te=te,
                 irradianza=irr, gg=gg or info.get("gg"), codice_istat=codice_istat or info.get("istat"),
                 provincia=SIGLE[cap], ur=ur)
