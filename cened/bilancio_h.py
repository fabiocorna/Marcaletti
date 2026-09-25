"""Fabbisogno di energia termica utile per riscaldamento secondo l'Allegato H del Decreto
Lombardia 6437/2026 (metodo mensile, condizione di riferimento), il metodo del motore CENED+2.0.

Differenze rispetto a `bilancio.py` (UNI/TS 11300-1 semplificata):
- apporti solari sulle opache sottratti dalle perdite (3.5), non moltiplicati per η;
- extra flusso verso il cielo con T_sky dalla pressione di vapore (3.32)-(3.37);
- ventilazione di riferimento 0,5·0,6 vol/h del volume netto, ρc = 1210 J/m³K (3.45)-(3.46);
- correzione angolare F_gl mensile per orientamento (Prosp. 3.XXIX);
- ombre F_S mensili per componente; stagione calcolata con γ_lim (1.1) e troncata al Prospetto I.
Riferimenti: docs/ALLEGATO_H_SPEC.md.
"""
import math
from dataclasses import dataclass, field

GIORNI = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
RHO_C = 1210.0
H_E = 25.0
SIGMA = 5.67e-8
ALFA_COLORE = {1: 0.3, 2: 0.6, 3: 0.9}
CAMPI_FRAZIONE = ("te", "hb", "hd")  # grandezze ricalcolate nelle frazioni di mese [AMB-1]
PERIODO_MAX = {"E": ((10, 15), (4, 15)), "F": ((10, 5), (4, 22))}
# Prospetto 3.XXIX: F_gl per vetro doppio (S, E/O, N, orizzontale), gennaio..dicembre
F_GL_DOPPIO = {
    "S": (0.978, 0.950, 0.897, 0.833, 0.787, 0.770, 0.766, 0.797, 0.865, 0.933, 0.971, 0.982),
    "EO": (0.861, 0.890, 0.904, 0.912, 0.916, 0.915, 0.915, 0.915, 0.907, 0.894, 0.876, 0.862),
    "N": (0.901, 0.901, 0.901, 0.890, 0.854, 0.831, 0.831, 0.870, 0.899, 0.900, 0.901, 0.901),
    "O": (0.812, 0.851, 0.895, 0.923, 0.933, 0.934, 0.935, 0.928, 0.909, 0.865, 0.818, 0.789),
}
F_GL_SINGOLO = {
    "S": (0.984, 0.967, 0.933, 0.888, 0.852, 0.838, 0.835, 0.861, 0.911, 0.957, 0.981, 0.987),
    "EO": (0.902, 0.923, 0.932, 0.938, 0.941, 0.941, 0.941, 0.940, 0.935, 0.925, 0.912, 0.903),
    "N": (0.932, 0.932, 0.931, 0.921, 0.895, 0.877, 0.877, 0.905, 0.930, 0.931, 0.931, 0.932),
    "O": (0.876, 0.902, 0.931, 0.949, 0.955, 0.955, 0.956, 0.952, 0.940, 0.912, 0.880, 0.858),
}
F_GL_TRIPLO = {
    "S": (0.972, 0.937, 0.872, 0.796, 0.747, 0.731, 0.724, 0.756, 0.833, 0.915, 0.964, 0.977),
    "EO": (0.833, 0.868, 0.884, 0.894, 0.898, 0.898, 0.898, 0.898, 0.888, 0.872, 0.851, 0.834),
    "N": (0.880, 0.880, 0.879, 0.868, 0.828, 0.802, 0.801, 0.846, 0.877, 0.878, 0.879, 0.880),
    "O": (0.770, 0.817, 0.871, 0.906, 0.918, 0.920, 0.921, 0.912, 0.887, 0.833, 0.776, 0.744),
}


# Prospetto 3.XXVIII: f_shd (frazione di tempo con schermatura mobile attiva), gen..dic
F_SHD = {"N": (0,) * 12,
         "E": (0.52, 0.48, 0.66, 0.71, 0.71, 0.75, 0.74, 0.75, 0.73, 0.72, 0.62, 0.50),
         "S": (0.81, 0.82, 0.81, 0.74, 0.62, 0.56, 0.62, 0.76, 0.82, 0.86, 0.84, 0.86),
         "O": (0.39, 0.55, 0.63, 0.62, 0.64, 0.68, 0.73, 0.72, 0.67, 0.60, 0.30, 0.42)}
# Prospetto 3.XXX: f_b (quota diretta sulla globale, Lombardia); "H" = orizzontale
F_B = {"S": (0.75, 0.70, 0.65, 0.55, 0.40, 0.35, 0.45, 0.50, 0.65, 0.75, 0.75, 0.75),
       "E": (0.50, 0.50, 0.55, 0.55, 0.55, 0.55, 0.60, 0.60, 0.60, 0.55, 0.50, 0.50),
       "N": (0, 0, 0, 0.10, 0.25, 0.30, 0.35, 0.15, 0, 0, 0, 0),
       "H": (0.40, 0.50, 0.55, 0.60, 0.60, 0.65, 0.70, 0.65, 0.60, 0.55, 0.45, 0.40)}
