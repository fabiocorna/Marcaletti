"""Modello del documento PDF: tutte le operazioni di lettura/modifica, senza Qt.

Convenzione sulle coordinate: tutti i metodi che ricevono rettangoli o punti
lavorano nello spazio *non ruotato* della pagina (quello usato da PyMuPDF per
testo e annotazioni). Il visualizzatore converte dallo spazio mostrato a schermo
usando ``page.derotation_matrix``.
"""
from __future__ import annotations

import io
import os
from dataclasses import dataclass
from typing import Iterable, Sequence

import pymupdf

A4 = (595.0, 842.0)

# Font base-14 disponibili senza file esterni
BASE14 = {
    "Helvetica": "helv",
    "Helvetica grassetto": "hebo",
    "Helvetica corsivo": "heit",
    "Times": "tiro",
    "Times grassetto": "tibo",
    "Times corsivo": "tiit",
    "Courier": "cour",
    "Courier grassetto": "cobo",
}

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tif", ".tiff", ".webp", ".jxr", ".pnm")


@dataclass
class TextSpan:
    page: int
    bbox: pymupdf.Rect
    origin: pymupdf.Point
    text: str
    size: float
    color: tuple[float, float, float]
    font: str
    flags: int


def rgb_from_int(value: int) -> tuple[float, float, float]:
    return (((value >> 16) & 255) / 255, ((value >> 8) & 255) / 255, (value & 255) / 255)


def guess_base14(font: str, flags: int) -> str:
    """Sceglie il font base-14 più simile a quello originale di uno span."""
    name = font.lower()
    bold = bool(flags & 16) or "bold" in name or "black" in name or "heavy" in name
    italic = bool(flags & 2) or "italic" in name or "oblique" in name
    if bool(flags & 8) or "courier" in name or "mono" in name:
        return "cobo" if bold else "cour"
    if bool(flags & 4) or "times" in name or "serif" in name and "sans" not in name or "roman" in name:
        if bold and italic:
            return "tibi"
        return "tibo" if bold else ("tiit" if italic else "tiro")
    if bold and italic:
        return "hebi"
    return "hebo" if bold else ("heit" if italic else "helv")


