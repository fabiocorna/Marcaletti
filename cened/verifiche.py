"""Verifiche dei requisiti minimi (Legge 10/91 - DM 26/06/2015 "requisiti minimi").

Valori in vigore dal 2021 (edifici pubblici dal 2019). In Lombardia i requisiti sono
recepiti dal DDUO 18546/2019 e s.m.i.: prima dell'uso professionale verificare che i
valori coincidano con il testo regionale vigente.

Tipi di intervento:
  "nuova"          nuova costruzione / ristrutturazione importante di 1° livello
                   -> H'_T (tab. 10 App. A) + U dell'edificio di riferimento (App. A)
  "ristr2"         ristrutturazione importante di 2° livello -> H'_T (ultima riga tab. 10)
                   + U limite di App. B
  "riqualificazione" riqualificazione energetica -> U limite di App. B
  "esistente"      solo APE: nessun requisito, verifiche a titolo informativo (App. B)
"""
from dataclasses import dataclass

from .bilancio import Risultati
from .modello import Progetto

ZONE = ("A", "B", "C", "D", "E", "F")


def _per_zona(ab, c, d, e, f):
    return {"A": ab, "B": ab, "C": c, "D": d, "E": e, "F": f}


# DM 26/06/2015 App. B (riqualificazione, dal 2021) [W/m2K]
U_RIQUALIFICAZIONE = {
    "parete": _per_zona(0.40, 0.36, 0.32, 0.28, 0.26),
    "soffitto": _per_zona(0.32, 0.32, 0.26, 0.24, 0.22),
    "pavimento": _per_zona(0.42, 0.38, 0.32, 0.29, 0.28),
    "serramento": _per_zona(3.00, 2.00, 1.80, 1.40, 1.00),
}
# DM 26/06/2015 App. A tab. 1-4: edificio di riferimento (dal 2019/2021)
U_RIFERIMENTO = {
    "parete": _per_zona(0.43, 0.34, 0.29, 0.26, 0.24),
    "soffitto": _per_zona(0.35, 0.33, 0.26, 0.22, 0.20),
    "pavimento": _per_zona(0.44, 0.38, 0.29, 0.26, 0.24),
    "serramento": _per_zona(3.00, 2.20, 1.80, 1.40, 1.10),
}
U_DIVISORI = 0.8  # strutture tra unità immobiliari confinanti (zone climatiche diverse da A-B? v. DM)

# H'_T limite [W/m2K] (DM 26/06/2015 App. A tab. 10)
H_T_LIMITE = [  # (S/V minimo, valori per zona)
    (0.7, _per_zona(0.58, 0.55, 0.53, 0.50, 0.48)),
    (0.4, _per_zona(0.63, 0.60, 0.58, 0.55, 0.53)),
    (0.0, _per_zona(0.80, 0.80, 0.80, 0.75, 0.70)),
]
H_T_LIMITE_RISTR2 = _per_zona(0.73, 0.70, 0.68, 0.65, 0.62)

INTERVENTI = ("nuova", "ristr2", "riqualificazione", "esistente")


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


def h_t_limite(sv: float, zona: str, intervento: str) -> float:
    if intervento == "ristr2":
        return H_T_LIMITE_RISTR2[zona]
    for soglia, valori in H_T_LIMITE:
        if sv >= soglia:
            return valori[zona]
    return H_T_LIMITE[-1][1][zona]


def verifica(prog: Progetto, ris: Risultati, intervento: str = "esistente") -> list[Verifica]:
    if intervento not in INTERVENTI:
        raise ValueError(f"intervento '{intervento}' non valido {INTERVENTI}")
    zona = prog.clima.zona_climatica
    if zona not in ZONE:
        raise ValueError(f"zona climatica '{zona}' non valida")
    tab = U_RIFERIMENTO if intervento == "nuova" else U_RIQUALIFICAZIONE
    rif = "DM 26/06/2015 App. A (edificio di riferimento)" if intervento == "nuova" \
        else "DM 26/06/2015 App. B"
    out = []

    visti = set()
    for d in prog.zona.dispersioni:
        el = d.elemento
        if el.id in visti:
            continue
        visti.add(el.id)
        if d.is_serramento:
            out.append(Verifica(el.nome, "U_w", el.u_w, tab["serramento"][zona], rif))
            continue
        if el.verso == "adiacente":
            out.append(Verifica(el.nome, "U (divisorio tra unità)", el.u,
                                U_DIVISORI if zona not in ("A", "B") else None,
                                "DM 26/06/2015 all. 1 par. 3.3 / 5.2"))
            continue
        chiave = "parete" if el.tipo in ("parete",) else el.tipo
        if chiave == "porta":
            chiave = "serramento"
        # verso ZNC o terreno: il DM ammette il limite con b_tr / U equivalente; qui valore diretto
        out.append(Verifica(el.nome, "U", el.u, tab[chiave][zona], rif))

    s = ris.superficie_disperdente
    v = prog.zona.volume_lordo
    sv = s / v if v else 0.0
    if intervento in ("nuova", "ristr2"):
        out.append(Verifica(f"Edificio (S/V = {sv:.2f})", "H'_T", ris.h_t_medio,
                            h_t_limite(sv, zona, intervento), "DM 26/06/2015 App. A tab. 10"))
    else:
        out.append(Verifica(f"Edificio (S/V = {sv:.2f})", "H'_T", ris.h_t_medio, None,
                            "informativo"))
    return out
