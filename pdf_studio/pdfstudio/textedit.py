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


_NOLIG_CACHE: dict[str, bytes] = {}


def without_ligatures(buf: bytes) -> bytes:
    """Toglie la tabella GSUB (legature come «tt», «ti», «fi»): con le legature il motore HTML
    scrive glifi senza corrispondenza Unicode e il testo non si trova né si copia più.
    La crenatura (GPOS) resta, quindi la spaziatura delle lettere non cambia."""
    key = hashlib.md5(buf).hexdigest()
    if key in _NOLIG_CACHE:
        return _NOLIG_CACHE[key]
    out = buf
    try:
        import io
        from fontTools.ttLib import TTFont
        font = TTFont(io.BytesIO(buf), lazy=False)
        if "GSUB" in font:
            del font["GSUB"]
            bio = io.BytesIO()
            font.save(bio)
            out = bio.getvalue()
    except Exception:
        pass  # formato non gestito (es. CFF puro): si usa il font così com'è
    _NOLIG_CACHE[key] = out
    return out


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
class TextStyle:
    font: str
    size: float
    color: tuple[float, float, float]
    flags: int

    @property
    def bold(self) -> bool:
        return bool(self.flags & 16) or any(w in self.font.lower() for w in ("bold", "black", "heavy"))

    @property
    def italic(self) -> bool:
        return bool(self.flags & 2) or "italic" in self.font.lower() or "oblique" in self.font.lower()


@dataclass
class TextLine:
    bbox: pymupdf.Rect
    origin: pymupdf.Point
    text: str


@dataclass
class TextBlock:
    """Un paragrafo: righe consecutive con le parti di testo (run) e i loro stili."""
    page: int
    bbox: pymupdf.Rect
    lines: list[TextLine]
    font: str            # stile prevalente (per compatibilità e per l'anteprima)
    size: float
    color: tuple[float, float, float]
    flags: int
    align: str = "left"
    line_height: float = 1.2
    extra: dict = field(default_factory=dict)
    styles: list[TextStyle] = field(default_factory=list)
    runs: list[tuple[str, int]] = field(default_factory=list)   # (testo, indice dello stile)
    pitch: float = 0.0   # distanza tra le linee di base, in punti

    @property
    def text(self) -> str:
        return "".join(t for t, _s in self.runs)

    @property
    def bold(self) -> bool:
        return bool(self.flags & 16) or "bold" in self.font.lower()

    @property
    def italic(self) -> bool:
        return bool(self.flags & 2) or "italic" in self.font.lower() or "oblique" in self.font.lower()

    def char_styles(self) -> list[int]:
        """Indice di stile per ogni carattere del testo."""
        out: list[int] = []
        for t, sid in self.runs:
            out.extend([sid] * len(t))
        return out


def _rgb(value: int) -> tuple[float, float, float]:
    return (((value >> 16) & 255) / 255, ((value >> 8) & 255) / 255, (value & 255) / 255)


def _page_lines(page: pymupdf.Page) -> list[dict]:
    """Righe orizzontali della pagina, ordinate dall'alto; unisce i pezzi sulla stessa linea di base."""
    raw = []
    for b in page.get_text("dict", flags=pymupdf.TEXTFLAGS_TEXT)["blocks"]:
        for ln in b.get("lines", []):
            if abs(ln["dir"][1]) > 0.01 or ln["dir"][0] < 0:
                continue  # testo ruotato: non modificabile come paragrafo
            spans = [sp for sp in ln["spans"] if sp["text"]]
            if not "".join(sp["text"] for sp in spans).strip():
                continue
            raw.append({"bbox": pymupdf.Rect(ln["bbox"]), "spans": spans,
                        "y": spans[0]["origin"][1], "size": max(sp["size"] for sp in spans)})
    raw.sort(key=lambda r: (round(r["y"], 1), r["bbox"].x0))
    merged: list[dict] = []
    for r in raw:
        last = merged[-1] if merged else None
        if last and abs(last["y"] - r["y"]) < 0.3 * r["size"] and 0 <= r["bbox"].x0 - last["bbox"].x1 < 1.5 * r["size"]:
            last["spans"] += r["spans"]
            last["bbox"] |= r["bbox"]
            last["size"] = max(last["size"], r["size"])
        else:
            merged.append(r)
    for r in merged:
        sizes: dict[float, int] = {}
        for sp in r["spans"]:
            sizes[round(sp["size"], 1)] = sizes.get(round(sp["size"], 1), 0) + len(sp["text"])
        r["main_size"] = max(sizes, key=sizes.get)
    return merged


