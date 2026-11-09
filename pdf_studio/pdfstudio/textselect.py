"""Selezione del testo di una pagina in ordine di lettura (come in Acrobat).

I caratteri della pagina vengono letti una volta e messi in fila nell'ordine del
testo; una selezione è un intervallo [inizio, fine] di quella fila. Le coordinate
sono quelle non ruotate della pagina (le stesse di PyMuPDF).
"""
from __future__ import annotations

from dataclasses import dataclass

import pymupdf


@dataclass
class Char:
    c: str
    bbox: pymupdf.Rect
    line: int     # indice progressivo della riga nella pagina
    block: int


class PageText:
    def __init__(self, page: pymupdf.Page):
        self.chars: list[Char] = []
        self.line_rects: dict[int, pymupdf.Rect] = {}
        line_no = 0
        raw = page.get_text("rawdict", flags=pymupdf.TEXTFLAGS_TEXT | pymupdf.TEXT_PRESERVE_WHITESPACE)
        for b_no, block in enumerate(raw["blocks"]):
            for line in block.get("lines", []):
                added = False
                for span in line["spans"]:
                    for ch in span["chars"]:
                        r = pymupdf.Rect(ch["bbox"])
                        if r.is_empty:  # spazi e caratteri senza larghezza
                            r = pymupdf.Rect(r.x0, line["bbox"][1], r.x0 + 0.5, line["bbox"][3])
                        self.chars.append(Char(ch["c"], r, line_no, b_no))
                        added = True
                if added:
                    self.line_rects[line_no] = pymupdf.Rect(line["bbox"])
                    line_no += 1

    @property
    def empty(self) -> bool:
        return not any(c.c.strip() for c in self.chars)

    # -------------------------------------------------------------- ricerca
    def char_at(self, pt: pymupdf.Point, tolerance: float = 2.0) -> int | None:
        """Carattere sotto il punto (con piccola tolleranza), altrimenti None."""
        best, best_d = None, tolerance
        for i, ch in enumerate(self.chars):
            r = ch.bbox
            dx = max(r.x0 - pt.x, 0, pt.x - r.x1)
            dy = max(r.y0 - pt.y, 0, pt.y - r.y1)
            d = max(dx, dy)
            if d <= best_d:
                best, best_d = i, d
                if d == 0:
                    break
        return best

    def nearest(self, pt: pymupdf.Point) -> int | None:
        """Carattere più vicino al punto, per estendere la selezione trascinando."""
        if not self.chars:
            return None
        # Prima la riga più vicina in verticale, poi il carattere più vicino in orizzontale
        def vdist(r: pymupdf.Rect) -> float:
            return 0 if r.y0 <= pt.y <= r.y1 else min(abs(pt.y - r.y0), abs(pt.y - r.y1))
        line = min(self.line_rects, key=lambda n: (vdist(self.line_rects[n]),
                                                   abs((self.line_rects[n].x0 + self.line_rects[n].x1) / 2
                                                       - pt.x)))
        idx = [i for i, ch in enumerate(self.chars) if ch.line == line]
        i = min(idx, key=lambda k: abs((self.chars[k].bbox.x0 + self.chars[k].bbox.x1) / 2 - pt.x))
        # Oltre la metà del carattere: la selezione lo include
        return i

    def is_over_text(self, pt: pymupdf.Point) -> bool:
        i = self.char_at(pt)
        if i is not None:
            return True
        return any(r.contains(pt) for r in self.line_rects.values())

    # -------------------------------------------------------------- intervalli
    def text(self, a: int, b: int) -> str:
        """Testo selezionato: le righe di uno stesso paragrafo si uniscono (incollando in Word
        si ottiene un paragrafo continuo), i paragrafi restano separati."""
        if a > b:
            a, b = b, a
        out, prev = [], None
        for ch in self.chars[a:b + 1]:
            if prev is not None and ch.line != prev.line:
                if ch.block != prev.block:
                    out.append("\n\n" if self._gap(prev, ch) else "\n")
                elif out and out[-1] == "-" and len(out) > 1 and out[-2].isalpha():
                    out.pop()  # parola spezzata a fine riga
                elif out and not out[-1].isspace():
                    out.append(" ")
            out.append(ch.c)
            prev = ch
        lines = "".join(out).split("\n")
        return "\n".join(" ".join(ln.split()) if ln.strip() else "" for ln in lines).strip("\n")

    def _gap(self, a: Char, b: Char) -> bool:
        """Spazio verticale ampio tra due blocchi = nuovo paragrafo."""
        ra, rb = self.line_rects[a.line], self.line_rects[b.line]
        return rb.y0 - ra.y1 > (ra.height * 0.6)

    def rects(self, a: int, b: int) -> list[pymupdf.Rect]:
        """Un rettangolo per riga, per evidenziare la selezione."""
        if a > b:
            a, b = b, a
        rows: dict[int, pymupdf.Rect] = {}
        for ch in self.chars[a:b + 1]:
            lr = self.line_rects[ch.line]
            r = pymupdf.Rect(ch.bbox.x0, lr.y0, ch.bbox.x1, lr.y1)
            rows[ch.line] = rows[ch.line] | r if ch.line in rows else r
        return list(rows.values())

    def word_at(self, i: int) -> tuple[int, int]:
        def is_word(c: str) -> bool:
            return c.isalnum() or c in "_-'’.,/@€%"
        if not is_word(self.chars[i].c):
            return i, i
        a = b = i
        line = self.chars[i].line
        while a > 0 and self.chars[a - 1].line == line and is_word(self.chars[a - 1].c):
            a -= 1
        while b < len(self.chars) - 1 and self.chars[b + 1].line == line and is_word(self.chars[b + 1].c):
            b += 1
        # niente punteggiatura finale
        while b > a and self.chars[b].c in ".,":
            b -= 1
        return a, b

    def line_at(self, i: int) -> tuple[int, int]:
        line = self.chars[i].line
        idx = [k for k, ch in enumerate(self.chars) if ch.line == line]
        return idx[0], idx[-1]

    def all(self) -> tuple[int, int] | None:
        return (0, len(self.chars) - 1) if self.chars else None

    def in_rect(self, rect: pymupdf.Rect) -> str:
        """Testo dentro un rettangolo (selezione a colonna, utile per le tabelle)."""
        chosen = [ch for ch in self.chars if rect.contains((ch.bbox.tl + ch.bbox.br) / 2)]
        out, prev = [], None
        for ch in chosen:
            if prev is not None and ch.line != prev.line:
                out.append("\n")
            out.append(ch.c)
            prev = ch
        return "\n".join(ln.rstrip() for ln in "".join(out).split("\n")).strip()
