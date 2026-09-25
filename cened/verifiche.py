"""Verifiche dei requisiti minimi di legge (Legge 10/91).

Lombardia (zone E ed F): DGR 6153 dell'11/05/2026 e Decreto 6437 del 15/05/2026,
"Disposizioni per l'efficienza energetica degli edifici", Allegato B. Per le altre zone
climatiche restano, a titolo indicativo, le tabelle del DM 26/06/2015.

Tipi di intervento:
  "nuova"            nuova costruzione, ampliamenti e recuperi di volume -> H'_T (All. B Tab. 10);
                     U dell'edificio di riferimento (Tab. 1-5) riportate come confronto
  "ristr1"           ristrutturazione importante di 1° livello -> H'_T (Tab. 11, per quota vetrata)
  "ristr2"           ristrutturazione importante di 2° livello -> U limite (Tab. 13-16), da integrare
                     con la U comprensiva dei ponti termici (All. B §3.1 p.2)
  "riqualificazione" riqualificazione energetica -> U in sezione corrente (Tab. 13-16), +30% con
                     isolamento interno o in intercapedine (Disposizioni §8.3)
  "esistente"        solo APE: confronto informativo con i limiti di riqualificazione
Divisori tra unità immobiliari: U <= 0,8 (Tab. 5). Verso ZNC il limite si divide per b_tr (All. B
§3.1 p.5); verso terreno si confronta la U equivalente UNI EN ISO 13370 (p.6).
"""
from dataclasses import dataclass

from .bilancio import Risultati, b_tr
from .modello import Progetto

RIF_2026 = "Decreto Lombardia 6437/2026 All. B"

# ---- Lombardia 2026, Allegato B ----
U_RIFERIMENTO_2026 = {  # Tab. 1-4 (edificio di riferimento)
    "parete": {"E": 0.26, "F": 0.24},
    "copertura": {"E": 0.22, "F": 0.20},
    "pavimento": {"E": 0.26, "F": 0.24},
    "serramento": {"E": 1.40, "F": 1.10},
}
U_LIMITE_2026 = {  # Tab. 13-16 (ristrutturazione di 2° livello e riqualificazione)
    "parete": {"E": 0.28, "F": 0.26},
    "copertura": {"E": 0.24, "F": 0.22},
    "pavimento": {"E": 0.29, "F": 0.28},
    "serramento": {"E": 1.40, "F": 1.10},
}
U_DIVISORI = 0.8  # Tab. 5, tutte le zone
H_T_NUOVA_2026 = [(0.7, {"E": 0.50, "F": 0.48}), (0.4, {"E": 0.55, "F": 0.53}), (0.0, {"E": 0.75, "F": 0.70})]
# Tab. 11: soglie di quota vetrata ex ante e H'_T limite per E ed F
SOGLIE_VETRO = (9, 14, 19, 24, 28, 33, 38, 43, 47, 52, 57, 62, 67, 71, 76, 81, 86, 90, 95, 100)
H_T_RISTR1_2026 = {
    "E": (0.55, 0.55, 0.55, 0.55, 0.58, 0.62, 0.66, 0.70, 0.74, 0.78,
          0.82, 0.85, 0.89, 0.92, 0.95, 0.99, 1.02, 1.04, 1.07, 1.10),
    "F": (0.53, 0.53, 0.53, 0.53, 0.53, 0.53, 0.56, 0.60, 0.63, 0.66,
          0.69, 0.72, 0.75, 0.79, 0.82, 0.85, 0.87, 0.90, 0.93, 0.96),
}
MAGGIORAZIONE_ISOLAMENTO_INTERNO = 1.30  # Disposizioni §8.3

# ---- DM 26/06/2015 (fallback per zone A-D, indicativo) ----
def _per_zona(ab, c, d, e, f):
    return {"A": ab, "B": ab, "C": c, "D": d, "E": e, "F": f}


U_LIMITE_DM2015 = {
    "parete": _per_zona(0.40, 0.36, 0.32, 0.28, 0.26),
    "copertura": _per_zona(0.32, 0.32, 0.26, 0.24, 0.22),
    "pavimento": _per_zona(0.42, 0.38, 0.32, 0.29, 0.28),
    "serramento": _per_zona(3.00, 2.00, 1.80, 1.40, 1.00),
}

INTERVENTI = ("nuova", "ristr1", "ristr2", "riqualificazione", "esistente")


@dataclass
class Verifica:
    oggetto: str
    grandezza: str
    valore: float
    limite: float | None
    riferimento: str

    @property
    def esito(self) -> str:
        if self.limite is None:
            return "n.a."
        return "OK" if self.valore <= self.limite + 1e-9 else "NON VERIFICATA"


def zona_normativa(zona: str) -> str:
    return "F" if zona.upper().startswith("F") else zona.upper()


def h_t_limite_nuova(sv: float, zona: str) -> float:
    for soglia, valori in H_T_NUOVA_2026:
        if sv > soglia:
            return valori[zona]
    return H_T_NUOVA_2026[-1][1][zona]


def h_t_limite_ristr1(quota_vetrata_pct: float, zona: str) -> float:
    for soglia, valore in zip(SOGLIE_VETRO, H_T_RISTR1_2026[zona]):
        if quota_vetrata_pct <= soglia:
            return valore
    return H_T_RISTR1_2026[zona][-1]


