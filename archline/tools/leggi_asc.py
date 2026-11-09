#!/usr/bin/env python3
"""Lettore dei disegni binari di ARCHLine.XP (.asc) con esportazione DXF.

Formato documentato in archline/analisi/03-formato-asc.md. Decodifica la
grafica 2D di base (linee, polilinee, archi, cerchi/ellissi) e i testi; gli
altri tipi (quote, retini, blocchi) vengono elencati ma non convertiti.
I layer vengono dal campo 8 (-(Index+1) dei Layers del .pro).

Solo libreria standard. Uso:

    python leggi_asc.py progetto.pro                     disegni ed entita' per tipo
    python leggi_asc.py progetto.pro --dxf out.dxf       esporta la pianta 2D principale
    python leggi_asc.py progetto.pro --disegno BAR.asc --dxf bar.dxf
    python leggi_asc.py disegno.asc --dxf out.dxf        anche su un .asc gia' estratto
"""

from __future__ import annotations

import argparse
import math
import struct
import sys
import zlib
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

__all__ = ["Entita", "Testo", "Disegno", "Layer", "leggi_disegno", "scrivi_dxf", "layers_da_pro"]

# --- struttura del file ---------------------------------------------------
# [header fisso] [XML <HeaderExt>] [frame...] [anteprima BMP] [frame <Footer>]
# frame = u32 n, poi n byte: u32 lunghezza_decompressa + stream zlib.
# Ordine dei frame osservato nei disegni 2D:
#   0 tabelle (penne/stili), 1 tipi linea, 2 ENTITA', 3 dizionario proprieta',
#   4 blocchi/simboli (se presenti), ultimo <Footer> XML.
FRAME_ENTITA = 2

# Record entita': 16 tag fissi (u16 tag + valore), tag opzionali fino a 0xFFFF,
# poi t11 coppie (u32, u32) di proprieta', poi t13 byte di geometria.
_TAG_FISSI = (2, 2, 2, 4, 4, 4, 4, 4, 2, 2, 2, 2, 4, 4, 4, 16)
_TAG_OPZIONALI = {0x10: 16, 0x11: 16, 0x25: 4, 0x2B: 1}
# Formato vecchio (versione disegno < 10, es. 5.06): stessi campi 0..14 senza
# tag, senza GUID e senza tag opzionali.
_VERSIONE_CON_TAG = 10.0
_FINE_TAG = 0xFFFF

TIPI = {
    2: "linea",
    3: "polilinea",
    4: "?4",
    5: "arco",
    6: "ellisse",
    9: "testo",
    10: "quota",  # sempre sul layer delle quote (verificato su 2016-2025); geometria da decodificare
    11: "retino",  # sempre sul layer dei retini/campiture; geometria da decodificare
    14: "blocco",
}


# Codifica dei testi: segue la lingua di Windows con cui e' stato salvato il file
# (cp1252 per i progetti italiani: a', e', °, ² verificati).
CODIFICA_TESTI = "cp1252"


@dataclass
class Testo:
    """Testo (tipo 9). Angoli in gradi antiorari, misure in unita' del disegno."""

    x: float
    y: float
    altezza: float
    rotazione: float
    allineamento: int  # 1..9: (a-1)//3 = 0 sinistra, 1 centro, 2 destra; (a-1)%3 = 0 basso, 1 centro, 2 alto
    interlinea: float  # distanza tra le linee di base di due righe consecutive
    righe: list[str]