F_B["O"] = F_B["E"]


def _per_azimut(tab, gamma: float, mese: int) -> float:
    """Interpolazione lineare fra N (180), E (−90), S (0), O (+90)."""
    g = ((gamma + 180) % 360) - 180
    punti = [(-180, "N"), (-90, "E"), (0, "S"), (90, "O"), (180, "N")]
    for (g0, k0), (g1, k1) in zip(punti, punti[1:]):
        if g0 <= g <= g1:
            t = (g - g0) / (g1 - g0)
            return tab[k0][mese] + (tab[k1][mese] - tab[k0][mese]) * t
    return tab["S"][mese]


def f_sh_gl(c, mese: int) -> float:
    """F_(sh+gl) (3.65)-(3.66): schermature mobili pesate con f_shd, correzione angolare F_gl."""
    fgl = f_gl(c.vetri, c.beta, c.gamma, mese)
    if c.g_sh_b is None or c.g_n <= 0:
        return fgl
    orizz = c.beta < 45
    fshd = 0.0 if orizz else _per_azimut(F_SHD, c.gamma, mese)
    fb = F_B["H"][mese] if orizz else _per_azimut(F_B, c.gamma, mese)
    f_sh = (fb * c.g_sh_b + (1 - fb) * c.g_sh_d) / c.g_n
    return fshd * f_sh + (1 - fshd) * fgl


def f_gl(vetri: int, beta: float, gamma: float, mese: int) -> float:
    """Correzione angolare: interpolazione lineare sull'azimut tra S, E/O e N; 'O' = orizzontale."""
    tab = {1: F_GL_SINGOLO, 3: F_GL_TRIPLO}.get(vetri, F_GL_DOPPIO)
    if beta < 45:
        return tab["O"][mese]
    g = abs(((gamma + 180) % 360) - 180)  # 0 = Sud, 90 = E/O, 180 = Nord
    if g <= 90:
        return tab["S"][mese] + (tab["EO"][mese] - tab["S"][mese]) * g / 90
    return tab["EO"][mese] + (tab["N"][mese] - tab["EO"][mese]) * (g - 90) / 90


@dataclass
class Componente:
    nome: str
    area: float  # m² (A_L)
    u: float  # W/m²K
    b: float = 1.0  # (θi − θa)/(θi − θe); 0 per ambienti climatizzati
    esterno: bool = False  # scambia radiazione con l'esterno (sole, cielo)
    trasparente: bool = False
    beta: float = 90.0
    gamma: float = 0.0
    alfa: float = 0.6  # assorbimento solare (opache)
    g_n: float = 0.0  # trasparenti
    frazione_telaio: float = 0.2
    vetri: int = 2
    f_s: list[float] | None = None  # fattore d'ombra mensile (1 se assente)
    f_s_d: float = 1.0  # ombra sulla componente diffusa (per F_r)
    g_sh_b: float | None = None  # g con schermatura mobile, componente diretta
    g_sh_d: float | None = None  # g con schermatura mobile, componente diffusa
    psi_l: float = 0.0  # Σ ψ·L associati [W/K], moltiplicati per b


@dataclass
class ClimaH:
    te: list[float]
    hb: list[float]  # kWh/m² giorno, orizzontale
    hd: list[float]
    pv: list[float]  # Pa
    lat: float
    zona: str = "E"


@dataclass
class ZonaH:
    superficie_utile: float
    volume_netto: float
    capacita: float  # C [kJ/K]
    componenti: list[Componente] = field(default_factory=list)
    theta_i: float = 20.0
    ricambi: float = 0.5 * 0.6


@dataclass
class MeseH:
    mese: int
    giorni: float = 0.0
    q_t: float = 0.0
    q_v: float = 0.0
    q_se_o: float = 0.0
    q_si: float = 0.0
    q_i: float = 0.0
    gamma: float = 0.0
    a: float = 0.0
    eta: float = 0.0
    q_nh: float = 0.0


@dataclass
class RisultatoH:
    h_t: float
    h_v: float
    mesi: list[MeseH]
    inizio: tuple[int, int] | None
    fine: tuple[int, int] | None

    @property
    def q_nh(self) -> float:
        return sum(m.q_nh for m in self.mesi)


def apporti_interni(su: float) -> float:
    return 7.987 * su - 0.0353 * su ** 2 if su <= 120 else 450.0


