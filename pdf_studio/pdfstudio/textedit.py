"""Modifica del testo esistente: paragrafi con riflusso, righe singole, trova e sostituisci.

Per mantenere l'aspetto originale il testo nuovo viene scritto, in ordine di preferenza:
1. con il font incorporato nel PDF, se contiene tutti i caratteri necessari;
2. con lo stesso font installato nel sistema (es. C:\\Windows\\Fonts\\calibri.ttf);
3. con il font standard più simile (Helvetica, Times, Courier), comunque incorporato.
"""
from __future__ import annotations

import hashlib
import os
import re
import sys
from dataclasses import dataclass, field

import pymupdf

_SUBSET = re.compile(r"^[A-Z]{6}\+")


def normalize_font_name(name: str) -> str:
    """'ABCDEF+Arial-BoldMT' → 'arialbold', 'TimesNewRomanPSMT' → 'timesnewroman'."""
    name = re.sub(r"[^a-z0-9]", "", _SUBSET.sub("", name or "").lower())
    name = re.sub(r"(psmt|mt)$", "", name)
    name = re.sub(r"ps(bold|italic|bolditalic|)$", r"\1", name)
    for word in ("regular", "normal", "book"):
        if name.endswith(word) and len(name) > len(word):
            name = name[: -len(word)]
    return name


def _font_dirs() -> list[str]:
    if sys.platform == "win32":
        windir = os.environ.get("WINDIR", r"C:\Windows")
        dirs = [os.path.join(windir, "Fonts")]
        local = os.environ.get("LOCALAPPDATA")
        if local:
            dirs.append(os.path.join(local, "Microsoft", "Windows", "Fonts"))
        return dirs
    if sys.platform == "darwin":
        return ["/System/Library/Fonts", "/Library/Fonts", os.path.expanduser("~/Library/Fonts")]
    return ["/usr/share/fonts", "/usr/local/share/fonts", os.path.expanduser("~/.fonts"),
            os.path.expanduser("~/.local/share/fonts")]


_SYSTEM_FONTS: dict[str, str] | None = None


def system_fonts() -> dict[str, str]:
    """Indice nome normalizzato → file dei font installati (costruito una volta)."""
    global _SYSTEM_FONTS
    if _SYSTEM_FONTS is not None:
        return _SYSTEM_FONTS
    index: dict[str, str] = {}
    for d in _font_dirs():
        for root, _dirs, files in os.walk(d):
            for fn in files:
                if not fn.lower().endswith((".ttf", ".otf")):
                    continue
                path = os.path.join(root, fn)
                try:
                    font = pymupdf.Font(fontfile=path)
                except Exception:
                    continue
                for key in {normalize_font_name(font.name), normalize_font_name(os.path.splitext(fn)[0])}:
                    index.setdefault(key, path)
    _SYSTEM_FONTS = index
    return index


# Nomi comuni nei PDF → equivalenti metrici diffusi
_ALIASES = {
    "arial": ["arial", "liberationsans", "helvetica"],
    "arialbold": ["arialbold", "liberationsansbold"],
    "arialitalic": ["arialitalic", "liberationsansitalic"],
    "timesnewroman": ["timesnewroman", "liberationserif"],
    "timesnewromanbold": ["timesnewromanbold", "liberationserifbold"],
    "couriernew": ["couriernew", "liberationmono"],
    "calibri": ["calibri", "carlito"],
    "calibribold": ["calibribold", "carlitobold"],
    "cambria": ["cambria", "caladea"],
}


@dataclass
class FontChoice:
    alias: str            # nome della risorsa font nella pagina
    buffer: bytes         # dati del font (sempre incorporato)
    source: str           # "incorporato", "sistema" o "standard"
    label: str            # nome leggibile

    def font(self) -> pymupdf.Font:
        return pymupdf.Font(fontbuffer=self.buffer)


def _base14_for(font: str, flags: int) -> str:
    from .document import guess_base14
    return guess_base14(font, flags)


def _covers(font: pymupdf.Font, text: str) -> bool:
    return all(c.isspace() or font.has_glyph(ord(c)) for c in text)


