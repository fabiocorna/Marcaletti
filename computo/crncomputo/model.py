"""Modello del progetto: dati generali, elenco prezzi, capitoli, voci e misure, quadro economico.

Il progetto si salva in un file JSON (estensione ``.crcm``). Ogni modifica passa da
``ProgettoDoc`` e si può annullare (Ctrl+Z) e ripetere (Ctrl+Y).
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from decimal import Decimal

from .numeri import ZERO, FormulaError, evaluate, round2, to_decimal

FILE_VERSION = 1
FILE_EXT = ".crcm"
MAX_UNDO = 200


# --------------------------------------------------------------------------- dati
@dataclass
class Misura:
    """Riga di misura: quantità = parti uguali × lunghezza × larghezza × altezza/peso.

    I campi vuoti non contano. Ogni campo accetta un'espressione («2*(3,5+4)»).
    Le deduzioni (vuoti, aperture…) hanno segno negativo.
    """
    descrizione: str = ""
    parti: str = ""
    lunghezza: str = ""
    larghezza: str = ""
    altezza: str = ""
    deduzione: bool = False

    FIELDS = ("parti", "lunghezza", "larghezza", "altezza")

    def fattori(self) -> list[Decimal | None]:
        return [evaluate(getattr(self, f)) for f in self.FIELDS]

    def quantita(self) -> Decimal:
        values = [v for v in self.fattori() if v is not None]
        if not values:
            return ZERO
        q = Decimal(1)
        for v in values:
            q *= v
        return -abs(q) if self.deduzione else q

    def quantita_sicura(self) -> tuple[Decimal, str | None]:
        try:
            return self.quantita(), None
        except FormulaError as exc:
            return ZERO, str(exc)


@dataclass
class Articolo:
    """Voce dell'elenco prezzi del progetto."""
    codice: str
    descrizione: str
    um: str = ""
    prezzo: Decimal = ZERO
    manodopera_pct: Decimal = ZERO     # incidenza della manodopera
    sicurezza: bool = False            # onere della sicurezza (non soggetto a ribasso)
    fonte: str = ""                    # prezzario di provenienza o «Nuovo prezzo»

    @property
    def descrizione_breve(self) -> str:
        d = " ".join(self.descrizione.split())
        return d if len(d) <= 90 else d[:87].rstrip() + "…"


@dataclass
class Capitolo:
    id: int
    titolo: str
    codice: str = ""
    parent: int | None = None


@dataclass
class Voce:
    id: int
    capitolo: int | None
    articolo: str                      # codice dell'articolo nell'elenco prezzi
    misure: list[Misura] = field(default_factory=list)
    nota: str = ""

    def quantita(self) -> Decimal:
        return round2(sum((m.quantita_sicura()[0] for m in self.misure), ZERO))

    def errori(self) -> list[str]:
        return [e for m in self.misure if (e := m.quantita_sicura()[1])]


@dataclass
class SommaDisposizione:
    descrizione: str
    modo: str = "importo"              # "importo" oppure "percentuale" (dei lavori)
    valore: Decimal = ZERO
    iva_pct: Decimal = ZERO


@dataclass
class QuadroEconomico:
    sicurezza_modo: str = "voci"       # "voci" | "percentuale" | "importo"
    sicurezza_valore: Decimal = ZERO   # % dei lavori o importo, secondo il modo
    ribasso_pct: Decimal = ZERO
    iva_lavori_pct: Decimal = Decimal("10")
    somme: list[SommaDisposizione] = field(default_factory=list)


@dataclass
class DatiGenerali:
    titolo: str = "Nuovo computo"
    committente: str = ""
    comune: str = ""
    indirizzo: str = ""
    progettista: str = ""
    impresa: str = ""
    data: str = ""
    prezzario: str = ""
    note: str = ""


DATI_LABELS = {
    "titolo": "Oggetto dei lavori", "committente": "Committente", "comune": "Comune",
    "indirizzo": "Indirizzo", "progettista": "Progettista", "impresa": "Impresa",
    "data": "Data", "prezzario": "Prezzario di riferimento", "note": "Note",
}


