"""Verifica termoigrometrica - UNI EN ISO 13788 (metodo di Glaser, mensile).

- Condensa superficiale / muffa: fattore di temperatura f_Rsi > f_Rsi,max (con R_si = 0,25).
- Condensa interstiziale: diagramma di Glaser con costruzione della curva di pressione
  come inviluppo convesso inferiore delle pressioni di saturazione; accumulo ed
  evaporazione mese per mese a partire dal primo mese con condensa.

Umidità interna da classe di concentrazione del vapore (prospetto A.2): p_i = p_e + 1,10 Δp,
con Δp lineare tra θe = 0 °C (valore della classe) e θe = 20 °C (0).
"""
import math
from dataclasses import dataclass, field

from .involucro import StrutturaOpaca
from .modello import GIORNI_MESE, MESI

DELTA0 = 2e-10  # permeabilità al vapore dell'aria [kg/(m s Pa)]
RSI_MUFFA = 0.25
CLASSI_DP = {1: 270, 2: 540, 3: 810, 4: 1080, 5: 1350}  # Pa a θe <= 0 °C
UR_MUFFA = 0.80


def p_sat(theta: float) -> float:
    if theta >= 0:
        return 610.5 * math.exp(17.269 * theta / (237.3 + theta))
    return 610.5 * math.exp(21.875 * theta / (265.5 + theta))


def theta_da_p_sat(p: float) -> float:
    x = math.log(p / 610.5)
    if p >= 610.5:
        return 237.3 * x / (17.269 - x)
    return 265.5 * x / (21.875 - x)


def delta_p(theta_e: float, classe: int) -> float:
    dp0 = CLASSI_DP[classe]
    if theta_e <= 0:
        return dp0
    if theta_e >= 20:
        return 0.0
    return dp0 * (20 - theta_e) / 20


@dataclass
class MeseGlaser:
    mese: str
    te: float
    ur_e: float
    p_i: float
    f_rsi_min: float
    condensa: list[float]  # kg/m2 condensati (+) o evaporati (-) nel mese per interfaccia
    accumulo: list[float]  # kg/m2 accumulati a fine mese per interfaccia


@dataclass
class EsitoGlaser:
    f_rsi: float
    f_rsi_max: float
    mese_critico: str
    mesi: list[MeseGlaser] = field(default_factory=list)
    interfacce: list[str] = field(default_factory=list)

    @property
    def muffa_ok(self) -> bool:
        return self.f_rsi > self.f_rsi_max

    @property
    def accumulo_max(self) -> float:
        return max((sum(m.accumulo) for m in self.mesi), default=0.0)

    @property
    def residuo_fine_ciclo(self) -> float:
        return sum(self.mesi[-1].accumulo) if self.mesi else 0.0

    @property
    def interstiziale_ok(self) -> bool:
        """Ammessa condensa che evapora completamente entro il ciclo annuale (ISO 13788).
        Il limite di quantità ammissibile per materiale va verificato a parte."""
        return self.residuo_fine_ciclo <= 1e-9


def _profilo(s: StrutturaOpaca):
    """Ascisse (R cumulata) e (s_d cumulato) alle interfacce, dall'interno all'esterno."""
    r = [s.rsi]
    sd = [0.0]
    nomi = ["superficie interna"]
    for st in s.strati:
        r.append(r[-1] + st.resistenza(s.flusso))
        sd.append(sd[-1] + st.materiale.mu * st.spessore)
        nomi.append(f"dopo {st.materiale.nome}")
    return r, sd, nomi