class PdfDocument:
    """Documento PDF aperto nell'editor, con annulla/ripeti."""

    MAX_UNDO = 30

    def __init__(self, doc: pymupdf.Document, path: str | None = None):
        self.doc = doc
        self.path = path
        self.modified = False
        # (owner_pw, user_pw) da riapplicare al salvataggio, oppure None
        self.encryption: tuple[str, str] | None = None
        self._undo: list[bytes] = []
        self._redo: list[bytes] = []

    # ------------------------------------------------------------------ apertura
    @classmethod
    def new(cls, width: float = A4[0], height: float = A4[1], pages: int = 1) -> "PdfDocument":
        doc = pymupdf.open()
        for _ in range(max(1, pages)):
            doc.new_page(width=width, height=height)
        d = cls(doc)
        d.modified = True
        return d

    @classmethod
    def open(cls, path: str) -> "PdfDocument":
        """Apre un PDF (o un'immagine/XPS/EPUB, convertiti in PDF)."""
        src = pymupdf.open(path)
        if src.is_pdf:
            src.close()
            # Carica il file in memoria: su Windows un file tenuto aperto non può
            # essere sovrascritto, e l'utente deve poter salvare sopra l'originale.
            with open(path, "rb") as f:
                return cls(pymupdf.open("pdf", f.read()), path)
        # Formati non PDF: conversione in memoria
        pdf_bytes = src.convert_to_pdf()
        src.close()
        d = cls(pymupdf.open("pdf", pdf_bytes), None)
        d.modified = True
        return d

    @property
    def needs_password(self) -> bool:
        return bool(self.doc.needs_pass) and self.doc.is_encrypted

    def authenticate(self, password: str) -> bool:
        if not self.doc.authenticate(password):
            return False
        # Lavoriamo su una copia decifrata; la protezione viene riapplicata al salvataggio
        self.encryption = (password, password)
        data = self.doc.tobytes(encryption=pymupdf.PDF_ENCRYPT_NONE)
        self.doc = pymupdf.open("pdf", data)
        return True

    @classmethod
    def from_images(cls, paths: Sequence[str]) -> "PdfDocument":
        doc = pymupdf.open()
        for p in paths:
            img = pymupdf.open(p)
            pdf = pymupdf.open("pdf", img.convert_to_pdf())
            doc.insert_pdf(pdf)
            pdf.close()
            img.close()
        d = cls(doc)
        d.modified = True
        return d

    @property
    def page_count(self) -> int:
        return self.doc.page_count

    @property
    def title(self) -> str:
        return os.path.basename(self.path) if self.path else "Senza titolo.pdf"

    def page(self, index: int) -> pymupdf.Page:
        return self.doc[index]

    # ------------------------------------------------------------- annulla/ripeti
    def checkpoint(self) -> None:
        """Salva lo stato corrente prima di una modifica."""
        self._undo.append(self.doc.tobytes())
        if len(self._undo) > self.MAX_UNDO:
            self._undo.pop(0)
        self._redo.clear()
        self.modified = True

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    def undo(self) -> bool:
        if not self._undo:
            return False
        self._redo.append(self.doc.tobytes())
        self._replace(self._undo.pop())
        return True

    def redo(self) -> bool:
        if not self._redo:
            return False
        self._undo.append(self.doc.tobytes())
        self._replace(self._redo.pop())
        return True

    def _replace(self, data: bytes) -> None:
        old = self.doc
        self.doc = pymupdf.open("pdf", data)
        old.close()
        self.modified = True

    # ---------------------------------------------------------------- salvataggio
    def to_bytes(self, garbage: int = 3, encryption: tuple[str, str] | None | bool = True,
                 permissions: int | None = None) -> bytes:
        """Serializza il documento. ``encryption=True`` usa quella del documento."""
        if encryption is True:
            encryption = self.encryption
        kwargs: dict = dict(garbage=garbage, deflate=True)
        if encryption:
            owner, user = encryption
            kwargs.update(
                encryption=pymupdf.PDF_ENCRYPT_AES_256,
                owner_pw=owner or user,
                user_pw=user,
                permissions=permissions if permissions is not None else -1,
            )
        return self.doc.tobytes(**kwargs)

    def save(self, path: str | None = None) -> None:
        path = path or self.path
        if not path:
            raise ValueError("Percorso di salvataggio mancante")
        data = self.to_bytes()
        tmp = path + ".tmp"
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
        self.path = path
        self.modified = False

    def save_compressed(self, path: str, image_dpi: int | None = 150, image_quality: int = 70) -> tuple[int, int]:
        """Salva una copia ottimizzata. Ritorna (dimensione prima, dimensione dopo)."""
        before = len(self.to_bytes(garbage=0, encryption=False))
        work = pymupdf.open("pdf", self.doc.tobytes())
        if image_dpi and hasattr(work, "rewrite_images"):
            work.rewrite_images(dpi_threshold=image_dpi + 10, dpi_target=image_dpi, quality=image_quality)
        if hasattr(work, "subset_fonts"):
            try:
                work.subset_fonts()
            except Exception:
                pass
        kwargs: dict = dict(garbage=4, deflate=True, deflate_images=True, deflate_fonts=True, clean=True, use_objstms=1)
        if self.encryption:
            kwargs.update(encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw=self.encryption[0], user_pw=self.encryption[1])
        data = work.tobytes(**kwargs)
        work.close()
        with open(path, "wb") as f:
            f.write(data)
        return before, len(data)

    # --------------------------------------------------------------------- pagine
    def insert_blank_page(self, index: int, width: float | None = None, height: float | None = None) -> None:
        self.checkpoint()
        if width is None or height is None:
            ref = self.doc[min(max(index - 1, 0), self.page_count - 1)].rect if self.page_count else pymupdf.Rect(0, 0, *A4)
            width, height = ref.width, ref.height
        self.doc.new_page(pno=index, width=width, height=height)

    def delete_pages(self, indices: Iterable[int]) -> None:
        indices = sorted(set(indices))
        if not indices:
            return
        if len(indices) >= self.page_count:
            raise ValueError("Non è possibile eliminare tutte le pagine")
        self.checkpoint()
        self.doc.delete_pages(indices)

    def rotate_pages(self, indices: Iterable[int], delta: int) -> None:
        self.checkpoint()
        for i in indices:
            p = self.doc[i]
            p.set_rotation((p.rotation + delta) % 360)

    def move_page(self, src: int, dst: int) -> None:
        """Sposta la pagina ``src`` in modo che finisca in posizione ``dst``."""
        if src == dst:
            return
        self.checkpoint()
        # PyMuPDF inserisce *prima* di 'to'; -1 = in fondo
        if dst >= self.page_count - 1:
            self.doc.move_page(src, -1)
        elif dst > src:
            self.doc.move_page(src, dst + 1)
        else:
            self.doc.move_page(src, dst)

    def reorder(self, order: Sequence[int]) -> None:
        """Riordina le pagine secondo ``order`` (lista di indici attuali)."""
        if list(order) == list(range(self.page_count)):
            return
        self.checkpoint()
        self.doc.select(list(order))

    def duplicate_page(self, index: int) -> None:
        self.checkpoint()
        self.doc.fullcopy_page(index, index + 1)

    def insert_file(self, path: str, index: int) -> int:
        """Inserisce un altro PDF (o immagine) prima di ``index``. Ritorna le pagine aggiunte."""
        src = pymupdf.open(path)
        if not src.is_pdf:
            data = src.convert_to_pdf()
            src.close()
            src = pymupdf.open("pdf", data)
        if src.needs_pass:
            src.close()
            raise PermissionError(f"{os.path.basename(path)} è protetto da password")
        self.checkpoint()
        n = src.page_count
        self.doc.insert_pdf(src, start_at=index)
        src.close()
        return n

    def extract_pages(self, indices: Sequence[int], out_path: str) -> None:
        out = pymupdf.open()
        for i in indices:
            out.insert_pdf(self.doc, from_page=i, to_page=i)
        out.save(out_path, garbage=3, deflate=True)
        out.close()

    def split(self, ranges: Sequence[tuple[int, int]], out_dir: str, base: str) -> list[str]:
        """Divide il documento in più file secondo gli intervalli (inclusivi, base 0)."""
        paths = []
        for n, (a, b) in enumerate(ranges, 1):
            out = pymupdf.open()
            out.insert_pdf(self.doc, from_page=a, to_page=b)
            p = os.path.join(out_dir, f"{base}_{n:03d}.pdf")
            out.save(p, garbage=3, deflate=True)
            out.close()
            paths.append(p)
        return paths

    def crop_page(self, index: int, rect: pymupdf.Rect | None) -> None:
        """Ritaglia la pagina (rect in coordinate non ruotate); None ripristina."""
        self.checkpoint()
        p = self.doc[index]
        p.set_cropbox(p.mediabox if rect is None else rect & p.mediabox)

    # ---------------------------------------------------------------- annotazioni
    def add_text_markup(self, index: int, rect: pymupdf.Rect, kind: str = "highlight",
                        color: tuple[float, float, float] | None = None) -> bool:
        """Evidenzia/sottolinea/barra le parole nel rettangolo. Ritorna False se non c'è testo."""
        page = self.doc[index]
        words = [w for w in page.get_text("words") if pymupdf.Rect(w[:4]).intersects(rect)]
        if not words:
            return False
        self.checkpoint()
        # Unisce le parole della stessa riga in un unico quadrilatero
        lines: dict[tuple[int, int], pymupdf.Rect] = {}
        for w in words:
            key = (w[5], w[6])
            r = pymupdf.Rect(w[:4])
            lines[key] = lines[key] | r if key in lines else r
        quads = [r.quad for r in lines.values()]
        adder = {
            "highlight": page.add_highlight_annot,
            "underline": page.add_underline_annot,
            "strikeout": page.add_strikeout_annot,
            "squiggly": page.add_squiggly_annot,
        }[kind]
        annot = adder(quads)
        if color:
            annot.set_colors(stroke=color)
            annot.update()
        return True

    def add_area_highlight(self, index: int, rect: pymupdf.Rect, color=(1, 1, 0)) -> None:
        self.checkpoint()
        annot = self.doc[index].add_highlight_annot(rect.quad)
        annot.set_colors(stroke=color)
        annot.update()

    def add_shape(self, index: int, kind: str, rect: pymupdf.Rect, color=(1, 0, 0), width: float = 1.5,
                  fill=None, start: pymupdf.Point | None = None, end: pymupdf.Point | None = None) -> None:
        self.checkpoint()
        page = self.doc[index]
        if kind == "rect":
            annot = page.add_rect_annot(rect)
        elif kind == "ellipse":
            annot = page.add_circle_annot(rect)
        elif kind in ("line", "arrow"):
            annot = page.add_line_annot(start, end)
            if kind == "arrow":
                annot.set_line_ends(pymupdf.PDF_ANNOT_LE_NONE, pymupdf.PDF_ANNOT_LE_OPEN_ARROW)
        else:
            raise ValueError(kind)
        annot.set_colors(stroke=color, fill=fill)
        annot.set_border(width=width)
        annot.update()

    def add_ink(self, index: int, strokes: list[list[tuple[float, float]]], color=(0, 0, 1), width: float = 2) -> None:
        if not strokes:
            return
        self.checkpoint()
        annot = self.doc[index].add_ink_annot(strokes)
        annot.set_colors(stroke=color)
        annot.set_border(width=width)
        annot.update()

    def add_note(self, index: int, point: pymupdf.Point, text: str, color=(1, 0.85, 0)) -> None:
        self.checkpoint()
        annot = self.doc[index].add_text_annot(point, text, icon="Comment")
        annot.set_colors(stroke=color)
        annot.update()

    def add_text_box(self, index: int, rect: pymupdf.Rect, text: str, fontsize: float = 12,
                     color=(0, 0, 0), fontname: str = "helv", flatten: bool = True, align: int = 0) -> None:
        """Aggiunge testo. Con ``flatten`` il testo diventa parte del contenuto della pagina,
        altrimenti resta un'annotazione di testo libero modificabile."""
        self.checkpoint()
        page = self.doc[index]
        if flatten:
            rc = page.insert_textbox(rect, text, fontsize=fontsize, fontname=fontname, color=color,
                                     rotate=page.rotation, align=align)
            if rc < 0:
                # Il riquadro è troppo piccolo: lo allarga verso il basso
                big = pymupdf.Rect(rect.x0, rect.y0, max(rect.x1, rect.x0 + 50), rect.y1 + (-rc) + fontsize * 2)
                page.insert_textbox(big, text, fontsize=fontsize, fontname=fontname, color=color,
                                    rotate=page.rotation, align=align)
        else:
            annot = page.add_freetext_annot(rect, text, fontsize=fontsize, fontname=fontname,
                                            text_color=color, rotate=page.rotation, align=align)
            annot.update()

    def insert_image(self, index: int, rect: pymupdf.Rect, filename: str | None = None,
                     stream: bytes | None = None, keep_proportion: bool = True) -> None:
        self.checkpoint()
        page = self.doc[index]
        page.insert_image(rect, filename=filename, stream=stream, keep_proportion=keep_proportion,
                          rotate=page.rotation)

    def whiteout(self, index: int, rect: pymupdf.Rect, color=(1, 1, 1)) -> None:
        """Copre un'area con un rettangolo pieno (il contenuto sotto resta nel file)."""
        self.checkpoint()
        self.doc[index].draw_rect(rect, color=None, fill=color, overlay=True)

    def redact(self, index: int, rect: pymupdf.Rect, fill=(0, 0, 0)) -> None:
        """Oscuramento definitivo: rimuove testo e immagini sotto il rettangolo."""
        self.checkpoint()
        page = self.doc[index]
        page.add_redact_annot(rect, fill=fill)
        page.apply_redactions()

    def annotation_at(self, index: int, point: pymupdf.Point):
        page = self.doc[index]
        hits = [a for a in page.annots() if a.rect.contains(point)]
        if not hits:
            return None
        return min(hits, key=lambda a: a.rect.width * a.rect.height)

    def delete_annotation_at(self, index: int, point: pymupdf.Point) -> bool:
        annot = self.annotation_at(index, point)
        if annot is None:
            return False
        xref = annot.xref
        self.checkpoint()
        page = self.doc[index]
        for a in page.annots():
            if a.xref == xref:
                page.delete_annot(a)
                return True
        return False

    def set_annotation_text(self, index: int, xref: int, text: str) -> None:
        self.checkpoint()
        for a in self.doc[index].annots():
            if a.xref == xref:
                a.set_info(content=text)
                a.update()
                return

    def flatten_annotations(self) -> None:
        """Rende le annotazioni parte del contenuto (non più modificabili)."""
        self.checkpoint()
        self.doc.bake(annots=True, widgets=False)

    # ----------------------------------------------------------- modifica testo
    def span_at(self, index: int, point: pymupdf.Point) -> TextSpan | None:
        page = self.doc[index]
        best = None
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                for span in line["spans"]:
                    r = pymupdf.Rect(span["bbox"])
                    if r.contains(point) and span["text"].strip():
                        if best is None or r.width * r.height < best.bbox.width * best.bbox.height:
                            best = TextSpan(index, r, pymupdf.Point(span["origin"]), span["text"],
                                            span["size"], rgb_from_int(span["color"]), span["font"], span["flags"])
        return best

    def replace_span(self, span: TextSpan, new_text: str, fontsize: float | None = None,
                     color=None, fontname: str | None = None) -> None:
        """Sostituisce il testo di uno span: cancella l'originale e riscrive il nuovo."""
        self.checkpoint()
        page = self.doc[span.page]
        r = pymupdf.Rect(span.bbox)
        # Riduce leggermente il riquadro per non toccare le righe adiacenti
        shrink = r.height * 0.2
        r.y0 += shrink
        r.y1 -= shrink
        page.add_redact_annot(r, fill=False)
        page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE,
                              graphics=getattr(pymupdf, "PDF_REDACT_LINE_ART_NONE", 0))
        if new_text:
            page.insert_text(span.origin, new_text, fontsize=fontsize or span.size,
                             fontname=fontname or guess_base14(span.font, span.flags),
                             color=color if color is not None else span.color,
                             rotate=page.rotation)

    # --------------------------------------------------------------- strumenti
    def search(self, query: str) -> list[tuple[int, pymupdf.Rect]]:
        results = []
        if not query:
            return results
        for i, page in enumerate(self.doc):
            for r in page.search_for(query):
                results.append((i, r))
        return results

    def text_in_rect(self, index: int, rect: pymupdf.Rect) -> str:
        return self.doc[index].get_text("text", clip=rect).strip()

    def add_watermark(self, text: str, fontsize: float = 60, color=(0.6, 0.6, 0.6),
                      opacity: float = 0.3, angle: float = 45, pages: Iterable[int] | None = None) -> None:
        self.checkpoint()
        font = pymupdf.Font("helv")
        for i in (pages if pages is not None else range(self.page_count)):
            page = self.doc[i]
            # Lavora nelle coordinate non ruotate, compensando la rotazione della pagina
            vis = page.rect
            center = pymupdf.Point((vis.x0 + vis.x1) / 2, (vis.y0 + vis.y1) / 2) * page.derotation_matrix
            width = font.text_length(text, fontsize)
            tw = pymupdf.TextWriter(page.rect, opacity=opacity, color=color)
            tw.append(pymupdf.Point(center.x - width / 2, center.y + fontsize / 3), text, font=font, fontsize=fontsize)
            tw.write_text(page, morph=(center, pymupdf.Matrix(angle + page.rotation)))

    def add_page_numbers(self, fmt: str = "Pagina {n} di {tot}", fontsize: float = 10,
                         position: str = "bottom-center", margin: float = 28, start: int = 1) -> None:
        self.checkpoint()
        tot = self.page_count
        for i, page in enumerate(self.doc):
            text = fmt.format(n=i + start, tot=tot + start - 1)
            vis = page.rect  # coordinate come visualizzate
            width = pymupdf.get_text_length(text, "helv", fontsize)
            vert, horiz = position.split("-")
            y = vis.y1 - margin if vert == "bottom" else vis.y0 + margin + fontsize
            x = {"left": vis.x0 + margin, "center": (vis.x0 + vis.x1 - width) / 2,
                 "right": vis.x1 - margin - width}[horiz]
            pt = pymupdf.Point(x, y) * page.derotation_matrix
            page.insert_text(pt, text, fontsize=fontsize, fontname="helv", color=(0, 0, 0), rotate=page.rotation)

    def get_metadata(self) -> dict:
        return dict(self.doc.metadata or {})

    def set_metadata(self, meta: dict) -> None:
        self.checkpoint()
        current = self.get_metadata()
        current.update(meta)
        self.doc.set_metadata(current)

    # ------------------------------------------------------------------- moduli
    def widget_at(self, index: int, point: pymupdf.Point):
        for w in self.doc[index].widgets() or []:
            if w.rect.contains(point):
                return w
        return None

    def set_widget_value(self, index: int, xref: int, value) -> None:
        self.checkpoint()
        for w in self.doc[index].widgets() or []:
            if w.xref == xref:
                w.field_value = value
                w.update()
                return

    def has_forms(self) -> bool:
        return bool(self.doc.is_form_pdf)

    # -------------------------------------------------------------- esportazione
    def export_images(self, out_dir: str, dpi: int = 150, fmt: str = "png",
                      pages: Iterable[int] | None = None) -> list[str]:
        base = os.path.splitext(self.title)[0]
        paths = []
        for i in (pages if pages is not None else range(self.page_count)):
            pix = self.doc[i].get_pixmap(dpi=dpi, annots=True)
            p = os.path.join(out_dir, f"{base}_p{i + 1:03d}.{fmt}")
            pix.save(p)
            paths.append(p)
        return paths

    def export_text(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            for i, page in enumerate(self.doc):
                f.write(f"===== Pagina {i + 1} =====\n")
                f.write(page.get_text("text", sort=True))
                f.write("\n")

    def export_docx(self, path: str) -> None:
        try:
            from pdf2docx import Converter
        except ImportError as exc:  # opzionale
            raise RuntimeError("Per esportare in Word installare il pacchetto 'pdf2docx'") from exc
        tmp = io.BytesIO(self.doc.tobytes())
        cv = Converter(stream=tmp.getvalue())
        try:
            cv.convert(path)
        finally:
            cv.close()

    def ocr(self, language: str = "ita+eng", dpi: int = 300) -> None:
        """Aggiunge uno strato di testo ricercabile alle pagine scansionate (richiede Tesseract)."""
        self.checkpoint()
        out = pymupdf.open()
        for page in self.doc:
            pix = page.get_pixmap(dpi=dpi)
            pdfbytes = pix.pdfocr_tobytes(language=language)
            ocr_page = pymupdf.open("pdf", pdfbytes)
            out.insert_pdf(ocr_page)
            ocr_page.close()
        old = self.doc
        self.doc = out
        old.close()

    def close(self) -> None:
        self.doc.close()


def merge_files(paths: Sequence[str], out_path: str) -> int:
    out = pymupdf.open()
    for p in paths:
        src = pymupdf.open(p)
        if not src.is_pdf:
            data = src.convert_to_pdf()
            src.close()
            src = pymupdf.open("pdf", data)
        out.insert_pdf(src)
        src.close()
    n = out.page_count
    out.save(out_path, garbage=3, deflate=True)
    out.close()
    return n


def parse_page_ranges(text: str, page_count: int) -> list[tuple[int, int]]:
    """Converte "1-3, 5, 8-" in intervalli base 0 inclusivi."""
    ranges = []
    for part in text.replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            a = int(a) if a.strip() else 1
            b = int(b) if b.strip() else page_count
        else:
            a = b = int(part)
        if a < 1 or b > page_count or a > b:
            raise ValueError(f"Intervallo non valido: {part}")
        ranges.append((a - 1, b - 1))
    if not ranges:
        raise ValueError("Nessun intervallo indicato")
    return ranges