def posizione_isolante(s) -> str | None:
    """'esterno', 'interno', 'intercapedine' o None (strati dall'interno all'esterno)."""
    idx = [i for i, st in enumerate(s.strati) if st.materiale.isolante]
    if not idx:
        return None
    pesanti = [i for i, st in enumerate(s.strati)
               if not st.materiale.isolante and not st.intercapedine and st.spessore >= 0.05]
    if not pesanti:
        return "esterno"
    if all(i > max(pesanti) for i in idx):
        return "esterno"
    if all(i < min(pesanti) for i in idx):
        return "interno"
    return "intercapedine"


def _categoria(el) -> str:
    if el.tipo == "soffitto":
        return "copertura"
    if el.tipo == "porta":
        return "serramento"
    return el.tipo


def verifica(prog: Progetto, ris: Risultati, intervento: str = "esistente") -> list[Verifica]:
    if intervento not in INTERVENTI:
        raise ValueError(f"intervento '{intervento}' non valido {INTERVENTI}")
    zona = zona_normativa(prog.clima.zona_climatica)
    lombardia = zona in ("E", "F")
    tab = U_LIMITE_2026 if lombardia else U_LIMITE_DM2015
    if zona not in tab["parete"]:
        raise ValueError(f"zona climatica '{zona}' non valida")
    rif_u = f"{RIF_2026} Tab. 13-16" if lombardia else "DM 26/06/2015 App. B (indicativo)"
    out: list[Verifica] = []

    # ---- trasmittanze dei componenti
    visti = set()
    for d in prog.zona.dispersioni:
        el = d.elemento
        chiave = (el.id, d.znc.id if d.znc else None)
        if chiave in visti:
            continue
        visti.add(chiave)
        if not d.is_serramento and el.verso == "adiacente":
            out.append(Verifica(el.nome, "U (divisorio tra unità)", el.u, U_DIVISORI,
                                f"{RIF_2026} Tab. 5" if lombardia else "DM 26/06/2015"))
            continue
        if not d.is_serramento and el.verso == "interno":
            continue
        cat = "serramento" if d.is_serramento else _categoria(el)
        u = el.u_w if d.is_serramento else (d.u_terreno or el.u)
        grandezza = "U_w" if d.is_serramento else ("U equivalente ISO 13370" if d.u_terreno else "U")
        limite = tab[cat][zona]
        note = []
        if d.znc is not None:  # All. B §3.1 p.5: limite diviso per b_tr
            limite = limite / b_tr(d) if b_tr(d) > 0 else None
            note.append(f"limite / b_tr ({b_tr(d):.2f})")
        if intervento == "riqualificazione" and not d.is_serramento and limite is not None:
            pos = posizione_isolante(el) if el.strati else None
            if pos in ("interno", "intercapedine"):
                limite *= MAGGIORAZIONE_ISOLAMENTO_INTERNO
                note.append(f"+30% isolamento {pos} (§8.3)")
        rif = rif_u + (f" — {', '.join(note)}" if note else "")
        if intervento in ("nuova", "ristr1") and lombardia:
            # per nuove costruzioni e 1° livello le U di Tab. 1-4 definiscono l'edificio di
            # riferimento: sono un confronto, la verifica è su H'_T ed EP
            rif_n = U_RIFERIMENTO_2026[cat][zona]
            if d.znc is not None and b_tr(d) > 0:  # All. B §1.1 p.2
                rif_n /= b_tr(d)
            out.append(Verifica(el.nome, f"{grandezza} (confronto con edificio di riferimento)", u, None,
                                f"{RIF_2026} Tab. 1-4: U_rif = {rif_n:.2f}"))
            continue
        if intervento == "esistente":
            out.append(Verifica(el.nome, grandezza, u, None,
                                f"informativo: limite riqualificazione {limite:.2f}" if limite else "informativo"))
            continue
        out.append(Verifica(el.nome, grandezza, u, limite, rif))

    # ---- H'_T
    area = ris.superficie_disperdente
    sv = area / prog.zona.volume_lordo if prog.zona.volume_lordo else 0.0
    a_vetro = sum(d.area for d in prog.zona.dispersioni if d.is_serramento and b_tr(d) > 0)
    quota_vetro = 100 * a_vetro / area if area else 0.0
    if intervento == "nuova" and lombardia:
        out.append(Verifica(f"Edificio (S/V = {sv:.2f})", "H'_T", ris.h_t_medio,
                            h_t_limite_nuova(sv, zona), f"{RIF_2026} Tab. 10"))
    elif intervento == "ristr1" and lombardia:
        out.append(Verifica(f"Edificio (quota vetrata {quota_vetro:.0f}%)", "H'_T", ris.h_t_medio,
                            h_t_limite_ristr1(quota_vetro, zona),
                            f"{RIF_2026} Tab. 11 (quota vetrata attuale usata come ex ante)"))
    else:
        out.append(Verifica(f"Edificio (S/V = {sv:.2f})", "H'_T", ris.h_t_medio, None, "informativo"))

    if intervento == "ristr2":
        out.append(Verifica("Strutture oggetto di intervento", "U comprensiva dei ponti termici", 0.0, None,
                            f"{RIF_2026} §3.1 p.2 e Tab. 18: da verificare (non ancora calcolata)"))
    if intervento in ("nuova", "ristr1"):
        out.append(Verifica("Componenti finestrati", "A_sol,est / A_sup,utile", 0.0, None,
                            f"{RIF_2026} Tab. 12 (limite 0,030 residenziale): non ancora calcolata"))
    return out
