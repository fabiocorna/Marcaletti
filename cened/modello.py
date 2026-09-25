"""Modello dati del progetto: clima, zona termica, dispersioni."""
from dataclasses import dataclass, field

from .involucro import PonteTermico, Serramento, StrutturaOpaca, ZonaNonClimatizzata

MESI = ("gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic")
GIORNI_MESE = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
ESPOSIZIONI = ("S", "SE", "E", "NE", "N", "NO", "O", "SO", "ORIZ")
# azimut CENED/UNI (0 = Sud, positivo verso Ovest)
AZIMUT = {"S": 0, "SO": 45, "O": 90, "NO": 135, "N": 180, "NE": -135, "E": -90, "SE": -45}

# Periodo convenzionale di riscaldamento (D.P.R. 412/93 art. 9) per zona climatica
STAGIONI = {
    "A": ((12, 1), (3, 15)),
    "B": ((12, 1), (3, 31)),
    "C": ((11, 15), (3, 31)),
    "D": ((11, 1), (4, 15)),
    "E": ((10, 15), (4, 15)),
    "F": None,  # nessuna limitazione: mesi con fabbisogno positivo
}


@dataclass
class Clima:
    comune: str
    zona_climatica: str
    te: list[float]  # temperatura media mensile [°C]
    irradianza: dict[str, list[float]]  # esposizione -> irradiazione media giornaliera [MJ/m2]
    gg: float | None = None
    codice_istat: str | None = None
    provincia: str | None = None
    ur: list[float] | None = None  # umidità relativa esterna media mensile [0-1]

    def __post_init__(self):
        if len(self.te) != 12:
            raise ValueError("clima.te: servono 12 temperature mensili")
        if self.ur is not None:
            if len(self.ur) != 12:
                raise ValueError("clima.ur: servono 12 valori mensili")
            self.ur = [u / 100 if u > 1 else u for u in self.ur]  # ammessi anche valori in %
        for k, v in self.irradianza.items():
            if k not in ESPOSIZIONI:
                raise ValueError(f"clima.irradianza: esposizione '{k}' non valida {ESPOSIZIONI}")
            if len(v) != 12:
                raise ValueError(f"clima.irradianza.{k}: servono 12 valori")

    def giorni_riscaldamento(self) -> list[float] | None:
        """Giorni del periodo convenzionale di riscaldamento per ciascun mese."""
        per = STAGIONI.get(self.zona_climatica)
        if per is None:
            return None
        (m1, g1), (m2, g2) = per
        giorni = []
        for m in range(1, 13):
            n = GIORNI_MESE[m - 1]
            if m == m1:
                giorni.append(n - g1 + 1)
            elif m == m2:
                giorni.append(g2)
            elif (m1 > m2 and (m > m1 or m < m2)) or (m1 < m2 and m1 < m < m2):
                giorni.append(n)
            else:
                giorni.append(0)
        return giorni

    def gradi_giorno(self, t_int: float = 20.0) -> float:
        """GG calcolati sul periodo convenzionale (controllo di coerenza con il dato di legge)."""
        g = self.giorni_riscaldamento() or list(GIORNI_MESE)
        return sum(max(0.0, t_int - te) * d for te, d in zip(self.te, g))


@dataclass
class PonteApplicato:
    ponte: PonteTermico
    lunghezza: float


@dataclass
class Dispersione:
    id: str
    nome: str
    elemento: StrutturaOpaca | Serramento
    area: float  # per le opache; per i serramenti = quantita * a_w
    esposizione: str | None = None
    znc: ZonaNonClimatizzata | None = None
    quantita: int = 1
    f_sh_ob: float = 1.0  # fattore di ombreggiatura da ostruzioni/aggetti
    ponti: list[PonteApplicato] = field(default_factory=list)
    perimetro: float | None = None  # perimetro esposto, per pavimenti su terreno (UNI EN ISO 13370)
    spessore_muri: float = 0.30  # spessore dei muri perimetrali w [m] (UNI EN ISO 13370)

    @property
    def u_terreno(self) -> float | None:
        """U equivalente UNI EN ISO 13370 se è un pavimento su terreno con perimetro noto."""
        if self.is_serramento or self.elemento.verso != "terreno" or not self.perimetro:
            return None
        from .terreno import u_pavimento_terreno
        s = self.elemento
        return u_pavimento_terreno(self.area, self.perimetro, self.r_tot_terreno, self.spessore_muri)

    @property
    def r_tot_terreno(self) -> float:
        """R_si + R_f + R_se del pavimento su terreno (R_se = 0,04 per convenzione ISO 13370)."""
        from .terreno import RSE_TERRENO
        s = self.elemento
        return s.r_totale - s.rse + RSE_TERRENO

    @property
    def is_serramento(self) -> bool:
        return isinstance(self.elemento, Serramento)

    @property
    def verso(self) -> str:
        if self.is_serramento:
            return "znc" if self.znc else "esterno"
        return self.elemento.verso


@dataclass
class Zona:
    nome: str
    superficie_utile: float
    volume_lordo: float
    altezza_netta: float
    destinazione: str = "E.1(1)"
    volume_netto: float | None = None
    ricambi_orari: float = 0.5
    temperatura_interna: float = 20.0
    capacita_areica: float | None = None  # kJ/(m2 K) riferita a Su, se imposta
    dispersioni: list[Dispersione] = field(default_factory=list)

    @property
    def v_netto(self) -> float:
        return self.volume_netto or self.superficie_utile * self.altezza_netta


@dataclass
class Progetto:
    nome: str
    clima: Clima
    zona: Zona
    strutture: dict[str, StrutturaOpaca]
    serramenti: dict[str, Serramento]
    ponti: dict[str, PonteTermico]
    znc: dict[str, ZonaNonClimatizzata]
    anagrafica: dict = field(default_factory=dict)
    ipotesi: list[str] = field(default_factory=list)  # registro dei default applicati
    impianto: dict = field(default_factory=dict)  # dati impianto (per ora solo in scheda)