@dataclass
class Progetto:
    dati: DatiGenerali = field(default_factory=DatiGenerali)
    articoli: dict[str, Articolo] = field(default_factory=dict)
    capitoli: list[Capitolo] = field(default_factory=list)
    voci: list[Voce] = field(default_factory=list)
    quadro: QuadroEconomico = field(default_factory=QuadroEconomico)
    next_id: int = 1

    # ------------------------------------------------------------ serializzazione
    def to_dict(self) -> dict:
        def conv(obj):
            if isinstance(obj, Decimal):
                return str(obj)
            if isinstance(obj, dict):
                return {k: conv(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [conv(v) for v in obj]
            return obj
        return {"formato": "CRN Computo", "versione": FILE_VERSION,
                "dati": asdict(self.dati),
                "articoli": [conv(asdict(a)) for a in self.articoli.values()],
                "capitoli": [asdict(c) for c in self.capitoli],
                "voci": [conv(asdict(v)) for v in self.voci],
                "quadro": conv(asdict(self.quadro)),
                "next_id": self.next_id}

    @classmethod
    def from_dict(cls, d: dict) -> "Progetto":
        if d.get("formato") != "CRN Computo":
            raise ValueError("Il file non è un progetto di CRN Computo.")
        if int(d.get("versione", 1)) > FILE_VERSION:
            raise ValueError("Il progetto è stato creato con una versione più recente del programma.")
        dec = lambda v: to_decimal(v)  # noqa: E731
        p = cls()
        p.dati = DatiGenerali(**{k: v for k, v in d.get("dati", {}).items() if k in DatiGenerali.__annotations__})
        for a in d.get("articoli", []):
            art = Articolo(codice=a["codice"], descrizione=a.get("descrizione", ""), um=a.get("um", ""),
                           prezzo=dec(a.get("prezzo", "0")), manodopera_pct=dec(a.get("manodopera_pct", "0")),
                           sicurezza=bool(a.get("sicurezza", False)), fonte=a.get("fonte", ""))
            p.articoli[art.codice] = art
        p.capitoli = [Capitolo(id=c["id"], titolo=c["titolo"], codice=c.get("codice", ""), parent=c.get("parent"))
                      for c in d.get("capitoli", [])]
        for v in d.get("voci", []):
            misure = [Misura(**{k: m.get(k, "" if k != "deduzione" else False)
                                for k in ("descrizione", "parti", "lunghezza", "larghezza", "altezza", "deduzione")})
                      for m in v.get("misure", [])]
            p.voci.append(Voce(id=v["id"], capitolo=v.get("capitolo"), articolo=v["articolo"], misure=misure,
                               nota=v.get("nota", "")))
        q = d.get("quadro", {})
        p.quadro = QuadroEconomico(
            sicurezza_modo=q.get("sicurezza_modo", "voci"), sicurezza_valore=dec(q.get("sicurezza_valore", "0")),
            ribasso_pct=dec(q.get("ribasso_pct", "0")), iva_lavori_pct=dec(q.get("iva_lavori_pct", "10")),
            somme=[SommaDisposizione(descrizione=s["descrizione"], modo=s.get("modo", "importo"),
                                     valore=dec(s.get("valore", "0")), iva_pct=dec(s.get("iva_pct", "0")))
                   for s in q.get("somme", [])])
        ids = [c.id for c in p.capitoli] + [v.id for v in p.voci]
        p.next_id = max([int(d.get("next_id", 1))] + [i + 1 for i in ids])
        return p

    # ------------------------------------------------------------------ ricerca
    def new_id(self) -> int:
        i = self.next_id
        self.next_id += 1
        return i

    def capitolo(self, cid: int | None) -> Capitolo | None:
        return next((c for c in self.capitoli if c.id == cid), None)

    def voce(self, vid: int) -> Voce | None:
        return next((v for v in self.voci if v.id == vid), None)

    def figli(self, parent: int | None) -> list[Capitolo]:
        return [c for c in self.capitoli if c.parent == parent]

    def discendenti(self, cid: int) -> list[int]:
        out = [cid]
        for c in self.figli(cid):
            out += self.discendenti(c.id)
        return out

    def capitoli_ordinati(self) -> list[tuple[Capitolo, int]]:
        """Capitoli in ordine di albero, con il livello (0 = principale)."""
        out: list[tuple[Capitolo, int]] = []

        def walk(parent, level):
            for c in self.figli(parent):
                out.append((c, level))
                walk(c.id, level + 1)
        walk(None, 0)
        return out

    def voci_ordinate(self) -> list[Voce]:
        """Voci nell'ordine del computo: prima quelle senza capitolo, poi per capitolo."""
        order = {None: -1} | {c.id: i for i, (c, _) in enumerate(self.capitoli_ordinati())}
        pos = {v.id: i for i, v in enumerate(self.voci)}
        return sorted(self.voci, key=lambda v: (order.get(v.capitolo, len(order)), pos[v.id]))

    def numeri(self) -> dict[int, int]:
        """Numero progressivo di ogni voce (id → N.)."""
        return {v.id: i for i, v in enumerate(self.voci_ordinate(), 1)}

    def numero(self, voce: Voce) -> int:
        return self.numeri()[voce.id]

    def voce_per_numero(self, n: int) -> Voce:
        voci = self.voci_ordinate()
        if not 1 <= n <= len(voci):
            raise ValueError(f"la voce n. {n} non esiste (il computo ha {len(voci)} voci)")
        return voci[n - 1]

    def articoli_usati(self) -> list[Articolo]:
        used = {v.articolo for v in self.voci}
        return [a for a in self.articoli.values() if a.codice in used]

    # ------------------------------------------------------------------ importi
    def prezzo(self, voce: Voce) -> Decimal:
        a = self.articoli.get(voce.articolo)
        return a.prezzo if a else ZERO

    def importo(self, voce: Voce) -> Decimal:
        return round2(voce.quantita() * self.prezzo(voce))

    def totale_capitolo(self, cid: int) -> Decimal:
        ids = set(self.discendenti(cid))
        return sum((self.importo(v) for v in self.voci if v.capitolo in ids), ZERO)

    def totale_voci(self) -> Decimal:
        return sum((self.importo(v) for v in self.voci), ZERO)

    def totale_manodopera(self) -> Decimal:
        tot = ZERO
        for v in self.voci:
            a = self.articoli.get(v.articolo)
            if a and a.manodopera_pct:
                tot += self.importo(v) * a.manodopera_pct / 100
        return round2(tot)

    def quadro_economico(self) -> dict:
        q = self.quadro
        totale = self.totale_voci()
        sic_voci = sum((self.importo(v) for v in self.voci
                        if (a := self.articoli.get(v.articolo)) and a.sicurezza), ZERO)
        soggetti = totale - sic_voci
        if q.sicurezza_modo == "percentuale":
            sicurezza = sic_voci + round2(soggetti * q.sicurezza_valore / 100)
        elif q.sicurezza_modo == "importo":
            sicurezza = sic_voci + round2(q.sicurezza_valore)
        else:
            sicurezza = sic_voci
        lavori = soggetti + sicurezza
        ribasso = round2(soggetti * q.ribasso_pct / 100)
        righe_b = []
        iva_lavori = round2(lavori * q.iva_lavori_pct / 100)
        if q.iva_lavori_pct:
            righe_b.append({"descrizione": f"IVA sui lavori ({_pct(q.iva_lavori_pct)})", "importo": iva_lavori})
        for s in q.somme:
            base = round2(lavori * s.valore / 100) if s.modo == "percentuale" else round2(s.valore)
            righe_b.append({"descrizione": s.descrizione + (f" ({_pct(s.valore)} dei lavori)"
                                                            if s.modo == "percentuale" else ""),
                            "importo": base})
            if s.iva_pct:
                righe_b.append({"descrizione": f"IVA su «{s.descrizione}» ({_pct(s.iva_pct)})",
                                "importo": round2(base * s.iva_pct / 100)})
        somme = sum((r["importo"] for r in righe_b), ZERO)
        return {"lavori_soggetti_ribasso": soggetti, "oneri_sicurezza": sicurezza, "totale_lavori": lavori,
                "ribasso": ribasso, "importo_contrattuale": lavori - ribasso, "somme_disposizione": righe_b,
                "totale_somme": somme, "totale_generale": lavori + somme,
                "manodopera": self.totale_manodopera()}


def _pct(v: Decimal) -> str:
    from .numeri import fmt_pct
    return fmt_pct(v)


# ------------------------------------------------------------------- documento
class ProgettoDoc:
    """Progetto aperto: percorso del file, modifiche non salvate, annulla/ripeti."""

    def __init__(self, progetto: Progetto | None = None, path: str | None = None):
        self.p = progetto or Progetto()
        self.path = path
        self.modified = False
        self._undo: list[tuple[str, str]] = []
        self._redo: list[tuple[str, str]] = []
        self._group: list | None = None

    # ------------------------------------------------------------------- file
    @classmethod
    def open(cls, path: str) -> "ProgettoDoc":
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return cls(Progetto.from_dict(data), path)

    def save(self, path: str | None = None) -> None:
        path = path or self.path
        if not path:
            raise ValueError("percorso del file mancante")
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.p.to_dict(), f, ensure_ascii=False, indent=1)
        import os
        os.replace(tmp, path)
        self.path = path
        self.modified = False

    @property
    def title(self) -> str:
        import os
        return os.path.basename(self.path) if self.path else (self.p.dati.titolo or "Senza titolo")

    # ---------------------------------------------------------- annulla/ripeti
    def _snapshot(self) -> str:
        return json.dumps(self.p.to_dict(), ensure_ascii=False)

    def begin_group(self, label: str) -> None:
        """Le modifiche fino a ``end_group`` si annullano insieme, con un solo Ctrl+Z."""
        self._group = [label, False]

    def end_group(self) -> None:
        self._group = None

    def checkpoint(self, label: str) -> None:
        """Da chiamare prima di ogni modifica."""
        group = self._group
        if group is not None:
            if group[1]:
                self._redo.clear()
                self.modified = True
                return
            group[1] = True
            label = group[0]
        self._undo.append((label, self._snapshot()))
        del self._undo[:-MAX_UNDO]
        self._redo.clear()
        self.modified = True

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    def undo_label(self) -> str:
        return self._undo[-1][0] if self._undo else ""

    def redo_label(self) -> str:
        return self._redo[-1][0] if self._redo else ""

    def undo(self) -> None:
        label, state = self._undo.pop()
        self._redo.append((label, self._snapshot()))
        self.p = Progetto.from_dict(json.loads(state))
        self.modified = True

    def redo(self) -> None:
        label, state = self._redo.pop()
        self._undo.append((label, self._snapshot()))
        self.p = Progetto.from_dict(json.loads(state))
        self.modified = True

    # --------------------------------------------------------------- modifiche
    def set_dato(self, campo: str, valore: str) -> None:
        if campo not in DatiGenerali.__annotations__:
            raise ValueError(f"campo sconosciuto: {campo}")
        self.checkpoint(f"Modifica {DATI_LABELS.get(campo, campo).lower()}")
        setattr(self.p.dati, campo, valore)

    def add_capitolo(self, titolo: str, parent: int | None = None, codice: str = "") -> Capitolo:
        if parent is not None and self.p.capitolo(parent) is None:
            raise ValueError("capitolo padre inesistente")
        self.checkpoint("Nuovo capitolo")
        c = Capitolo(id=self.p.new_id(), titolo=titolo.strip() or "Capitolo", codice=codice, parent=parent)
        self.p.capitoli.append(c)
        return c

    def update_capitolo(self, cid: int, titolo: str | None = None, codice: str | None = None) -> None:
        c = self.p.capitolo(cid)
        if c is None:
            raise ValueError("capitolo inesistente")
        self.checkpoint("Modifica capitolo")
        if titolo is not None:
            c.titolo = titolo
        if codice is not None:
            c.codice = codice

    def delete_capitolo(self, cid: int) -> int:
        """Elimina il capitolo, i sottocapitoli e le loro voci. Ritorna le voci eliminate."""
        ids = set(self.p.discendenti(cid))
        self.checkpoint("Elimina capitolo")
        n = sum(1 for v in self.p.voci if v.capitolo in ids)
        self.p.voci = [v for v in self.p.voci if v.capitolo not in ids]
        self.p.capitoli = [c for c in self.p.capitoli if c.id not in ids]
        return n

    def move_capitolo(self, cid: int, delta: int) -> None:
        c = self.p.capitolo(cid)
        sib = self.p.figli(c.parent)
        i = sib.index(c)
        j = i + delta
        if not 0 <= j < len(sib):
            return
        self.checkpoint("Sposta capitolo")
        a, b = self.p.capitoli.index(sib[i]), self.p.capitoli.index(sib[j])
        self.p.capitoli[a], self.p.capitoli[b] = self.p.capitoli[b], self.p.capitoli[a]

    def set_articolo(self, art: Articolo, label: str = "Elenco prezzi") -> None:
        """Aggiunge o aggiorna un articolo dell'elenco prezzi."""
        if not art.codice.strip():
            raise ValueError("il codice dell'articolo è obbligatorio")
        self.checkpoint(label)
        self.p.articoli[art.codice] = art

    def rename_articolo(self, old: str, new: str) -> None:
        if new in self.p.articoli and new != old:
            raise ValueError(f"il codice {new} esiste già")
        self.checkpoint("Rinomina articolo")
        art = self.p.articoli.pop(old)
        art.codice = new
        self.p.articoli[new] = art
        for v in self.p.voci:
            if v.articolo == old:
                v.articolo = new

    def delete_articolo(self, codice: str) -> None:
        if any(v.articolo == codice for v in self.p.voci):
            raise ValueError("l'articolo è usato nel computo: elimina prima le voci che lo usano")
        self.checkpoint("Elimina articolo")
        del self.p.articoli[codice]

    def add_voce(self, articolo: str, capitolo: int | None, misure: list[Misura] | None = None,
                 after: int | None = None, nota: str = "") -> Voce:
        if articolo not in self.p.articoli:
            raise ValueError(f"l'articolo {articolo} non è nell'elenco prezzi")
        if capitolo is not None and self.p.capitolo(capitolo) is None:
            raise ValueError("capitolo inesistente")
        self.checkpoint("Nuova voce")
        v = Voce(id=self.p.new_id(), capitolo=capitolo, articolo=articolo, misure=list(misure or []), nota=nota)
        idx = next((i + 1 for i, x in enumerate(self.p.voci) if x.id == after), len(self.p.voci))
        self.p.voci.insert(idx, v)
        return v

    def delete_voci(self, ids: list[int]) -> None:
        self.checkpoint("Elimina voci" if len(ids) > 1 else "Elimina voce")
        s = set(ids)
        self.p.voci = [v for v in self.p.voci if v.id not in s]

    def duplicate_voce(self, vid: int) -> Voce:
        v = self.p.voce(vid)
        return self.add_voce(v.articolo, v.capitolo, [Misura(**asdict(m)) for m in v.misure], after=vid, nota=v.nota)

    def move_voce(self, vid: int, delta: int) -> None:
        v = self.p.voce(vid)
        same = [x for x in self.p.voci if x.capitolo == v.capitolo]
        i = same.index(v)
        j = i + delta
        if not 0 <= j < len(same):
            return
        self.checkpoint("Sposta voce")
        a, b = self.p.voci.index(same[i]), self.p.voci.index(same[j])
        self.p.voci[a], self.p.voci[b] = self.p.voci[b], self.p.voci[a]

    def set_voce_capitolo(self, vid: int, capitolo: int | None) -> None:
        self.checkpoint("Sposta voce in altro capitolo")
        self.p.voce(vid).capitolo = capitolo

    def set_voce_articolo(self, vid: int, articolo: str) -> None:
        if articolo not in self.p.articoli:
            raise ValueError(f"l'articolo {articolo} non è nell'elenco prezzi")
        self.checkpoint("Cambia articolo della voce")
        self.p.voce(vid).articolo = articolo

    def set_voce_nota(self, vid: int, nota: str) -> None:
        self.checkpoint("Nota della voce")
        self.p.voce(vid).nota = nota

    def add_misure(self, vid: int, misure: list[Misura], index: int | None = None) -> None:
        v = self.p.voce(vid)
        for m in misure:
            for f in Misura.FIELDS:   # le formule errate si segnalano subito
                evaluate(getattr(m, f))
        self.checkpoint("Nuova misura" if len(misure) == 1 else "Nuove misure")
        pos = len(v.misure) if index is None else max(0, min(index, len(v.misure)))
        v.misure[pos:pos] = misure

    def update_misura(self, vid: int, index: int, **values) -> None:
        v = self.p.voce(vid)
        if not 0 <= index < len(v.misure):
            raise ValueError(f"la riga di misura {index + 1} non esiste")
        m = v.misure[index]
        for k, val in values.items():
            if k not in ("descrizione", "deduzione") + Misura.FIELDS:
                raise ValueError(f"campo sconosciuto: {k}")
            if k in Misura.FIELDS:
                evaluate(val)
        self.checkpoint("Modifica misura")
        for k, val in values.items():
            setattr(m, k, val)

    def delete_misure(self, vid: int, indexes: list[int]) -> None:
        v = self.p.voce(vid)
        self.checkpoint("Elimina misure" if len(indexes) > 1 else "Elimina misura")
        s = set(indexes)
        v.misure = [m for i, m in enumerate(v.misure) if i not in s]

    def set_quadro(self, **values) -> None:
        self.checkpoint("Quadro economico")
        for k, val in values.items():
            if k not in QuadroEconomico.__annotations__ or k == "somme":
                raise ValueError(f"campo sconosciuto: {k}")
            setattr(self.p.quadro, k, to_decimal(val) if k != "sicurezza_modo" else val)

    def set_somme(self, somme: list[SommaDisposizione]) -> None:
        self.checkpoint("Somme a disposizione")
        self.p.quadro.somme = somme