@dataclass
class Entita:
    offset: int
    tipo: int
    id: int
    campi: dict[int, int]  # tag fissi 0..14 come interi
    guid: bytes  # tag 15
    opzionali: dict[int, bytes]
    proprieta: list[tuple[int, int]]
    geometria: bytes

    @property
    def layer(self) -> int:
        """Indice del layer (= `Index` dei `Layers` nell'indice del .pro).

        Il campo 8 vale -(Index + 1): verificato su progetti 2016, 2020, 2025
        (testi su "Testi", quote su "Quote", retini su "Retini", muri su "Murature").
        """
        return -self.campi[8] - 1

    @property
    def nome_tipo(self) -> str:
        return TIPI.get(self.tipo, f"?{self.tipo}")

    def segmenti_o_primitive(self):
        """Restituisce una primitiva geometrica, o None se il tipo non e' decodificato.

        ("linee", [(x, y), ...])             linea o polilinea aperta
        ("arco", cx, cy, r, inizio, ampiezza) angoli in gradi, antiorario
        ("ellisse", cx, cy, rx, ry, rotazione)
        """
        g = self.geometria
        try:
            if self.tipo in (2, 3):
                n = (len(g) - 16) // 16
                return ("linee", [struct.unpack_from("<2d", g, 16 + 16 * k) for k in range(n)])
            if self.tipo == 5:
                return ("arco", *struct.unpack_from("<5d", g, 16))
            if self.tipo == 6:
                return ("ellisse", *struct.unpack_from("<5d", g, 16))
        except struct.error:
            return None
        return None

    def testo(self) -> Testo | None:
        """Decodifica un testo (tipo 9), o None.

        Geometria: bbox (4 f32), punto (2 f64), 16 byte, u8 allineamento @48, ...,
        f32 altezza @68, f32 rotazione @84, f32 spaziatura extra @88,
        u32 numero righe @92, n f32 larghezze, poi il testo (righe separate da LF).
        """
        g = self.geometria
        if self.tipo != 9 or len(g) < 96:
            return None
        try:
            x, y = struct.unpack_from("<2d", g, 16)
            (h,) = struct.unpack_from("<f", g, 68)
            rot, extra = struct.unpack_from("<2f", g, 84)
            (n,) = struct.unpack_from("<I", g, 92)
        except struct.error:
            return None
        inizio = 96 + 4 * n
        if n > 10000 or inizio > len(g):
            return None
        righe = g[inizio:].decode(CODIFICA_TESTI, "replace").split("\n")
        # Il conteggio puo' includere righe vuote in coda (etichette dei locali: 68
        # righe dichiarate, ~10 usate): non occupano spazio nel riquadro.
        while len(righe) > 1 and not righe[-1].strip():
            righe.pop()
        interlinea = h + (extra if extra > 0 else 0.48 * h)
        # Interlinea dal riquadro salvato (bbox locale), quando la rotazione e'
        # multipla di 90°: verificato su testi da 2, 4, 5 e 12 righe.
        if len(righe) > 1 and h > 0 and abs(rot / 90 - round(rot / 90)) < 1e-4:
            x0, y0, x1, y1 = struct.unpack_from("<4f", g, 0)
            alto = (y1 - y0) if round(rot / 90) % 2 == 0 else (x1 - x0)
            if alto > h:
                interlinea = (alto - h) / (len(righe) - 1)
        return Testo(x, y, h, rot, g[48], interlinea, righe)


@dataclass
class Disegno:
    nome: str
    firma: str
    versione: str
    file_id: int
    frame: list[bytes] = field(default_factory=list)
    entita: list[Entita] = field(default_factory=list)


def _frame(d: bytes, inizio: int) -> list[bytes]:
    """Decomprime i frame zlib a partire da `inizio`, saltando le zone non compresse."""
    out, p = [], inizio
    while p + 8 <= len(d):
        n, grezzo = struct.unpack_from("<II", d, p)
        if 6 <= n <= len(d) - p - 4 and d[p + 8] == 0x78:
            try:
                dati = zlib.decompress(d[p + 8 : p + 4 + n])
            except zlib.error:
                dati = None
            if dati is not None and len(dati) == grezzo:
                out.append(dati)
                p += 4 + n
                continue
        p += 1
    return out


