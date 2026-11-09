#!/usr/bin/env python3
"""Lettore del formato progetto ARCHLine.XP (.pro).

Il .pro e' un archivio ZIP (vedi archline/analisi/02-formato-pro.md). Questo
modulo legge la parte gia' documentata: indice del progetto (layer, gruppi,
viste/disegni), materiali, intestazioni dei disegni binari .asc/.3as e
anteprima. La geometria dentro i .asc non e' ancora decodificata.

Solo libreria standard. Uso da riga di comando:

    python leggi_pro.py progetto.pro                 riepilogo leggibile
    python leggi_pro.py progetto.pro --json          tutto in JSON
    python leggi_pro.py progetto.pro --estrai DIR    estrae le voci in DIR

Uso come libreria:

    from leggi_pro import ProFile
    with ProFile("progetto.pro") as p:
        for layer in p.layers():
            print(layer["Name"])
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import struct
import sys
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath

__all__ = ["ProFile", "Voce", "IntestazioneDisegno", "leggi_xml_tollerante"]

# Le voci hanno come nome il percorso assoluto della cartella temporanea di chi
# ha salvato, es. C:/Users/x/AppData/Roaming/CadLine/ARCHlineXP2026/Temp123/a.pro
# oppure C:/ProgramData/Cadline/ARCHlineXP2016/Temp/a.pro: teniamo cio' che
# segue la cartella Temp.
_RE_TEMP = re.compile(r"(?i)^.*?/archlinexp\d*/temp\d*/")
_RE_TAG_CIFRA = re.compile(r"<(/?)(\d)")
_RE_DICHIARAZIONE = re.compile(r"^\s*<\?xml[^>]*\?>")
_RE_ENCODING = re.compile(rb'encoding="([^"]+)"')
_RE_AMP_NUDA = re.compile(r"&(?!(?:[A-Za-z][\w.-]*|#\d+|#x[0-9A-Fa-f]+);)")
# Riga foglia "<tag attr>testo</tag>": il testo puo' contenere < > non escapati.
_RE_FOGLIA = re.compile(r"(?m)^([ \t]*<([\w.-]+)(?:\s[^<>]*)?>)(.*)(</\2>[ \t]*\r?)$")


def _escapa_foglia(m: re.Match) -> str:
    interno = m.group(3)
    if "<" in interno or ">" in interno:
        interno = interno.replace("<", "&lt;").replace(">", "&gt;")
    return m.group(1) + interno + m.group(4)

# Intestazione dei disegni binari (.asc, .3as): campi a larghezza fissa.
_ASC_CAMPI = {"data": (0, 24), "firma": (34, 44), "piattaforma": (44, 54), "versione": (54, 64)}
_ASC_OFFSET_ID = 108  # uint32: MetFileID della voce <File> nell'indice
_ASC_TIPI = {"CAD_UNO": "2D", "CadLn3D": "3D"}


@dataclass
class Voce:
    """Una voce dell'archivio ZIP."""

    nome_zip: str  # nome originale nello ZIP
    relativo: str  # percorso dopo la cartella Temp
    dimensione: int
    compressa: int
    metodo: int  # 0 = store, 8 = deflate

    @property
    def nome(self) -> str:
        return PurePosixPath(self.relativo).name

    @property
    def estensione(self) -> str:
        return PurePosixPath(self.relativo).suffix.lower()


@dataclass
class IntestazioneDisegno:
    voce: str
    firma: str
    tipo: str  # "2D", "3D" o "?"
    versione: str
    piattaforma: str
    data: str
    file_id: int | None
    estremi: tuple[float, float, float, float] | None  # probabili BLX, BLY, TRX, TRY


def _testo(b: bytes, codifica: str) -> str:
    return b.decode(codifica, errors="replace")


