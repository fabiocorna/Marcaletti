"""Prezzari: importazione (Excel, CSV, XML SIX), libreria locale e ricerca delle voci.

I prezzari regionali si distribuiscono di solito in Excel o in XML «SIX» (Standard di
Interscambio). Spesso le righe senza prezzo sono titoli di gruppo («01.A01 Scavi») e le
voci con prezzo ne riportano solo la parte finale: in questo caso la descrizione completa
si ricostruisce concatenando i titoli dei gruppi che precedono la voce.
"""
from __future__ import annotations

import csv
import json
import os
import re
import unicodedata
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from decimal import Decimal

from .numeri import ZERO, to_decimal


@dataclass
class VocePrezzario:
    codice: str
    descrizione: str
    um: str = ""
    prezzo: Decimal = ZERO
    manodopera_pct: Decimal = ZERO
    sicurezza: bool = False


@dataclass
class Prezzario:
    nome: str
    fonte: str = ""                    # file di origine
    voci: list[VocePrezzario] = field(default_factory=list)
    _index: list[tuple[str, VocePrezzario]] | None = field(default=None, repr=False, compare=False)

    # ---------------------------------------------------------------- salvataggio
    def to_dict(self) -> dict:
        return {"formato": "CRN Prezzario", "nome": self.nome, "fonte": self.fonte,
                "voci": [{k: (str(v) if isinstance(v, Decimal) else v) for k, v in asdict(x).items()}
                         for x in self.voci]}

    @classmethod
    def from_dict(cls, d: dict) -> "Prezzario":
        voci = [VocePrezzario(codice=v["codice"], descrizione=v.get("descrizione", ""), um=v.get("um", ""),
                              prezzo=to_decimal(v.get("prezzo", "0")),
                              manodopera_pct=to_decimal(v.get("manodopera_pct", "0")),
                              sicurezza=bool(v.get("sicurezza", False)))
                for v in d.get("voci", [])]
        return cls(nome=d.get("nome", "Prezzario"), fonte=d.get("fonte", ""), voci=voci)

    # -------------------------------------------------------------------- ricerca
    def get(self, codice: str) -> VocePrezzario | None:
        c = codice.strip().lower()
        return next((v for v in self.voci if v.codice.lower() == c), None)

    def search(self, query: str, limit: int = 50) -> list[VocePrezzario]:
        """Tutte le parole devono comparire (nel codice o nella descrizione).

        Le parole si confrontano senza accenti e senza distinguere maiuscole; una parola
        di almeno 5 lettere trova anche le varianti (es. «intonaco» → «intonaci»).
        """
        words = [w for w in _norm(query).split() if w]
        if not words:
            return self.voci[:limit]
        if self._index is None:
            self._index = [(_norm(v.codice + " " + v.descrizione), v) for v in self.voci]
        patterns = [w[:-1] if len(w) >= 5 else w for w in words]
        scored = []
        for text, v in self._index:
            if all(p in text for p in patterns):
                code = v.codice.lower()
                score = (0 if any(code.startswith(w) for w in words) else 1,
                         -sum(text.count(w) for w in words), len(v.descrizione))
                scored.append((score, v))
        scored.sort(key=lambda t: t[0])
        return [v for _, v in scored[:limit]]


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^\w.]+", " ", s)


# ---------------------------------------------------------------- importazione
_HEADERS = {
    "codice": ("codice", "cod.", "cod", "tariffa", "articolo", "n. tariffa", "num. tariffa", "voce"),
    "descrizione": ("descrizione", "descr", "designazione", "denominazione", "declaratoria"),
    "um": ("u.m.", "u.m", "um", "unita", "unità", "unità di misura", "unita di misura", "u. m."),
    "prezzo": ("prezzo", "prezzo unitario", "importo", "euro", "€", "prezzo €", "valore"),
    "manodopera": ("manodopera", "mdo", "% mdo", "incidenza manodopera", "% manodopera", "inc. mdo",
                   "incidenza mdo"),
    "sicurezza": ("sicurezza", "oneri sicurezza", "os"),
}


def _match_header(cell: str) -> str | None:
    c = " ".join(_norm(str(cell or "")).replace(".", ". ").split()).replace(". ", ".").strip()
    raw = str(cell or "").strip().lower()
    for key, names in _HEADERS.items():
        for n in names:
            nn = _norm(n).strip()
            if c == nn or raw == n:
                return key
    for key, names in (("manodopera", _HEADERS["manodopera"]), ("descrizione", _HEADERS["descrizione"]),
                       ("prezzo", ("prezzo",)), ("codice", ("codice", "tariffa"))):
        if any(_norm(n).strip() in c for n in names):
            return key
    return None