def leggi_entita(blocco: bytes, con_tag: bool = True) -> list[Entita]:
    out, p = [], 0
    fissi = _TAG_FISSI if con_tag else _TAG_FISSI[:15]
    while p < len(blocco):
        s, campi, guid = p, {}, b""
        for tag, dim in enumerate(fissi):
            if con_tag:
                (t,) = struct.unpack_from("<H", blocco, p)
                if t != tag:
                    raise ValueError(f"record @{s:#x}: atteso tag {tag}, trovato {t:#x}")
                p += 2
            if tag == 15:
                guid = blocco[p : p + dim]
            else:
                campi[tag] = int.from_bytes(blocco[p : p + dim], "little", signed=True)
            p += dim
        opz = {}
        while con_tag:
            (t,) = struct.unpack_from("<H", blocco, p)
            p += 2
            if t == _FINE_TAG:
                break
            if t not in _TAG_OPZIONALI:
                raise ValueError(f"record @{s:#x}: tag opzionale sconosciuto {t:#x}")
            opz[t] = blocco[p : p + _TAG_OPZIONALI[t]]
            p += _TAG_OPZIONALI[t]
        n_prop = campi[11]
        prop = [struct.unpack_from("<II", blocco, p + 8 * k) for k in range(n_prop)]
        p += 8 * n_prop
        geo = blocco[p : p + campi[13]]
        p += campi[13]
        out.append(Entita(s, campi[1], campi[4], campi, guid, opz, prop, geo))
    return out


def leggi_disegno(dati: bytes, nome: str = "") -> Disegno:
    firma = dati[34:44].split(b"\0", 1)[0].decode("latin-1")
    versione = dati[54:64].split(b"\0", 1)[0].decode("latin-1")
    file_id = struct.unpack_from("<I", dati, 108)[0] if len(dati) >= 112 else 0
    dis = Disegno(nome, firma, versione, file_id)
    fine_xml = dati.find(b"</HeaderExt>")
    if fine_xml < 0:
        return dis
    dis.frame = _frame(dati, fine_xml + len(b"</HeaderExt>"))
    if firma == "CAD_UNO" and len(dis.frame) > FRAME_ENTITA:
        try:
            con_tag = float(versione) >= _VERSIONE_CON_TAG
        except ValueError:
            con_tag = True
        dis.entita = leggi_entita(dis.frame[FRAME_ENTITA], con_tag)
    return dis


# --- DXF (R12 ASCII: si apre in AutoCAD, LibreCAD, ArchLine, QGIS...) -------
def _punti_ellisse(cx, cy, rx, ry, rot, n=72):
    c, s = math.cos(math.radians(rot)), math.sin(math.radians(rot))
    pts = []
    for k in range(n + 1):
        a = 2 * math.pi * k / n
        x, y = rx * math.cos(a), ry * math.sin(a)
        pts.append((cx + x * c - y * s, cy + x * s + y * c))
    return pts


@dataclass
class Layer:
    nome: str
    colore: int = 7  # ACI
    nascosto: bool = False


_NON_AMMESSI_DXF = '<>/\\":;?*|=`'


def nome_layer_dxf(nome: str) -> str:
    out = "".join("_" if c in _NON_AMMESSI_DXF or ord(c) < 32 else c for c in nome).strip()
    return out or "0"


def colore_aci(colour: str | int | None) -> int:
    """`Colour` dei layer ArchLine -> colore ACI.

    Con il bit 0x01000000 il byte basso e' un indice ACI (osservati 7, 8, 253);
    gli altri valori (RGB, spesso 0) diventano 7 (bianco/nero).
    """
    try:
        c = int(colour)
    except (TypeError, ValueError):
        return 7
    if c & 0x01000000 and 1 <= (c & 0xFF) <= 255:
        return c & 0xFF
    return 7