def leggi_xml_tollerante(dati: bytes, codifica: str | None = None) -> ET.Element:
    """Parsa l'XML di ArchLine, che non e' sempre ben formato.

    - Decodifica secondo la dichiarazione (spesso ISO-8859-2, che expat non
      gestisce in modo nativo) e rimuove la dichiarazione.
    - I tag che iniziano con una cifra (es. <3DDatabase>) diventano <_3DDatabase>.
    - Le & non escapate (es. <name>V&B_Chrom1</name>) diventano &amp;.
    - Nelle righe foglia, < e > nel testo (es. <longname><Charcoal></longname>)
      vengono escapati.
    """
    if codifica is None:
        m = _RE_ENCODING.search(dati[:200])
        codifica = m.group(1).decode("ascii") if m else "utf-8"
    testo = _testo(dati, codifica).lstrip("\ufeff")
    testo = _RE_DICHIARAZIONE.sub("", testo, count=1)
    testo = _RE_TAG_CIFRA.sub(r"<\1_\2", testo)
    testo = _RE_FOGLIA.sub(_escapa_foglia, testo)
    testo = _RE_AMP_NUDA.sub("&amp;", testo)
    return ET.fromstring(testo)


def _foglie(e: ET.Element) -> dict[str, str]:
    """Attributi + figli senza figli, come dizionario tag -> testo."""
    d = dict(e.attrib)
    for ch in e:
        if len(ch) == 0 and ch.tag not in d:
            d[ch.tag] = (ch.text or "").strip()
    return d


def _numero(s: str | None):
    if s is None:
        return None
    try:
        return int(s)
    except ValueError:
        try:
            return float(s)
        except ValueError:
            return s