def _find_columns(rows: list[list]) -> tuple[int, dict[str, int]]:
    for r, row in enumerate(rows[:40]):
        cols: dict[str, int] = {}
        for i, cell in enumerate(row):
            key = _match_header(cell) if cell not in (None, "") else None
            if key and key not in cols:
                cols[key] = i
        if {"codice", "descrizione", "prezzo"} <= cols.keys():
            return r, cols
    raise ValueError("Non trovo le colonne del prezzario. Servono almeno le intestazioni "
                     "«Codice», «Descrizione» e «Prezzo» (facoltative «U.M.» e «Manodopera»).")


def _num(v) -> Decimal | None:
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return Decimal(str(round(v, 6)))
    s = str(v).strip().replace("%", "")
    if not re.search(r"\d", s):
        return None
    try:
        return to_decimal(s)
    except ValueError:
        return None


def rows_to_prezzario(rows: list[list], nome: str, fonte: str = "") -> Prezzario:
    start, cols = _find_columns(rows)
    voci: list[VocePrezzario] = []
    groups: list[tuple[str, str]] = []   # titoli di gruppo (righe senza prezzo)

    def cell(row, key):
        i = cols.get(key)
        return row[i] if i is not None and i < len(row) else None

    for row in rows[start + 1:]:
        codice = str(cell(row, "codice") or "").strip()
        desc = " ".join(str(cell(row, "descrizione") or "").split())
        prezzo = _num(cell(row, "prezzo"))
        if not codice and not desc:
            continue
        if prezzo is None:
            if codice:
                while groups and not codice.startswith(groups[-1][0]):
                    groups.pop()
                groups.append((codice, desc))
            elif voci and desc:            # descrizione che continua sulla riga successiva
                voci[-1].descrizione += " " + desc
            continue
        if not codice:
            continue
        while groups and not codice.startswith(groups[-1][0]):
            groups.pop()
        parts = [g[1] for g in groups if g[1] and g[1] not in desc]
        full = " – ".join(parts + [desc]) if parts else desc
        mdo = _num(cell(row, "manodopera")) or ZERO
        if Decimal(0) < mdo <= 1 and "manodopera" in cols:   # 0,35 → 35%
            mdo *= 100
        sic = str(cell(row, "sicurezza") or "").strip().lower() in ("si", "sì", "x", "1", "s", "true")
        voci.append(VocePrezzario(codice=codice, descrizione=full, um=str(cell(row, "um") or "").strip(),
                                  prezzo=prezzo, manodopera_pct=mdo, sicurezza=sic))
    if not voci:
        raise ValueError("Nessuna voce con prezzo trovata nel file.")
    return Prezzario(nome=nome, fonte=fonte, voci=voci)


def load_csv(path: str, nome: str | None = None) -> Prezzario:
    with open(path, "rb") as f:
        raw = f.read()
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    try:
        dialect = csv.Sniffer().sniff(text[:5000], delimiters=";,\t|")
    except csv.Error:
        dialect = csv.excel
        dialect.delimiter = ";"
    rows = list(csv.reader(text.splitlines(), dialect))
    return rows_to_prezzario(rows, nome or _stem(path), path)


def load_xlsx(path: str, nome: str | None = None) -> Prezzario:
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    errors = []
    try:
        for ws in wb.worksheets:
            rows = [list(r) for r in ws.iter_rows(values_only=True)]
            try:
                return rows_to_prezzario(rows, nome or _stem(path), path)
            except ValueError as exc:
                errors.append(f"{ws.title}: {exc}")
    finally:
        wb.close()
    raise ValueError("Nessun foglio contiene un prezzario riconoscibile.\n" + "\n".join(errors))


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].split(":")[-1]


def _attr(el, *names) -> str:
    low = {_local(k).lower(): v for k, v in el.attrib.items()}
    for n in names:
        v = low.get(n.lower())
        if v not in (None, ""):
            return v.strip()
    return ""


def _descr(el) -> str:
    for ch in el:
        if "descrizione" in _local(ch.tag).lower():
            d = _attr(ch, "estesa", "breve", "testo") or (ch.text or "").strip()
            if d:
                return " ".join(d.split())
    return " ".join(_attr(el, "descrizione", "estesa", "breve").split())