def _h_overlap(a: pymupdf.Rect, b: pymupdf.Rect) -> float:
    return min(a.x1, b.x1) - max(a.x0, b.x0)


def _next_line(lines: list[dict], cur: dict, down: bool) -> dict | None:
    size = cur["main_size"]
    cands = [ln for ln in lines if ln is not cur and
             ((ln["y"] > cur["y"] + 0.3 * size) if down else (ln["y"] < cur["y"] - 0.3 * size)) and
             _h_overlap(ln["bbox"], cur["bbox"]) > 0.25 * min(ln["bbox"].width, cur["bbox"].width)]
    if not cands:
        return None
    return min(cands, key=lambda ln: abs(ln["y"] - cur["y"]))


def _same_paragraph(a: dict, b: dict, pitch: float | None) -> bool:
    """b segue a nello stesso paragrafo?"""
    size = max(a["main_size"], b["main_size"])
    if abs(a["main_size"] - b["main_size"]) > 0.2 * size:
        return False
    gap = abs(b["y"] - a["y"])
    if pitch:
        return abs(gap - pitch) <= 0.15 * pitch
    return gap <= 1.6 * size and abs(a["bbox"].x0 - b["bbox"].x0) < 4 * size


def block_at(doc: pymupdf.Document, index: int, point: pymupdf.Point) -> TextBlock | None:
    """Paragrafo che contiene il punto, anche se nel PDF ogni riga è un pezzo separato."""
    lines = _page_lines(doc[index])
    hit = next((ln for ln in lines if (ln["bbox"] + (-1, -1, 1, 1)).contains(point)), None)
    if hit is None:
        return None
    para = [hit]
    pitch = None
    cur = hit
    while (nxt := _next_line(lines, cur, down=True)) is not None and _same_paragraph(cur, nxt, pitch):
        pitch = pitch or abs(nxt["y"] - cur["y"])
        para.append(nxt)
        cur = nxt
    cur = hit
    while (prv := _next_line(lines, cur, down=False)) is not None and _same_paragraph(prv, cur, pitch):
        pitch = pitch or abs(cur["y"] - prv["y"])
        para.insert(0, prv)
        cur = prv

    styles: list[TextStyle] = []
    keys: dict[tuple, int] = {}
    runs: list[tuple[str, int]] = []
    counts: dict[int, int] = {}
    tlines: list[TextLine] = []
    for n, ln in enumerate(para):
        spans = ln["spans"]
        if n and runs:
            last_text, last_sid = runs[-1]
            first = spans[0]["text"]
            if last_text.endswith("-") and len(last_text) > 1 and last_text[-2].isalpha() and first[:1].islower():
                runs[-1] = (last_text[:-1], last_sid)          # parola spezzata a fine riga
            elif not last_text.endswith(" ") and not first.startswith(" "):
                runs[-1] = (last_text + " ", last_sid)
        for sp in spans:
            key = (sp["font"], round(sp["size"], 1), sp["color"], sp["flags"] & (2 | 16))
            if key not in keys:
                keys[key] = len(styles)
                styles.append(TextStyle(sp["font"], sp["size"], _rgb(sp["color"]), sp["flags"]))
            sid = keys[key]
            if runs and runs[-1][1] == sid:
                runs[-1] = (runs[-1][0] + sp["text"], sid)
            else:
                runs.append((sp["text"], sid))
            counts[sid] = counts.get(sid, 0) + len(sp["text"].strip())
        tlines.append(TextLine(ln["bbox"], pymupdf.Point(spans[0]["origin"]),
                               "".join(sp["text"] for sp in spans)))
    main = styles[max(counts, key=counts.get)]
    bbox = pymupdf.Rect(para[0]["bbox"])
    for ln in para[1:]:
        bbox |= ln["bbox"]
    blk = TextBlock(index, bbox, tlines, main.font, main.size, main.color, main.flags,
                    styles=styles, runs=runs, pitch=pitch or main.size * 1.2)
    blk.line_height = max(1.0, min(2.5, blk.pitch / main.size))
    blk.extra["mixed_styles"] = len(styles) > 1
    blk.extra["line_rects"] = [ln["bbox"] for ln in para]
    # Allineamento
    if len(para) >= 2:
        size = main.size
        x0s = [ln["bbox"].x0 for ln in para]
        x1s = [ln["bbox"].x1 for ln in para[:-1]]
        left_aligned = max(x0s) - min(x0s) < size * 0.6
        right_aligned = max(x1s) - min(x1s) < size * 0.6 if len(x1s) > 1 else False
        centers = [(ln["bbox"].x0 + ln["bbox"].x1) / 2 for ln in para]
        if left_aligned and right_aligned and len(para) >= 3:
            blk.align = "justify"
        elif left_aligned and len(para) == 2 and abs(para[0]["bbox"].x1 - bbox.x1) < size * 0.6 \
                and para[1]["bbox"].x1 < bbox.x1 - size:
            blk.align = "justify"  # due righe: la prima arriva al margine destro
        elif not left_aligned and max(centers) - min(centers) < size * 0.6:
            blk.align = "center"
        elif not left_aligned and len(x1s) > 1 and right_aligned:
            blk.align = "right"
    return blk