class ProFile:
    """Accesso in sola lettura a un file .pro di ARCHLine.XP."""

    def __init__(self, percorso: str | Path):
        self.percorso = Path(percorso)
        self._zip = zipfile.ZipFile(self.percorso)
        self._indice: ET.Element | None = None
        self.voci: list[Voce] = []
        for info in self._zip.infolist():
            if info.is_dir():
                continue
            rel = _RE_TEMP.sub("", info.filename.replace("\\", "/"))
            self.voci.append(Voce(info.filename, rel, info.file_size, info.compress_size, info.compress_type))

    # -- gestione risorse -------------------------------------------------
    def close(self) -> None:
        self._zip.close()

    def __enter__(self) -> "ProFile":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # -- voci -------------------------------------------------------------
    def leggi(self, voce: Voce) -> bytes:
        return self._zip.read(voce.nome_zip)

    def cerca(self, nome: str) -> list[Voce]:
        """Voci il cui nome finale e' `nome` (senza distinzione di maiuscole)."""
        n = nome.lower()
        return [v for v in self.voci if v.nome.lower() == n]

    def per_estensione(self, *est: str) -> list[Voce]:
        est = tuple(e.lower() for e in est)
        return [v for v in self.voci if v.estensione in est]

    def _prima(self, nome: str) -> Voce | None:
        trovate = self.cerca(nome)
        return trovate[0] if trovate else None

    # -- indice del progetto ----------------------------------------------
    def indice(self) -> ET.Element:
        if self._indice is None:
            v = self._prima("prosavetmp.pro")
            if v is None:
                raise ValueError("indice prosavetmp.pro non trovato: non sembra un .pro di ARCHLine.XP")
            self._indice = leggi_xml_tollerante(self.leggi(v))
        return self._indice

    def info(self) -> dict:
        r = self.indice()
        campi = ("Version", "Type", "Time", "ProjectName", "Project_version", "PaperWidth",
                 "PaperHeight", "_3DDatabase", "_3DDatabaseFile", "NumOfFiles", "TemplateMode")
        d = {k: r.attrib[k] for k in ("MinorVersion", "Build", "ID") if k in r.attrib}
        for c in campi:
            e = r.find(c)
            if e is not None:
                d[c.lstrip("_")] = (e.text or "").strip()
        return d

    def layers(self) -> list[dict]:
        out = []
        for e in self.indice().iterfind("Layers/Layer"):
            d = _foglie(e)
            for k in ("Index", "Colour", "Type", "Thickness", "IsPrintable", "TimeStamp"):
                if k in d:
                    d[k] = _numero(d[k])
            out.append(d)
        return out

    def gruppi_layer(self) -> list[str]:
        return [(e.text or "").strip() for e in self.indice().iterfind("LayerGroups/LayerGroup")]

    def disegni(self) -> list[dict]:
        """Le voci <File> dell'indice: finestre/disegni 2D e viste 3D.

        Ogni disegno e' collegato al suo .asc per nome (campo Path); MetFileID
        esiste solo nelle versioni recenti e coincide con l'ID nell'header .asc.
        """
        intest = {PurePosixPath(h.voce).name.lower(): h for h in self.intestazioni_disegni()}
        out = []
        for e in self.indice().iterfind("File"):
            d = _foglie(e)
            d.pop("Visible_Phases", None)
            d["MetFileID"] = _numero(d.get("MetFileID"))
            d["fasi_visibili"] = [_numero(x.text) for x in e.iterfind("Visible_Phases")]
            d["n_crt"] = len(e.findall("Crt"))
            h = intest.get((d.get("Path") or "").lower())
            d["tipo"] = h.tipo if h else "?"
            d["file_id"] = h.file_id if h else None
            d["estremi"] = h.estremi if h else None
            out.append(d)
        return out

    def impostazioni_globali(self) -> ET.Element | None:
        """GlobalProjectSettings: XML codificato in base64 dentro l'indice."""
        e = self.indice().find("GlobalProjectSettings")
        if e is None or not (e.text or "").strip():
            return None
        try:
            return leggi_xml_tollerante(base64.b64decode(e.text.strip()))
        except (ValueError, ET.ParseError):
            return None

    # -- materiali --------------------------------------------------------
    def materiali(self) -> list[dict]:
        v = self._prima("material.mtr")
        if v is None:
            return []
        r = leggi_xml_tollerante(self.leggi(v))
        out = []
        for m in r.iterfind("material"):
            d = _foglie(m)
            out.append(d)
        return out

    # -- disegni binari ---------------------------------------------------
    def intestazioni_disegni(self) -> list[IntestazioneDisegno]:
        out = []
        for v in self.per_estensione(".asc", ".3as"):
            out.append(self._intestazione(v))
        return out

    def _intestazione(self, v: Voce) -> IntestazioneDisegno:
        with self._zip.open(v.nome_zip) as f:
            h = f.read(160)
        campo = {k: h[a:b].split(b"\0", 1)[0].decode("latin-1").strip() for k, (a, b) in _ASC_CAMPI.items()}
        file_id = estremi = None
        if len(h) >= _ASC_OFFSET_ID + 4 + 8 + 32:
            file_id = struct.unpack_from("<I", h, _ASC_OFFSET_ID)[0]
            if v.estensione == ".asc":
                estremi = struct.unpack_from("<4d", h, _ASC_OFFSET_ID + 12)
            else:
                file_id = None  # nel .3as l'offset 108 ha un altro significato
        return IntestazioneDisegno(
            voce=v.relativo,
            firma=campo["firma"],
            tipo=_ASC_TIPI.get(campo["firma"], "?"),
            versione=campo["versione"],
            piattaforma=campo["piattaforma"],
            data=campo["data"],
            file_id=file_id,
            estremi=estremi,
        )

    # -- anteprima ed estrazione ------------------------------------------
    def anteprima(self) -> bytes | None:
        v = self._prima("Thumbnail.bmp")
        return self.leggi(v) if v else None

    def estrai(self, destinazione: str | Path) -> list[Path]:
        """Estrae le voci con percorsi relativi (senza la cartella Temp).

        I nomi duplicati ricevono un suffisso ~2, ~3, ... I percorsi che
        uscirebbero da `destinazione` vengono rifiutati.
        """
        dest = Path(destinazione).resolve()
        scritti: list[Path] = []
        usati: set[str] = set()
        for v in self.voci:
            rel = PurePosixPath(v.relativo)
            if rel.is_absolute() or ".." in rel.parts or ":" in rel.parts[0]:
                rel = PurePosixPath(rel.name)
            chiave = str(rel).lower()
            n = 2
            while chiave in usati:
                rel = rel.with_name(f"{rel.stem}~{n}{rel.suffix}")
                chiave = str(rel).lower()
                n += 1
            usati.add(chiave)
            p = (dest / rel).resolve()
            if dest not in p.parents:
                raise ValueError(f"percorso non sicuro nell'archivio: {v.nome_zip}")
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(self.leggi(v))
            scritti.append(p)
        return scritti

    # -- riepilogo --------------------------------------------------------
    def come_dict(self) -> dict:
        return {
            "file": str(self.percorso),
            "info": self.info(),
            "gruppi_layer": self.gruppi_layer(),
            "layers": self.layers(),
            "disegni": self.disegni(),
            "intestazioni_disegni": [asdict(h) for h in self.intestazioni_disegni()],
            "materiali": self.materiali(),
            "voci": [asdict(v) for v in self.voci],
        }