def load_six(path: str, nome: str | None = None) -> Prezzario:
    """Prezzario XML nel formato SIX (o simile): elementi ``prodotto`` con descrizione,
    unità di misura e quotazione."""
    root = ET.parse(path).getroot()
    udm: dict[str, str] = {}
    gruppi: dict[str, str] = {}
    titolo = ""
    for el in root.iter():
        name = _local(el.tag).lower()
        if name == "unitadimisura":
            uid = _attr(el, "unitaDiMisuraId", "id")
            udm[uid] = _attr(el, "simbolo", "udmSimbolo") or _descr(el)
        elif name == "gruppo":
            g = _attr(el, "grpValore", "valore", "codice", "grpId")
            if g:
                gruppi[g] = _descr(el)
        elif name in ("intestazione", "prezzario") and not titolo:
            titolo = _attr(el, "titolo", "descrizione", "nome")
    voci = []
    for el in root.iter():
        if _local(el.tag).lower() != "prodotto":
            continue
        codice = _attr(el, "voce", "voceCode", "codice", "prdCodice", "prdId")
        desc = _descr(el)
        um = udm.get(_attr(el, "unitaDiMisuraId"), "") or _attr(el, "um", "unitaDiMisura")
        prezzo = None
        mdo = _num(_attr(el, "incidenzaManodopera", "percentualeManodopera", "manodopera"))
        sic = _attr(el, "sicurezza", "oneriSicurezza").lower() in ("true", "1", "si", "sì")
        parents = []
        for ch in el:
            n = _local(ch.tag).lower()
            if "quotazione" in n and prezzo is None:
                prezzo = _num(_attr(ch, "valore", "prezzo", "importo") or ch.text)
            elif "manodopera" in n and mdo is None:
                mdo = _num(_attr(ch, "valore", "percentuale") or ch.text)
            elif n in ("prdgrpvalore", "grpvalore", "gruppo") and (g := _attr(ch, "grpValore", "valore")):
                if gruppi.get(g):
                    parents.append(gruppi[g])
        if prezzo is None:
            prezzo = _num(_attr(el, "prezzo", "valore", "importo"))
        if not codice or prezzo is None:
            continue
        parts = [p for p in parents if p and p not in desc]
        voci.append(VocePrezzario(codice=codice, descrizione=" – ".join(parts + [desc]) if parts else desc,
                                  um=um, prezzo=prezzo, manodopera_pct=mdo or ZERO, sicurezza=sic))
    if not voci:
        raise ValueError("Il file XML non contiene voci di prezzario riconoscibili (elementi «prodotto»).")
    return Prezzario(nome=nome or titolo or _stem(path), fonte=path, voci=voci)


def load_any(path: str, nome: str | None = None) -> Prezzario:
    ext = os.path.splitext(path)[1].lower()
    if ext in (".xlsx", ".xlsm"):
        return load_xlsx(path, nome)
    if ext in (".csv", ".txt"):
        return load_csv(path, nome)
    if ext == ".xml":
        return load_six(path, nome)
    if ext == ".json":
        with open(path, encoding="utf-8") as f:
            return Prezzario.from_dict(json.load(f))
    if ext == ".xls":
        raise ValueError("Il formato .xls (Excel 97-2003) non è supportato: aprilo in Excel e salvalo come .xlsx.")
    raise ValueError(f"Formato non supportato: {ext}")


def _stem(path: str) -> str:
    return os.path.splitext(os.path.basename(path))[0]


# ------------------------------------------------------------------- libreria
class Libreria:
    """Prezzari importati, salvati come JSON nella cartella dati dell'utente."""

    def __init__(self, folder: str):
        self.folder = folder
        os.makedirs(folder, exist_ok=True)
        self._cache: dict[str, Prezzario] = {}

    def _file(self, nome: str) -> str:
        safe = re.sub(r"[^\w\- ]+", "_", nome).strip() or "prezzario"
        return os.path.join(self.folder, safe + ".json")

    def nomi(self) -> list[str]:
        out = []
        for f in sorted(os.listdir(self.folder)):
            if f.endswith(".json"):
                try:
                    with open(os.path.join(self.folder, f), encoding="utf-8") as fh:
                        head = fh.read(400)
                    m = re.search(r'"nome":\s*"((?:[^"\\]|\\.)*)"', head)
                    out.append(json.loads(f'"{m.group(1)}"') if m else f[:-5])
                except OSError:
                    continue
        return out

    def add(self, prezzario: Prezzario) -> None:
        with open(self._file(prezzario.nome), "w", encoding="utf-8") as f:
            json.dump(prezzario.to_dict(), f, ensure_ascii=False)
        self._cache[prezzario.nome] = prezzario

    def get(self, nome: str) -> Prezzario:
        if nome not in self._cache:
            with open(self._file(nome), encoding="utf-8") as f:
                self._cache[nome] = Prezzario.from_dict(json.load(f))
        return self._cache[nome]

    def remove(self, nome: str) -> None:
        self._cache.pop(nome, None)
        try:
            os.remove(self._file(nome))
        except FileNotFoundError:
            pass

    def tutti(self) -> list[Prezzario]:
        out = []
        for n in self.nomi():
            try:
                out.append(self.get(n))
            except (OSError, ValueError, KeyError):
                continue
        return out