def scrivi_dxf(entita: list[Entita], percorso: Path, layers: dict[int, Layer] | None = None) -> Counter:
    """Scrive un DXF R12. `layers`: indice -> Layer (nomi dall'indice del .pro);
    senza, i layer si chiamano AL_<indice>."""
    layers = layers or {}
    nomi: dict[int, str] = {}
    usati: dict[str, Layer] = {}
    for e in entita:
        i = e.layer
        if i in nomi:
            continue
        lay = layers.get(i) or Layer(f"AL_{i}")
        n = nome_layer_dxf(lay.nome)
        if n in usati and usati[n] is not lay:  # stesso nome, layer diversi
            n = f"{n}_{i}"
        nomi[i] = n
        usati[n] = lay
    righe: list[str] = [
        "0", "SECTION", "2", "HEADER",
        "9", "$ACADVER", "1", "AC1009",
        "9", "$DWGCODEPAGE", "3", "ANSI_1252",
        "9", "$INSUNITS", "70", "4",  # millimetri
        "0", "ENDSEC",
        "0", "SECTION", "2", "TABLES",
        "0", "TABLE", "2", "LTYPE", "70", "1",
        "0", "LTYPE", "2", "CONTINUOUS", "70", "0", "3", "Solid line", "72", "65", "73", "0", "40", "0.0",
        "0", "ENDTAB",
        "0", "TABLE", "2", "LAYER", "70", str(len(usati) + 1),
        "0", "LAYER", "2", "0", "70", "0", "62", "7", "6", "CONTINUOUS",
    ]
    for n, lay in usati.items():
        if n == "0":
            continue
        colore = -lay.colore if lay.nascosto else lay.colore
        righe.extend(("0", "LAYER", "2", n, "70", "0", "62", str(colore), "6", "CONTINUOUS"))
    righe.extend(("0", "ENDTAB", "0", "ENDSEC", "0", "SECTION", "2", "ENTITIES"))
    fatti: Counter = Counter()

    def coppia(codice, valore):
        righe.extend((str(codice), valore if isinstance(valore, str) else f"{valore:.6f}"))

    def polilinea(pts, layer):
        righe.extend(("0", "POLYLINE", "8", layer, "66", "1", "70", "0"))
        for x, y in pts:
            righe.extend(("0", "VERTEX", "8", layer))
            coppia(10, x)
            coppia(20, y)
            coppia(30, 0.0)
        righe.extend(("0", "SEQEND", "8", layer))

    def testo(t: Testo, layer):
        n = len(t.righe)
        oriz, vert = (t.allineamento - 1) // 3, (t.allineamento - 1) % 3
        if not (0 <= oriz <= 2):
            oriz, vert = 0, 0
        alto = t.altezza + (n - 1) * t.interlinea
        base = (0.0, -alto / 2, -alto)[vert]  # linea di base dell'ultima riga
        c, s = math.cos(math.radians(t.rotazione)), math.sin(math.radians(t.rotazione))
        for i, riga in enumerate(t.righe):
            if not riga.strip():
                continue
            dy = base + (n - 1 - i) * t.interlinea
            px, py = t.x - dy * s, t.y + dy * c
            righe.extend(("0", "TEXT", "8", layer))
            coppia(10, px), coppia(20, py), coppia(30, 0.0), coppia(40, t.altezza)
            righe.extend(("1", riga.replace("\r", "")))
            if t.rotazione:
                coppia(50, t.rotazione % 360)
            if oriz:
                righe.extend(("72", str(oriz)))
                coppia(11, px), coppia(21, py), coppia(31, 0.0)

    for e in entita:
        layer = nomi[e.layer]
        if e.tipo == 9:
            t = e.testo()
            if t is not None:
                testo(t, layer)
                fatti[e.nome_tipo] += 1
            continue
        prim = e.segmenti_o_primitive()
        if prim is None:
            continue
        if prim[0] == "linee":
            pts = prim[1]
            if len(pts) == 2:
                righe.extend(("0", "LINE", "8", layer))
                for i, (x, y) in enumerate(pts):
                    coppia(10 + i, x)
                    coppia(20 + i, y)
                    coppia(30 + i, 0.0)
            elif len(pts) > 2:
                polilinea(pts, layer)
            else:
                continue
        elif prim[0] == "arco":
            _, cx, cy, r, a0, amp = prim
            if amp == 0 or abs(amp) >= 360:
                righe.extend(("0", "CIRCLE", "8", layer))
                coppia(10, cx), coppia(20, cy), coppia(30, 0.0), coppia(40, r)
            else:
                inizio, fine = (a0, a0 + amp) if amp > 0 else (a0 + amp, a0)
                righe.extend(("0", "ARC", "8", layer))
                coppia(10, cx), coppia(20, cy), coppia(30, 0.0), coppia(40, r)
                coppia(50, inizio % 360), coppia(51, fine % 360)
        elif prim[0] == "ellisse":
            _, cx, cy, rx, ry, rot = prim
            if abs(rx - ry) < 1e-9:
                righe.extend(("0", "CIRCLE", "8", layer))
                coppia(10, cx), coppia(20, cy), coppia(30, 0.0), coppia(40, rx)
            else:
                polilinea(_punti_ellisse(cx, cy, rx, ry, rot), layer)
        fatti[e.nome_tipo] += 1
    righe.extend(("0", "ENDSEC", "0", "EOF"))
    Path(percorso).write_text("\n".join(righe) + "\n", encoding=CODIFICA_TESTI, errors="replace")
    return fatti


