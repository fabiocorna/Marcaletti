"""Fabbisogno di energia termica utile per riscaldamento Q_H,nd - UNI/TS 11300-1 (mensile).

È un PRE-CALCOLO di controllo: il valore ufficiale dell'APE lo produce il motore
CENED+2.0. Serve a verificare la coerenza dei dati prima dell'import e a confrontare
soluzioni di intervento.
"""
from dataclasses import dataclass, field

from .modello import GIORNI_MESE, MESI, Dispersione, Progetto

B_TERRENO = 0.45  # UNI/TS 11300-1 prospetto 5, pavimento controterra (metodo semplificato)
H_R = 5 * 0.9  # coefficiente di scambio radiativo esterno 5*eps [W/(m2 K)]
DELTA_T_CIELO = 11.0  # differenza media aria esterna - volta celeste [K]
ALFA_SOL = 0.6  # assorbimento solare di default per superfici opache (colore medio)
F_W = 0.9  # rapporto g_gl / g_n (UNI/TS 11300-1)
RHO_C_ARIA = 1200.0  # J/(m3 K)
A0, TAU0 = 1.0, 15.0  # parametri del fattore di utilizzazione (metodo mensile)


def b_tr(d: Dispersione) -> float:
    if d.znc is not None:
        return d.znc.b_tr
    if d.u_terreno is not None:
        return 1.0  # la U equivalente UNI EN ISO 13370 comprende già l'effetto del terreno
    return {"esterno": 1.0, "terreno": B_TERRENO, "adiacente": 0.0, "znc": 1.0}[d.verso]


def apporti_interni(su: float) -> float:
    """Flusso termico interno medio [W] per residenziale (UNI/TS 11300-1, 13.1.1)."""
    if su <= 120:
        return 7.987 * su - 0.0353 * su ** 2
    return 450.0


@dataclass
class RisultatoMese:
    mese: str
    giorni: float
    te: float
    q_tr: float = 0.0  # kWh
    q_ve: float = 0.0
    q_sol: float = 0.0
    q_int: float = 0.0
    gamma: float = 0.0
    eta: float = 0.0
    q_h_nd: float = 0.0


@dataclass
class Risultati:
    h_tr: float  # W/K
    h_ve: float
    h_t_medio: float  # H'_T [W/(m2 K)] riferito alla superficie disperdente
    superficie_disperdente: float
    c_m: float  # capacità termica interna [kJ/K]
    tau: float  # costante di tempo [h]
    phi_int: float  # W
    mesi: list[RisultatoMese] = field(default_factory=list)
    dettaglio_h: list[dict] = field(default_factory=list)

    @property
    def q_h_nd(self) -> float:
        return sum(m.q_h_nd for m in self.mesi)

    def ep_h_nd(self, su: float) -> float:
        return self.q_h_nd / su


def _irradianza(prog: Progetto, d: Dispersione, i: int) -> float:
    """Energia solare incidente nel mese i su 1 m2 [kWh/m2], per giorno."""
    if d.esposizione is None:
        return 0.0
    serie = prog.clima.irradianza.get(d.esposizione)
    if serie is None:
        raise ValueError(f"manca l'irradiazione per l'esposizione {d.esposizione} ({d.nome})")
    return serie[i] / 3.6


def calcola(prog: Progetto) -> Risultati:
    z = prog.zona
    ti = z.temperatura_interna

    h_tr, area_disp, c_m = 0.0, 0.0, 0.0
    dettaglio = []
    for d in z.dispersioni:
        b = b_tr(d)
        e = d.elemento
        u = e.u_w if d.is_serramento else (d.u_terreno or e.u)
        h_el = b * u * d.area
        h_pt = sum(b * p.ponte.psi * p.lunghezza for p in d.ponti)
        h_tr += h_el + h_pt
        if b > 0:
            area_disp += d.area
        if not d.is_serramento:
            c_m += e.k_i * d.area
        dettaglio.append({"nome": d.nome, "verso": d.verso, "b_tr": b, "U": round(u, 3),
                          "A": round(d.area, 2), "H_elemento": round(h_el, 2),
                          "H_ponti": round(h_pt, 2)})

    if z.capacita_areica is not None:
        c_m = z.capacita_areica * z.superficie_utile
    h_ve = RHO_C_ARIA * z.ricambi_orari * z.v_netto / 3600
    tau = c_m * 1000 / 3600 / (h_tr + h_ve)
    a = A0 + tau / TAU0
    phi_int = apporti_interni(z.superficie_utile)

    ris = Risultati(h_tr=h_tr, h_ve=h_ve,
                    h_t_medio=h_tr / area_disp if area_disp else 0.0,
                    superficie_disperdente=area_disp, c_m=c_m, tau=tau, phi_int=phi_int,
                    dettaglio_h=dettaglio)

    giorni_stagione = prog.clima.giorni_riscaldamento()
    for i, mese in enumerate(MESI):
        te = prog.clima.te[i]
        giorni = giorni_stagione[i] if giorni_stagione else GIORNI_MESE[i]
        m = RisultatoMese(mese, giorni, te)
        if giorni == 0:
            ris.mesi.append(m)
            continue
        t_h = giorni * 24  # ore
        dt = ti - te

        q_r = 0.0  # extra flusso verso la volta celeste
        q_sol = 0.0
        for d in z.dispersioni:
            if d.verso != "esterno":
                continue
            e = d.elemento
            orizz = d.esposizione == "ORIZ"
            f_r = 1.0 if orizz else 0.5
            if d.is_serramento:
                u, rse = e.u_w, 0.04
                q_sol += d.f_sh_ob * F_W * e.g_n * (1 - e.frazione_telaio) * d.area \
                    * _irradianza(prog, d, i) * giorni
            else:
                u, rse = e.u, e.rse
                q_sol += d.f_sh_ob * ALFA_SOL * rse * u * d.area * _irradianza(prog, d, i) * giorni
            q_r += f_r * rse * u * d.area * H_R * DELTA_T_CIELO * t_h / 1000

        m.q_tr = h_tr * dt * t_h / 1000 + q_r
        m.q_ve = h_ve * dt * t_h / 1000
        m.q_sol = q_sol
        m.q_int = phi_int * t_h / 1000
        q_ht = m.q_tr + m.q_ve
        q_gn = m.q_sol + m.q_int
        if q_ht <= 0:
            m.gamma, m.eta, m.q_h_nd = float("inf"), 0.0, 0.0
        else:
            g = q_gn / q_ht
            m.gamma = g
            m.eta = a / (a + 1) if abs(g - 1) < 1e-9 else (1 - g ** a) / (1 - g ** (a + 1))
            m.q_h_nd = max(0.0, q_ht - m.eta * q_gn)
        ris.mesi.append(m)
    return ris