def _remove_text(page: pymupdf.Page, rect: pymupdf.Rect) -> None:
    page.add_redact_annot(rect, fill=False)
    page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE,
                          graphics=getattr(pymupdf, "PDF_REDACT_LINE_ART_NONE", 0))


def _remove_lines(page: pymupdf.Page, rects: list[pymupdf.Rect]) -> None:
    """Toglie il testo riga per riga (non tocca quello che sta accanto al paragrafo)."""
    for r in rects:
        h = r.height
        page.add_redact_annot(pymupdf.Rect(r.x0 - 0.5, r.y0 + 0.15 * h, r.x1 + 0.5, r.y1 - 0.15 * h), fill=False)
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


def map_styles(block: TextBlock, new_text: str) -> list[tuple[str, int]]:
    """Assegna uno stile a ogni carattere del testo nuovo confrontandolo con il vecchio:
    i caratteri rimasti tengono il loro stile, quelli nuovi prendono lo stile del carattere
    vicino (come in Word, dove si scrive con la formattazione del punto in cui si è)."""
    import difflib
    old = block.text
    old_styles = block.char_styles()
    main = block.styles.index(next(s for s in block.styles if s.font == block.font and
                                   abs(s.size - block.size) < 0.05)) if block.styles else 0
    styles: list[int] = []
    sm = difflib.SequenceMatcher(None, old, new_text, autojunk=False)
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            styles.extend(old_styles[i1:i2])
        elif op == "replace":
            span = old_styles[i1:i2] or [main]
            styles.extend(span[min(k, len(span) - 1)] for k in range(j2 - j1))
        elif op == "insert":
            # Stile del carattere precedente; a inizio paragrafo quello del successivo
            ref = old_styles[i1 - 1] if i1 > 0 else (old_styles[0] if old_styles else main)
            if i1 > 0 and old[i1 - 1] == " " and i1 < len(old):
                ref = old_styles[i1]  # dopo uno spazio si prosegue con la parola che segue
            styles.extend([ref] * (j2 - j1))
    runs: list[tuple[str, int]] = []
    for ch, sid in zip(new_text, styles):
        if runs and runs[-1][1] == sid:
            runs[-1] = (runs[-1][0] + ch, sid)
        else:
            runs.append((ch, sid))
    return runs


