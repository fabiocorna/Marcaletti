"""Libreria materiali e intercapedini per il calcolo della trasmittanza.

I valori sono INDICATIVI (ordini di grandezza tipici da UNI 10351, UNI EN ISO 10456,
UNI 10355). Per un APE vanno verificati con la norma o con la scheda tecnica del
prodotto: ogni materiale usato finisce nel registro ipotesi del progetto.

lambda_ = conducibilità [W/(m K)], rho = densità [kg/m3], c = calore specifico [J/(kg K)],
r = resistenza termica [m2 K/W] per elementi disomogenei (blocchi, solai) di spessore fisso.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Materiale:
    nome: str
    lambda_: float | None = None
    rho: float = 0.0
    c: float = 1000.0
    r: float | None = None
    spessore_fisso: float | None = None
    isolante: bool = False
    fonte: str = "indicativo"


def _m(nome, lambda_, rho, c, isolante=False):
    return Materiale(nome, lambda_=lambda_, rho=rho, c=c, isolante=isolante)


def _r(nome, r, spessore, rho, c=840):
    return Materiale(nome, r=r, spessore_fisso=spessore, rho=rho, c=c)


LIBRERIA: dict[str, Materiale] = {
    # intonaci e finiture
    "intonaco_calce_cemento": _m("Intonaco di calce e cemento", 0.90, 1800, 1000),
    "intonaco_gesso": _m("Intonaco di gesso", 0.40, 1000, 1000),
    "cartongesso": _m("Lastra di cartongesso", 0.25, 900, 1000),
    "piastrelle_ceramica": _m("Piastrelle in ceramica", 1.30, 2300, 840),
    "parquet": _m("Parquet in legno", 0.18, 700, 1600),
    "massetto_cementizio": _m("Massetto sabbia e cemento", 1.40, 2000, 1000),
    "cls_alleggerito": _m("Calcestruzzo alleggerito (sottofondo)", 0.35, 800, 1000),
    # murature e strutture
    "mattone_pieno": _m("Mattone pieno", 0.72, 1800, 840),
    "calcestruzzo_armato": _m("Calcestruzzo armato", 2.30, 2400, 1000),
    "pietra_naturale": _m("Pietra naturale compatta", 2.30, 2500, 1000),
    "legno_abete": _m("Legno di abete", 0.13, 450, 1600),
    "forato_8": _r("Laterizio forato 8 cm", 0.20, 0.08, 800),
    "forato_12": _r("Laterizio forato 12 cm", 0.31, 0.12, 800),
    "solaio_laterocemento_20_4": _r("Solaio in laterocemento 20+4", 0.33, 0.24, 1200),
    # isolanti
    "eps": _m("Polistirene espanso (EPS)", 0.035, 20, 1450, True),
    "eps_grafite": _m("EPS con grafite", 0.031, 20, 1450, True),
    "xps": _m("Polistirene estruso (XPS)", 0.034, 35, 1450, True),
    "pir": _m("Poliuretano espanso (PIR)", 0.024, 35, 1400, True),
    "lana_roccia": _m("Lana di roccia", 0.038, 100, 1030, True),
    "lana_vetro": _m("Lana di vetro", 0.040, 20, 1030, True),
    "fibra_legno": _m("Fibra di legno", 0.040, 160, 2100, True),
    # impermeabilizzazioni
    "guaina_bituminosa": _m("Guaina bituminosa", 0.17, 1100, 1000),
}

# Resistenza di intercapedini d'aria non ventilate (UNI EN ISO 6946, prospetto 8)
# spessore [mm] -> R [m2 K/W] per direzione del flusso
INTERCAPEDINI = {
    "orizzontale": [(0, 0.0), (5, 0.11), (7, 0.13), (10, 0.15), (15, 0.17), (25, 0.18), (300, 0.18)],
    "ascendente": [(0, 0.0), (5, 0.11), (7, 0.13), (10, 0.15), (15, 0.16), (25, 0.16), (300, 0.16)],
    "discendente": [(0, 0.0), (5, 0.11), (7, 0.13), (10, 0.15), (15, 0.17), (25, 0.19),
                    (50, 0.21), (100, 0.22), (300, 0.23)],
}


def r_intercapedine(spessore_m: float, flusso: str) -> float:
    """Interpolazione lineare della resistenza di un'intercapedine non ventilata."""
    mm = spessore_m * 1000
    tab = INTERCAPEDINI[flusso]
    if mm >= tab[-1][0]:
        return tab[-1][1]
    for (x0, y0), (x1, y1) in zip(tab, tab[1:]):
        if x0 <= mm <= x1:
            return y0 + (y1 - y0) * (mm - x0) / (x1 - x0)
    return 0.0