def _curva(sd, ps, p_i, p_e, forzati):
    """Pressione di vapore alle interfacce: inviluppo convesso inferiore passante per i punti forzati."""
    n = len(sd)
    punti = [(sd[0], p_i)] + [(sd[k], ps[k]) for k in range(1, n - 1)] + [(sd[-1], p_e)]
    obbligati = sorted({0, n - 1} | set(forzati))
    sulla_curva = set()
    for a, b in zip(obbligati, obbligati[1:]):
        hull = [a]
        for k in range(a + 1, b + 1):
            while len(hull) >= 2:
                x1, y1 = punti[hull[-2]]
                x2, y2 = punti[hull[-1]]
                x3, y3 = punti[k]
                if (x2 - x1) * (y3 - y1) - (y2 - y1) * (x3 - x1) <= 0:  # non convesso verso il basso
                    hull.pop()
                else:
                    break
            hull.append(k)
        sulla_curva.update(hull)
    vertici = sorted(sulla_curva)
    p = [0.0] * n
    for a, b in zip(vertici, vertici[1:]):
        (xa, ya), (xb, yb) = punti[a], punti[b]
        for k in range(a, b + 1):
            p[k] = ya if xb == xa else ya + (yb - ya) * (sd[k] - xa) / (xb - xa)
    return p, vertici


def glaser(s: StrutturaOpaca, te: list[float], ur_e: list[float], theta_i: float = 20.0,
           classe_umidita: int = 3) -> EsitoGlaser:
    if not s.strati:
        raise ValueError(f"{s.id}: la verifica di Glaser richiede la stratigrafia")
    r, sd, nomi = _profilo(s)
    r_tot = s.r_totale
    n = len(r)

    # --- muffa / condensa superficiale
    f_rsi = 1 - s.u * RSI_MUFFA
    f_max, critico = -1.0, MESI[0]
    dati_mese = []
    for i in range(12):
        pe = ur_e[i] * p_sat(te[i])
        pi = pe + 1.10 * delta_p(te[i], classe_umidita)
        dati_mese.append((pe, pi))
        if theta_i - te[i] > 0.5:
            th_min = theta_da_p_sat(pi / UR_MUFFA)
            f = (th_min - te[i]) / (theta_i - te[i])
            if f > f_max:
                f_max, critico = f, MESI[i]

    # --- condensa interstiziale
    def mese_calcolo(i, accumulo):
        pe, pi = dati_mese[i]
        theta = [theta_i - (theta_i - te[i]) * rk / r_tot for rk in r]
        ps = [p_sat(t) for t in theta]
        forzati = [k for k in range(1, n - 1) if accumulo[k] > 0]
        p, vertici = _curva(sd, ps, pi, pe, forzati)
        g = [0.0] * n
        secondi = GIORNI_MESE[i] * 86400
        for j, k in enumerate(vertici[1:-1], 1):
            a, b = vertici[j - 1], vertici[j + 1]
            flusso_in = DELTA0 * (p[a] - p[k]) / max(sd[k] - sd[a], 1e-9)
            flusso_out = DELTA0 * (p[k] - p[b]) / max(sd[b] - sd[k], 1e-9)
            if k in forzati or p[k] >= ps[k] - 1e-6:
                g[k] = (flusso_in - flusso_out) * secondi
        return g, pi

    # primo mese con condensa: si parte da lì (ISO 13788, 6.4)
    zero = [0.0] * n
    inizio = None
    for i in range(12):
        g, _ = mese_calcolo(i, zero)
        if any(x > 1e-12 for x in g):
            inizio = i
            break

    esito = EsitoGlaser(f_rsi=f_rsi, f_rsi_max=max(f_max, 0.0), mese_critico=critico,
                        interfacce=nomi)
    if inizio is None:
        for i in range(12):
            esito.mesi.append(MeseGlaser(MESI[i], te[i], ur_e[i], dati_mese[i][1], 0, zero[:], zero[:]))
        return esito

    acc = [0.0] * n
    for step in range(12):
        i = (inizio + step) % 12
        g, pi = mese_calcolo(i, acc)
        variazione = []
        for k in range(n):
            nuovo = max(0.0, acc[k] + g[k])
            variazione.append(nuovo - acc[k])
            acc[k] = nuovo
        esito.mesi.append(MeseGlaser(MESI[i], te[i], ur_e[i], pi, 0, variazione, acc[:]))
    return esito