def replace_block(doc: pymupdf.Document, block: TextBlock, new_text, fontsize: float | None = None,
                  color=None, align: str | None = None) -> dict:
    """Riscrive un paragrafo con riflusso mantenendo la formattazione di ogni parte.

    ``new_text`` è il testo nuovo (gli stili vengono ricavati confrontandolo con il vecchio)
    oppure direttamente l'elenco di run ``[(testo, indice stile), …]`` dell'editor."""
    page = doc[block.page]
    runs = map_styles(block, new_text) if isinstance(new_text, str) else [r for r in new_text if r[0]]
    plain = "".join(t for t, _s in runs)
    styles = list(block.styles) or [TextStyle(block.font, block.size, block.color, block.flags)]
    factor = (fontsize / block.size) if fontsize else 1.0
    free_below = _space_below(page, block.bbox)
    _remove_lines(page, block.extra.get("line_rects") or [block.bbox])
    resolver = FontResolver(doc)
    if not plain.strip():
        return {"font": block.font, "source": "incorporato", "scale": 1.0, "fits": True}

    # Un font per ogni stile usato, scelto in base ai caratteri che deve scrivere
    used = sorted({sid for _t, sid in runs})
    arch = pymupdf.Archive()
    families: dict[int, str] = {}
    faces = []
    added: dict[str, str] = {}
    sources = []
    for sid in used:
        st = styles[sid]
        text_for = "".join(t for t, s in runs if s == sid)
        choice = resolver.choose(page, st.font, st.flags, text_for)
        choice = FontChoice(choice.alias, without_ligatures(choice.buffer), choice.source, choice.label)
        sources.append(choice.source)
        if choice.alias not in added:
            ext = "otf" if choice.buffer[:4] == b"OTTO" else "ttf"
            fname = f"f{len(added)}.{ext}"
            arch.add(choice.buffer, fname)
            added[choice.alias] = f"F{len(added)}"
            faces.append(f"@font-face {{font-family: {added[choice.alias]}; src: url({fname});}}")
        families[sid] = added[choice.alias]
    parts = []
    for t, sid in runs:
        st = styles[sid]
        c = st.color if color is None else color
        parts.append(f'<span style="font-family: {families[sid]}; font-size: {st.size * factor:.2f}px; '
                     f'color: {_css_color(c)}">{_html_escape(t)}</span>')
    pitch = (block.pitch or block.size * block.line_height) * factor
    css = (" ".join(faces) + f" * {{margin: 0; padding: 0;}} "
           f"div {{text-align: {align or block.align}; line-height: {pitch:.2f}px;}}")
    html = f"<div>{''.join(parts)}</div>"
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
    worst = "standard" if "standard" in sources else "sistema" if "sistema" in sources else "incorporato"
    return {"font": block.font, "source": worst, "scale": scale, "fits": spare >= 0}


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


def _match_spans(doc: pymupdf.Document, pno: int, pattern) -> list[dict]:
    page = doc[pno]
    spans = []
    for b in page.get_text("dict", flags=pymupdf.TEXTFLAGS_TEXT)["blocks"]:
        for ln in b.get("lines", []):
            if abs(ln["dir"][1]) > 0.01:
                continue
            spans.extend(s for s in ln["spans"] if pattern.search(s["text"]))
    return spans


def _pattern(query: str, match_case: bool):
    return re.compile(re.escape(query), 0 if match_case else re.IGNORECASE)


def count_matches(doc: pymupdf.Document, query: str, pages=None, match_case: bool = True) -> int:
    """Occorrenze che find_replace sostituirebbe (stessi criteri)."""
    if not query:
        return 0
    pattern = _pattern(query, match_case)
    return sum(len(pattern.findall(s["text"]))
               for pno in (pages if pages is not None else range(doc.page_count))
               for s in _match_spans(doc, pno, pattern))


def find_replace(doc: pymupdf.Document, query: str, replacement: str, pages=None,
                 match_case: bool = True) -> int:
    """Sostituisce ogni occorrenza riscrivendo lo span che la contiene. Ritorna le sostituzioni."""
    if not query:
        return 0
    count = 0
    pattern = _pattern(query, match_case)
    for pno in (pages if pages is not None else range(doc.page_count)):
        for s in _match_spans(doc, pno, pattern):
            new, n = pattern.subn(lambda _m: replacement, s["text"])
            if not n:
                continue
            # Mantiene gli spazi iniziali dello span per non spostare il testo
            replace_line_span(doc, pno, pymupdf.Rect(s["bbox"]), pymupdf.Point(s["origin"]), s["font"],
                              s["flags"], s["size"], _rgb(s["color"]), new.rstrip())
            count += n
    return count
