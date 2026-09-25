"""Componenti dell'involucro: strutture opache, serramenti, ponti termici.

Norme applicate:
- UNI EN ISO 6946: resistenze superficiali, intercapedini, trasmittanza U.
- UNI EN ISO 13786 (metodo semplificato, app. A): capacità termica areica interna k_i.
- UNI EN ISO 10077-1: trasmittanza del serramento U_w.
"""
from dataclasses import dataclass, field

from .materiali import LIBRERIA, Materiale, r_intercapedine

TIPI_STRUTTURA = ("parete", "pavimento", "soffitto", "porta")
VERSI = ("esterno", "znc", "terreno", "adiacente")

# Resistenze superficiali (UNI EN ISO 6946, prospetto 7) [m2 K/W]
RSI = {"orizzontale": 0.13, "ascendente": 0.10, "discendente": 0.17}
RSE = 0.04


def direzione_flusso(tipo: str) -> str:
    """Direzione del flusso in inverno: soffitto -> ascendente, pavimento -> discendente."""
    return {"soffitto": "ascendente", "pavimento": "discendente"}.get(tipo, "orizzontale")


@dataclass
class Strato:
    materiale: Materiale
    spessore: float  # m
    intercapedine: bool = False

    def resistenza(self, flusso: str) -> float:
        if self.intercapedine:
            return r_intercapedine(self.spessore, flusso)
        m = self.materiale
        if m.r is not None:
            return m.r
        return self.spessore / m.lambda_

    @property
    def capacita_areica(self) -> float:
        """rho * c * d [J/(m2 K)]"""
        return 0.0 if self.intercapedine else self.materiale.rho * self.materiale.c * self.spessore


ARIA = Materiale("Intercapedine d'aria", lambda_=None, rho=1.2, c=1000, mu=1.0)


@dataclass
class StrutturaOpaca:
    """Strati elencati dall'INTERNO verso l'ESTERNO."""
    id: str
    nome: str
    tipo: str
    verso: str
    strati: list[Strato] = field(default_factory=list)
    u_imposta: float | None = None
    k_i_imposta: float | None = None  # kJ/(m2 K)
    extra: dict = field(default_factory=dict)  # attributi CENED aggiuntivi (codici)

    def __post_init__(self):
        if self.tipo not in TIPI_STRUTTURA:
            raise ValueError(f"{self.id}: tipo '{self.tipo}' non valido ({TIPI_STRUTTURA})")
        if self.verso not in VERSI:
            raise ValueError(f"{self.id}: verso '{self.verso}' non valido ({VERSI})")
        if not self.strati and self.u_imposta is None:
            raise ValueError(f"{self.id}: servono gli strati oppure 'u'")

    @property
    def flusso(self) -> str:
        return direzione_flusso(self.tipo)

    @property
    def rsi(self) -> float:
        return RSI[self.flusso]

    @property
    def rse(self) -> float:
        # verso ambienti interni (ZNC, altra unità) la superficie esterna è "interna";
        # verso terreno si calcola la sola struttura (il terreno lo tratta la UNI EN ISO 13370)
        if self.verso in ("znc", "adiacente"):
            return RSI[self.flusso]
        if self.verso == "terreno":
            return 0.0
        return RSE

    @property
    def spessore(self) -> float:
        return sum(s.spessore for s in self.strati)

    @property
    def r_totale(self) -> float:
        return self.rsi + sum(s.resistenza(self.flusso) for s in self.strati) + self.rse

    @property
    def u(self) -> float:
        if self.u_imposta is not None:
            return self.u_imposta
        return 1.0 / self.r_totale

    @property
    def massa_superficiale(self) -> float:
        """Massa superficiale [kg/m2] di tutti gli strati."""
        return sum(s.materiale.rho * s.spessore for s in self.strati if not s.intercapedine)

    @property
    def k_i(self) -> float:
        """Capacità termica areica interna [kJ/(m2 K)] - UNI EN ISO 13786 app. A.

        Si sommano rho*c*d dal lato interno fino al minore tra: 10 cm, metà dello
        spessore totale, primo strato isolante.
        """
        if self.k_i_imposta is not None:
            return self.k_i_imposta
        if not self.strati:
            return 0.0
        limite = min(0.10, self.spessore / 2)
        tot, prof = 0.0, 0.0
        for s in self.strati:
            if s.materiale.isolante:
                break
            d = min(s.spessore, limite - prof)
            if d <= 0:
                break
            if not s.intercapedine:
                tot += s.materiale.rho * s.materiale.c * d
            prof += d
        return tot / 1000


# Valori tipici per serramenti (UNI EN ISO 10077-1, UNI/TS 11300-1) - indicativi
VETRI = {
    "singolo": {"u_g": 5.7, "g_n": 0.85},
    "doppio": {"u_g": 2.8, "g_n": 0.75},
    "doppio_basso_emissivo": {"u_g": 1.1, "g_n": 0.60},
    "triplo_basso_emissivo": {"u_g": 0.7, "g_n": 0.50},
}
TELAI = {
    "legno": {"u_f": 1.8, "psi_g": 0.06},
    "pvc": {"u_f": 1.3, "psi_g": 0.06},
    "metallo": {"u_f": 5.9, "psi_g": 0.00},
    "metallo_taglio_termico": {"u_f": 2.8, "psi_g": 0.08},
}


@dataclass
class Serramento:
    id: str
    nome: str
    larghezza: float  # m (luce architettonica)
    altezza: float
    u_g: float
    u_f: float
    g_n: float
    psi_g: float = 0.06
    frazione_telaio: float = 0.25  # A_f / A_w
    u_w_imposta: float | None = None
    extra: dict = field(default_factory=dict)

    @property
    def a_w(self) -> float:
        return self.larghezza * self.altezza

    @property
    def a_f(self) -> float:
        return self.a_w * self.frazione_telaio

    @property
    def a_g(self) -> float:
        return self.a_w - self.a_f

    @property
    def l_g(self) -> float:
        """Perimetro del vetro, stimato su un vetro unico con telaio di bordo uniforme."""
        b = self._larghezza_telaio()
        return 2 * ((self.larghezza - 2 * b) + (self.altezza - 2 * b))

    def _larghezza_telaio(self) -> float:
        # risolve (L-2b)(H-2b) = A_g
        l, h, ag = self.larghezza, self.altezza, self.a_g
        # 4b^2 - 2(L+H)b + (LH - Ag) = 0
        disc = (2 * (l + h)) ** 2 - 16 * (l * h - ag)
        return (2 * (l + h) - disc ** 0.5) / 8

    @property
    def u_w(self) -> float:
        if self.u_w_imposta is not None:
            return self.u_w_imposta
        return (self.a_g * self.u_g + self.a_f * self.u_f + self.l_g * self.psi_g) / self.a_w


@dataclass
class PonteTermico:
    id: str
    nome: str
    psi: float  # W/(m K), riferito alle dimensioni esterne
    extra: dict = field(default_factory=dict)


@dataclass
class ZonaNonClimatizzata:
    id: str
    nome: str
    b_tr: float  # fattore di correzione UNI/TS 11300-1
    extra: dict = field(default_factory=dict)