class FontResolver:
    def __init__(self, doc: pymupdf.Document):
        self.doc = doc

    def embedded(self, page: pymupdf.Page, fontname: str) -> bytes | None:
        target = normalize_font_name(fontname)
        for f in page.get_fonts(full=True):
            xref, ext, basefont = f[0], f[1], f[3]
            if normalize_font_name(basefont) != target or ext in ("n/a", ""):
                continue
            try:
                _name, ext2, _type, buf = self.doc.extract_font(xref)
            except Exception:
                continue
            if buf and ext2 in ("ttf", "otf", "cff", "pfa", "pfb", "ttc"):
                return buf
        return None

    def choose(self, page: pymupdf.Page, fontname: str, flags: int, text: str) -> FontChoice:
        label = _SUBSET.sub("", fontname)
        # 1. Font incorporato (spesso è un sottoinsieme: va verificata la copertura)
        buf = self.embedded(page, fontname)
        if buf:
            try:
                f = pymupdf.Font(fontbuffer=buf)
                # I font sottoinsieme senza tabella unicode affidabile danno has_glyph ingannevoli:
                # richiediamo anche che il nome del font sia leggibile
                if _covers(f, text) and f.glyph_count > 0:
                    return FontChoice(self._alias(buf), buf, "incorporato", label)
            except Exception:
                pass
        # 2. Font di sistema con lo stesso nome
        key = normalize_font_name(fontname)
        idx = system_fonts()
        for cand in _ALIASES.get(key, []) + [key]:
            path = idx.get(cand)
            if path:
                try:
                    with open(path, "rb") as fh:
                        data = fh.read()
                    f = pymupdf.Font(fontbuffer=data)
                    if _covers(f, text):
                        return FontChoice(self._alias(data), data, "sistema", f.name)
                except Exception:
                    continue
        # 3. Standard più simile, incorporato
        b14 = _base14_for(fontname, flags)
        f = pymupdf.Font(b14)
        if not _covers(f, text):
            # Caratteri fuori dal set latino: font universale incluso in MuPDF
            f = pymupdf.Font("notos" if b14.startswith("he") else "notoserif" if b14.startswith("ti") else "notos")
        return FontChoice(self._alias(f.buffer), f.buffer, "standard", f.name)

    @staticmethod
    def _alias(buf: bytes) -> str:
        return "PS" + hashlib.md5(buf).hexdigest()[:10]


# ------------------------------------------------------------------ paragrafi
@dataclass
class TextLine:
    bbox: pymupdf.Rect
    origin: pymupdf.Point
    text: str


@dataclass
class TextBlock:
    page: int
    bbox: pymupdf.Rect
    lines: list[TextLine]
    font: str
    size: float
    color: tuple[float, float, float]
    flags: int
    align: str = "left"
    line_height: float = 1.2
    extra: dict = field(default_factory=dict)

    @property
    def text(self) -> str:
        out = ""
        for ln in self.lines:
            t = ln.text.rstrip()
            if not out:
                out = t
            elif out.endswith("-") and len(out) > 1 and out[-2].isalpha():
                out = out[:-1] + t.lstrip()  # parola spezzata a fine riga
            else:
                out += " " + t.lstrip()
        return out

    @property
    def bold(self) -> bool:
        return bool(self.flags & 16) or "bold" in self.font.lower()

    @property
    def italic(self) -> bool:
        return bool(self.flags & 2) or "italic" in self.font.lower() or "oblique" in self.font.lower()


def _rgb(value: int) -> tuple[float, float, float]:
    return (((value >> 16) & 255) / 255, ((value >> 8) & 255) / 255, (value & 255) / 255)


