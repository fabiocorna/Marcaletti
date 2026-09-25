"""Pavimento appoggiato sul terreno - UNI EN ISO 13370 (regime stazionario).

B' = A / (0,5 P)            dimensione caratteristica del pavimento
d_t = w + λ R_tot, con R_tot = R_si + R_f + R_se   spessore equivalente
se d_t < B':  U = 2λ / (π B' + d_t) · ln(π B' / d_t + 1)
altrimenti:   U = λ / (0,457 B' + d_t)
"""
import math

LAMBDA_TERRENO = 2.0  # W/(m K), argilla/limo (UNI EN ISO 13370, valore di default)
RSI_PAV, RSE_TERRENO = 0.17, 0.04


def u_pavimento_terreno(area: float, perimetro: float, r_tot: float, w: float = 0.30,
                        lambda_g: float = LAMBDA_TERRENO) -> float:
    """U equivalente [W/m2K]; r_tot = R_si + R_f + R_se del pavimento (come `r_gf` in CENED),
    w = spessore dei muri perimetrali [m], perimetro = perimetro esposto [m]."""
    if area <= 0 or perimetro <= 0:
        raise ValueError("area e perimetro esposto devono essere positivi")
    b1 = area / (0.5 * perimetro)
    dt = w + lambda_g * r_tot
    if dt < b1:
        return 2 * lambda_g / (math.pi * b1 + dt) * math.log(math.pi * b1 / dt + 1)
    return lambda_g / (0.457 * b1 + dt)