def layers_da_pro(pro) -> dict[int, Layer]:
    """Layer dell'indice di un ProFile (leggi_pro.py): Index -> Layer."""
    out = {}
    for l in pro.layers():
        try:
            i = int(l.get("Index"))
        except (TypeError, ValueError):
            continue
        nome = l.get("NameW") or l.get("Name") or f"AL_{i}"
        nascosto = str(l.get("IsHidden", "")).strip().lower() in ("1", "true", "yes")
        out[i] = Layer(nome, colore_aci(l.get("Colour")), nascosto)
    return out


# --- riga di comando ------------------------------------------------------
def _disegni_da(percorso: Path, layers: dict | None = None) -> list[tuple[str, bytes]]:
    if percorso.suffix.lower() == ".asc":
        return [(percorso.name, percorso.read_bytes())]
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from leggi_pro import ProFile

    with ProFile(percorso) as p:
        if layers is not None:
            layers.update(layers_da_pro(p))
        nomi_2d = [d.get("Path", "") for d in p.disegni() if d.get("tipo") == "2D"]
        principale = None
        fid = p.indice().findtext("FileIDOfMain2DWindow")
        for d in p.disegni():
            if fid and str(d.get("file_id")) == fid.strip():
                principale = d.get("Path")
        ordine = ([principale] if principale else []) + [n for n in nomi_2d if n != principale]
        out = []
        for nome in ordine:
            for v in p.cerca(nome):
                out.append((nome, p.leggi(v)))
                break
        return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Legge i disegni 2D di ARCHLine.XP (.asc).")
    ap.add_argument("file", type=Path, help="progetto .pro oppure disegno .asc")
    ap.add_argument("--disegno", help="nome del .asc da usare (default: pianta principale)")
    ap.add_argument("--dxf", type=Path, help="esporta in DXF R12")
    a = ap.parse_args(argv)

    layers: dict[int, Layer] = {}
    disegni = _disegni_da(a.file, layers)
    if not disegni:
        print("nessun disegno 2D trovato", file=sys.stderr)
        return 2
    if a.disegno:
        disegni = [d for d in disegni if d[0].lower() == a.disegno.lower()]
        if not disegni:
            print(f"disegno {a.disegno} non trovato", file=sys.stderr)
            return 2

    for nome, dati in disegni:
        try:
            dis = leggi_disegno(dati, nome)
        except ValueError as e:
            print(f"{nome}: {e}", file=sys.stderr)
            continue
        tipi = Counter(e.nome_tipo for e in dis.entita)
        print(f"{nome}: {dis.firma} v{dis.versione}, {len(dis.frame)} frame, {len(dis.entita)} entita'")
        for t, n in tipi.most_common():
            print(f"   {n:6d}  {t}")
        if a.dxf:
            fatti = scrivi_dxf(dis.entita, a.dxf, layers)
            print(f"DXF scritto in {a.dxf}: {sum(fatti.values())} entita' ({dict(fatti)})")
            break
    return 0


if __name__ == "__main__":
    sys.exit(main())