def _riepilogo(p: ProFile) -> str:
    righe = [f"# {p.percorso.name}"]
    info = p.info()
    righe.append("Versione formato {Version}  build {Build}  salvato {Time}".format(
        Version=info.get("Version", "?"), Build=info.get("Build", "?"), Time=info.get("Time", "?")))
    righe.append(f"Voci nell'archivio: {len(p.voci)}")

    righe.append("\n## Disegni")
    for d in p.disegni():
        nome = d.get("Pseudo_file_name") or "(senza nome)"
        righe.append(f"- [{d['tipo']}] {nome}  ->  {d.get('Path', '')}  (id {d['file_id']})")
    file3d = info.get("3DDatabaseFile")
    if file3d:
        righe.append(f"- database 3D: {file3d}")

    layers = p.layers()
    righe.append(f"\n## Layer ({len(layers)}), gruppi: {', '.join(p.gruppi_layer())}")
    for l in layers[:15]:
        nascosto = " (nascosto)" if l.get("IsHidden") == "true" else ""
        descr = f" - {l['Description']}" if l.get("Description") else ""
        righe.append(f"- {l.get('NameW') or l.get('Name')}{descr}{nascosto}")
    if len(layers) > 15:
        righe.append(f"- ... altri {len(layers) - 15}")

    mats = p.materiali()
    righe.append(f"\n## Materiali ({len(mats)})")
    for m in mats:
        righe.append(f"- {m.get('longname') or m.get('name')}")

    per_tipo: dict[str, list[int]] = {}
    for v in p.voci:
        per_tipo.setdefault(v.estensione or "(nessuna)", []).append(v.dimensione)
    righe.append("\n## Contenuto per tipo")
    for est, dims in sorted(per_tipo.items(), key=lambda x: -sum(x[1])):
        righe.append(f"- {est}: {len(dims)} file, {sum(dims) / 1024:.0f} KB")
    return "\n".join(righe)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Legge un progetto ARCHLine.XP (.pro).")
    ap.add_argument("pro", type=Path, help="file .pro")
    ap.add_argument("--json", action="store_true", help="stampa tutto in JSON")
    ap.add_argument("--estrai", type=Path, metavar="DIR", help="estrae le voci nella cartella DIR")
    a = ap.parse_args(argv)

    try:
        with ProFile(a.pro) as p:
            if a.estrai:
                n = len(p.estrai(a.estrai))
                print(f"Estratti {n} file in {a.estrai}", file=sys.stderr)
            if a.json:
                json.dump(p.come_dict(), sys.stdout, ensure_ascii=False, indent=2)
                print()
            elif not a.estrai:
                print(_riepilogo(p))
    except zipfile.BadZipFile:
        print(f"{a.pro}: non e' un archivio ZIP, quindi non e' un .pro supportato", file=sys.stderr)
        return 2
    except (ValueError, ET.ParseError) as e:
        print(f"{a.pro}: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