def _mese(z: ZonaH, c: ClimaH, m: int, giorni: float, h_t: float, h_v: float, irr) -> MeseH:
    r = MeseH(m, giorni)
    dt = giorni * 24 / 1000  # kh
    dth = z.theta_i - c.te[m]
    t_sky = 291 - 51.6 * math.exp(-c.pv[m] / 1000)
    t_e = c.te[m] + 273.15
    h_r = SIGMA * (t_sky ** 4 - t_e ** 4) / (t_sky - t_e)
    d_er = t_e - t_sky
    extra = 0.0
    for k, comp in enumerate(z.componenti):
        if not comp.esterno:
            continue
        fs = comp.f_s[m] if comp.f_s else 1.0
        h_s = irr[k][m]
        eps = 0.837 if comp.trasparente else 0.9
        f_r = comp.f_s_d * (1 + math.cos(math.radians(comp.beta))) / 2
        extra += f_r * comp.u / H_E * comp.area * eps * h_r * d_er
        if comp.trasparente:
            r.q_si += giorni * h_s * comp.area * (1 - comp.frazione_telaio) * fs \
                * f_sh_gl(comp, m) * comp.g_n
        else:
            r.q_se_o += giorni * h_s * comp.area * fs * comp.alfa * comp.u / H_E
    r.q_t = h_t * dth * dt + extra * dt
    r.q_v = h_v * dth * dt
    r.q_i = apporti_interni(z.superficie_utile) * dt
    q_l_net = r.q_t + r.q_v - r.q_se_o
    q_g = r.q_i + r.q_si
    h_l = (r.q_t + r.q_v) / (dt * dth) if dt and dth else h_t + h_v
    tau = z.capacita / (3.6 * h_l)
    r.a = 1 + tau / 15
    if q_l_net <= 0:
        r.gamma, r.eta, r.q_nh = float("inf"), 0.0, 0.0
        return r
    r.gamma = q_g / q_l_net
    g, a = r.gamma, r.a
    r.eta = a / (a + 1) if abs(g - 1) < 1e-9 else (1 - g ** a) / (1 - g ** (a + 1))
    r.q_nh = max(0.0, q_l_net - r.eta * q_g)
    return r


def _giorno_anno(mese: int, giorno: float) -> float:
    return sum(GIORNI[:mese]) + giorno


def calcola_h(z: ZonaH, c: ClimaH) -> RisultatoH:
    from .clima_lombardia import irradiazione
    h_t = sum(k.b * (k.u * k.area + k.psi_l) for k in z.componenti)
    h_v = RHO_C * z.ricambi * z.volume_netto / 3600
    irr = [irradiazione(c.lat, c.hb, c.hd, k.beta, k.gamma) if k.esterno else None for k in z.componenti]
    pieni = [_mese(z, c, m, GIORNI[m], h_t, h_v, irr) for m in range(12)]

    # stagione (1.1): giorni con γ_day < γ_lim = (a+1)/a, con γ e a interpolati linearmente fra
    # i valori mensili attribuiti al giorno centrale di ogni mese
    centri = [_giorno_anno(m, GIORNI[m] / 2) for m in range(12)]

    def interp(valori, giorno):
        for m in range(12):
            x0, x1 = centri[m], centri[(m + 1) % 12] + (365 if m == 11 else 0)
            g = giorno + 365 if giorno < centri[0] else giorno
            if x0 <= g <= x1:
                return valori[m] + (valori[(m + 1) % 12] - valori[m]) * (g - x0) / (x1 - x0)
        return valori[0]

    gam = [p.gamma if not math.isinf(p.gamma) else 1e9 for p in pieni]
    aa = [p.a for p in pieni]

    def serve(giorno: float) -> bool:
        a = interp(aa, giorno)
        return interp(gam, giorno) < (a + 1) / a

    (mi, gi), (mf, gf) = PERIODO_MAX.get(c.zona, PERIODO_MAX["E"])
    giorni_mese = [0.0] * 12
    giorni_attivi = [[] for _ in range(12)]
    inizio = fine = None
    for giorno in range(1, 366):
        m = next(i for i in range(12) if giorno <= _giorno_anno(i, GIORNI[i]))
        g_mese = giorno - _giorno_anno(m, 0)
        in_periodo = (m + 1 > mi or (m + 1 == mi and g_mese >= gi)) or \
                     (m + 1 < mf or (m + 1 == mf and g_mese <= gf))
        if in_periodo and serve(giorno - 0.5):
            giorni_mese[m] += 1
            giorni_attivi[m].append(giorno - 0.5)
    mesi = []
    for m in range(12):
        if giorni_mese[m] == 0:
            mesi.append(MeseH(m))
        elif giorni_mese[m] == GIORNI[m]:
            mesi.append(pieni[m])
        else:
            # frazione di mese: dati climatici ricalcolati come media dei valori giornalieri,
            # interpolati linearmente fra i giorni centrali dei mesi, sui soli giorni di calcolo
            giorni = giorni_attivi[m]
            cm = ClimaH(te=list(c.te), hb=list(c.hb), hd=list(c.hd), pv=list(c.pv), lat=c.lat, zona=c.zona)
            for nome in CAMPI_FRAZIONE:
                serie = getattr(c, nome)
                getattr(cm, nome)[m] = sum(interp(serie, g) for g in giorni) / len(giorni)
            irr_m = [irradiazione(cm.lat, cm.hb, cm.hd, k.beta, k.gamma) if k.esterno else None
                     for k in z.componenti]
            mesi.append(_mese(z, cm, m, giorni_mese[m], h_t, h_v, irr_m))
    attivi = [m for m in range(12) if giorni_mese[m]]
    if attivi:
        inizio, fine = (attivi[0], giorni_mese[attivi[0]]), (attivi[-1], giorni_mese[attivi[-1]])
    return RisultatoH(h_t=h_t, h_v=h_v, mesi=mesi, inizio=inizio, fine=fine)