def block_at(doc: pymupdf.Document, index: int, point: pymupdf.Point) -> TextBlock | None:
    page = doc[index]
    for b in page.get_text("dict", flags=pymupdf.TEXTFLAGS_TEXT)["blocks"]:
        if b.get("type") != 0 or not pymupdf.Rect(b["bbox"]).contains(point):
            continue
        lines = []
        stats: dict[tuple, int] = {}
        for ln in b["lines"]:
            if ln["dir"] != (1.0, 0.0) and abs(ln["dir"][1]) > 0.01:
                return None  # testo ruotato: non supportato nella modifica a paragrafo
            text = "".join(s["text"] for s in ln["spans"])
            if not text.strip():
                continue
            lines.append(TextLine(pymupdf.Rect(ln["bbox"]), pymupdf.Point(ln["spans"][0]["origin"]), text))
            for s in ln["spans"]:
                key = (s["font"], round(s["size"], 1), s["color"], s["flags"] & (2 | 16))
                stats[key] = stats.get(key, 0) + len(s["text"].strip())
        if not lines:
            return None
        font, size, color, flags = max(stats, key=stats.get)
        blk = TextBlock(index, pymupdf.Rect(b["bbox"]), lines, font, size, _rgb(color), flags)
        blk.extra["mixed_styles"] = len(stats) > 1
        # Interlinea
        if len(lines) > 1:
            gaps = [lines[i + 1].origin.y - lines[i].origin.y for i in range(len(lines) - 1)]
            gaps = [g for g in gaps if g > 0]
            if gaps:
                blk.line_height = max(1.0, min(2.5, sorted(gaps)[len(gaps) // 2] / size))
        # Allineamento
        if len(lines) >= 2:
            x0s = [ln.bbox.x0 for ln in lines]
            x1s = [ln.bbox.x1 for ln in lines[:-1]]
            left_aligned = max(x0s) - min(x0s) < size * 0.6
            right_aligned = max(x1s) - min(x1s) < size * 0.6 if len(x1s) > 1 else False
            centers = [(ln.bbox.x0 + ln.bbox.x1) / 2 for ln in lines]
            if left_aligned and right_aligned and len(lines) >= 3:
                blk.align = "justify"
            elif not left_aligned and max(centers) - min(centers) < size * 0.6:
                blk.align = "center"
            elif not left_aligned and len(x1s) > 1 and right_aligned:
                blk.align = "right"
        return blk
    return None


def _remove_text(page: pymupdf.Page, rect: pymupdf.Rect) -> None:
    page.add_redact_annot(rect, fill=False)
    page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE,
                          graphics=getattr(pymupdf, "PDF_REDACT_LINE_ART_NONE", 0))


def _css_color(rgb) -> str:
    return "#%02x%02x%02x" % tuple(int(round(c * 255)) for c in rgb)


def _html_escape(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace("\n", "<br/>"))


def _space_below(page: pymupdf.Page, rect: pymupdf.Rect) -> float:
    """Spazio libero sotto il riquadro fino al blocco successivo o al margine."""
    height = page.rect.height if page.rotation in (0, 180) else page.rect.width  # spazio non ruotato
    limit = height - 20
    for b in page.get_text("blocks"):
        r = pymupdf.Rect(b[:4])
        if r.y0 >= rect.y1 - 1 and r.x1 > rect.x0 and r.x0 < rect.x1:
            limit = min(limit, r.y0 - 2)
    return max(0.0, limit - rect.y1)


def replace_block(doc: pymupdf.Document, block: TextBlock, new_text: str, fontsize: float | None = None,
                  color=None, align: str | None = None) -> dict:
    """Riscrive un paragrafo con riflusso. Ritorna informazioni su font e adattamento."""
    page = doc[block.page]
    size = fontsize or block.size
    color = block.color if color is None else color
    choice = FontResolver(doc).choose(page, block.font, block.flags, new_text)
    inner = pymupdf.Rect(block.bbox.x0 + 0.5, block.bbox.y0 + 0.5, block.bbox.x1 - 0.5, block.bbox.y1 - 0.5)
    free_below = _space_below(page, block.bbox)
    _remove_text(page, inner)
    if not new_text.strip():
        return {"font": choice.label, "source": choice.source, "scale": 1.0}

    arch = pymupdf.Archive()
    ext = "otf" if choice.buffer[:4] == b"OTTO" else "ttf"
    arch.add(choice.buffer, f"f.{ext}")
    css = (f"@font-face {{font-family: PSF; src: url(f.{ext});}} "
           f"* {{font-family: PSF; font-size: {size:.2f}px; color: {_css_color(color)}; "
           f"line-height: {block.line_height:.3f}; margin: 0; padding: 0;}} "
           f"p {{text-align: {align or block.align};}}")
    html = f"<div>{_html_escape(new_text)}</div>"
    css = css.replace("p {text-align", "div {text-align")
    rect = pymupdf.Rect(block.bbox.x0, block.bbox.y0, block.bbox.x1 + 1, block.bbox.y1 + 1)
    # Calibra la posizione su una pagina di prova: la prima riga deve cadere sulla
    # stessa linea di base e allo stesso margine sinistro del paragrafo originale
    dx, dy = _calibrate(page, rect, html, css, arch, block.lines[0].origin)
    rect = pymupdf.Rect(rect.x0 + dx, rect.y0 + dy, rect.x1 + dx, rect.y1 + dy)
    rotate = page.rotation
    spare, scale = page.insert_htmlbox(rect, html, css=css, archive=arch, scale_low=1, rotate=rotate)
    if spare < 0:
        # Non entra: usa lo spazio libero sotto, poi riduce leggermente il carattere
        taller = pymupdf.Rect(rect.x0, rect.y0, rect.x1, rect.y1 + free_below)
        spare, scale = page.insert_htmlbox(taller, html, css=css, archive=arch, scale_low=1, rotate=rotate)
        if spare < 0:
            spare, scale = page.insert_htmlbox(taller, html, css=css, archive=arch, scale_low=0.5,
                                               rotate=rotate)
    return {"font": choice.label, "source": choice.source, "scale": scale, "fits": spare >= 0}


def _calibrate(page: pymupdf.Page, rect: pymupdf.Rect, html: str, css: str, arch, origin: pymupdf.Point):
    """Misura dove lo Story scrive la prima riga e ritorna la correzione (dx, dy)."""
    height = page.rect.height if page.rotation in (0, 180) else page.rect.width
    width = page.rect.width if page.rotation in (0, 180) else page.rect.height
    tmp = pymupdf.open()
    try:
        tp = tmp.new_page(width=width, height=height + 2000)
        big = pymupdf.Rect(rect.x0, rect.y0, rect.x1, rect.y0 + 1500)
        tp.insert_htmlbox(big, html, css=css, archive=arch, scale_low=1)
        for b in tp.get_text("dict")["blocks"]:
            for ln in b.get("lines", []):
                if ln["spans"]:
                    o = ln["spans"][0]["origin"]
                    return origin.x - o[0], origin.y - o[1]
    finally:
        tmp.close()
    return 0.0, 0.0


def replace_line_span(doc: pymupdf.Document, page_no: int, bbox: pymupdf.Rect, origin: pymupdf.Point,
                      font: str, flags: int, size: float, color, new_text: str) -> FontChoice | None:
    """Riscrive una porzione di riga sulla stessa linea di base."""
    page = doc[page_no]
    r = pymupdf.Rect(bbox)
    shrink = r.height * 0.2
    r.y0 += shrink
    r.y1 -= shrink
    choice = FontResolver(doc).choose(page, font, flags, new_text) if new_text else None
    _remove_text(page, r)
    if new_text:
        page.insert_font(fontname=choice.alias, fontbuffer=choice.buffer)
        page.insert_text(origin, new_text, fontsize=size, fontname=choice.alias, color=color,
                         rotate=page.rotation)
    return choice


def find_replace(doc: pymupdf.Document, query: str, replacement: str, pages=None,
                 match_case: bool = True) -> int:
    """Sostituisce ogni occorrenza riscrivendo lo span che la contiene. Ritorna le sostituzioni."""
    if not query:
        return 0
    count = 0
    flags_re = 0 if match_case else re.IGNORECASE
    pattern = re.compile(re.escape(query), flags_re)
    for pno in (pages if pages is not None else range(doc.page_count)):
        page = doc[pno]
        targets = []
        for b in page.get_text("dict", flags=pymupdf.TEXTFLAGS_TEXT)["blocks"]:
            for ln in b.get("lines", []):
                if abs(ln["dir"][1]) > 0.01:
                    continue
                for s in ln["spans"]:
                    if pattern.search(s["text"]):
                        targets.append(s)
        for s in targets:
            new, n = pattern.subn(lambda _m: replacement, s["text"])
            if not n:
                continue
            # Mantiene gli spazi iniziali dello span per non spostare il testo
            replace_line_span(doc, pno, pymupdf.Rect(s["bbox"]), pymupdf.Point(s["origin"]), s["font"],
                              s["flags"], s["size"], _rgb(s["color"]), new.rstrip())
            count += n
    return count
