"""Caratteristiche termiche dinamiche - UNI EN ISO 13786 (metodo delle matrici di trasferimento).

Periodo 24 h. Strati dall'interno (lato 1) all'esterno (lato 2), come nel resto del modello.
Risultati: trasmittanza termica periodica Y_ie [W/m2K], fattore di attenuazione f = Y_ie/U,
sfasamento [h], capacità termiche areiche interna ed esterna k_1, k_2 [kJ/m2K].
"""
import cmath
import math
from dataclasses import dataclass

from .involucro import StrutturaOpaca

T = 86400.0


def _mat(a, b, c, d):
    return [[a, b], [c, d]]


def _mul(x, y):
    return [[x[0][0] * y[0][0] + x[0][1] * y[1][0], x[0][0] * y[0][1] + x[0][1] * y[1][1]],
            [x[1][0] * y[0][0] + x[1][1] * y[1][0], x[1][0] * y[0][1] + x[1][1] * y[1][1]]]


def _strato(lam, rho, c, d):
    delta = math.sqrt(lam * T / (math.pi * rho * c))
    xi = d / delta
    z = xi * (1 + 1j)
    return _mat(cmath.cosh(z), -delta / (2 * lam) * (1 - 1j) * cmath.sinh(z),
                -lam / delta * (1 + 1j) * cmath.sinh(z), cmath.cosh(z))


def _resistenza(r):
    return _mat(1, -r, 0, 1)


@dataclass
class Dinamica:
    y_ie: float
    fattore_attenuazione: float
    sfasamento_h: float
    k_1: float
    k_2: float


def dinamica(s: StrutturaOpaca) -> Dinamica:
    if not s.strati:
        raise ValueError(f"{s.id}: servono gli strati")
    # Z = Z_s2 · Z_N ... Z_1 · Z_s1   (lato 1 = interno)
    z = _resistenza(s.rsi)
    for st in s.strati:
        m = st.materiale
        if st.intercapedine or m.lambda_ is None or m.rho <= 0:
            zs = _resistenza(st.resistenza(s.flusso))
        else:
            zs = _strato(m.lambda_, m.rho, m.c, st.spessore)
        z = _mul(zs, z)
    z = _mul(_resistenza(s.rse if s.rse > 0 else 0.04), z)
    y12 = -1 / z[0][1]
    y_ie = abs(y12)
    # sfasamento: ritardo del flusso interno rispetto alla sollecitazione esterna = -arg(Y12)/ω
    sfas = (-cmath.phase(y12) * 24 / (2 * math.pi)) % 24
    k1 = T / (2 * math.pi) * abs((z[0][0] - 1) / z[0][1]) / 1000
    k2 = T / (2 * math.pi) * abs((z[1][1] - 1) / z[0][1]) / 1000
    return Dinamica(y_ie=y_ie, fattore_attenuazione=y_ie * s.r_totale, sfasamento_h=sfas, k_1=k1, k_2=k2)
