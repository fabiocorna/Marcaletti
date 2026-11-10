"""Finestra di stampa con anteprima (sul modello di Acrobat).

A sinistra stampante e opzioni, a destra l'anteprima del foglio: carta, area
stampabile e pagina posizionata come uscirà, sfogliabile tra le pagine scelte.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import pymupdf
from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPageLayout, QPen, QPixmap, QTransform
from PySide6.QtPrintSupport import QPageSetupDialog, QPrinter, QPrinterInfo
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFormLayout,
                               QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
                               QProgressDialog, QPushButton, QRadioButton, QSpinBox, QToolButton, QVBoxLayout,
                               QWidget)

from .document import PdfDocument, parse_page_ranges

FIT, ACTUAL, SHRINK, CUSTOM = "fit", "actual", "shrink", "custom"
ALL, CURRENT, SELECTED, RANGE = "all", "current", "selected", "range"


@dataclass
class PrintOptions:
    pages_mode: str = ALL
    ranges: str = ""
    subset: str = "all"        # all, odd, even (rispetto alle pagine scelte)
    reverse: bool = False
    sizing: str = FIT
    scale: float = 100.0
    auto_rotate: bool = True
    grayscale: bool = False
    annotations: bool = True
    duplex: str = "none"       # none, long, short
    copies: int = 1
    collate: bool = True


# --------------------------------------------------------------- calcoli puri
def compute_pages(opts: PrintOptions, count: int, current: int, selected: list[int]) -> list[int]:
    """Indici (base 0) delle pagine da stampare, nell'ordine di stampa."""
    if opts.pages_mode == CURRENT:
        pages = [current]
    elif opts.pages_mode == SELECTED:
        pages = sorted(set(selected)) or [current]
    elif opts.pages_mode == RANGE:
        pages = [p for a, b in parse_page_ranges(opts.ranges, count) for p in range(a, b + 1)]
    else:
        pages = list(range(count))
    if opts.subset == "odd":
        pages = [p for p in pages if (p + 1) % 2 == 1]
    elif opts.subset == "even":
        pages = [p for p in pages if (p + 1) % 2 == 0]
    if opts.reverse:
        pages.reverse()
    return pages


def placement(page_w: float, page_h: float, paper_w: float, paper_h: float, printable: tuple,
              sizing: str = FIT, scale: float = 100.0, auto_rotate: bool = True):
    """Dove va la pagina sul foglio, in punti: (ruota_90, x, y, larghezza, altezza, scala)."""
    rotate = False
    if auto_rotate and abs(page_w - page_h) > 1 and (page_w > page_h) != (paper_w > paper_h):
        rotate = True
        page_w, page_h = page_h, page_w
    ax, ay, aw, ah = printable
    fit = min(aw / page_w, ah / page_h)
    s = {FIT: fit, ACTUAL: 1.0, SHRINK: min(1.0, fit), CUSTOM: scale / 100.0}[sizing]
    w, h = page_w * s, page_h * s
    return rotate, ax + (aw - w) / 2, ay + (ah - h) / 2, w, h, s


def sheets_needed(n_pages: int, copies: int, duplex: bool) -> int:
    per_copy = math.ceil(n_pages / 2) if duplex else n_pages
    return per_copy * copies


def render_page(page: pymupdf.Page, dpi: float, grayscale: bool, annotations: bool) -> QImage:
    cs = pymupdf.csGRAY if grayscale else pymupdf.csRGB
    pix = page.get_pixmap(dpi=dpi, colorspace=cs, annots=annotations, alpha=False)
    fmt = QImage.Format_Grayscale8 if pix.n == 1 else QImage.Format_RGB888
    return QImage(pix.samples, pix.width, pix.height, pix.stride, fmt).copy()


def paper_geometry(printer: QPrinter) -> tuple[float, float, tuple]:
    layout = printer.pageLayout()
    full = layout.fullRect(QPageLayout.Point)
    paint = layout.paintRect(QPageLayout.Point)
    return full.width(), full.height(), (paint.x(), paint.y(), paint.width(), paint.height())


def configure_printer(printer: QPrinter, opts: PrintOptions, title: str) -> None:
    printer.setDocName(title)
    printer.setFullPage(True)
    printer.setCopyCount(max(1, opts.copies))
    printer.setCollateCopies(opts.collate)
    printer.setColorMode(QPrinter.GrayScale if opts.grayscale else QPrinter.Color)
    printer.setDuplex({"none": QPrinter.DuplexNone, "long": QPrinter.DuplexLongSide,
                       "short": QPrinter.DuplexShortSide}[opts.duplex])


def print_pages(doc: PdfDocument, pages: list[int], printer: QPrinter, opts: PrintOptions,
                progress=None) -> int:
    """Stampa le pagine sulla stampante già configurata. Ritorna le pagine stampate."""
    paper_w, paper_h, printable = paper_geometry(printer)
    dpi = min(printer.resolution(), 300)
    px_per_pt = printer.resolution() / 72.0
    painter = QPainter()
    if not painter.begin(printer):
        raise RuntimeError("Impossibile avviare la stampa: controlla che la stampante sia disponibile")
    done = 0
    try:
        for n, i in enumerate(pages):
            if progress is not None and not progress(n, len(pages)):
                break
            if n:
                printer.newPage()
            page = doc.page(i)
            rotate, x, y, w, h, _s = placement(page.rect.width, page.rect.height, paper_w, paper_h, printable,
                                               opts.sizing, opts.scale, opts.auto_rotate)
            img = render_page(page, dpi, opts.grayscale, opts.annotations)
            if rotate:
                img = img.transformed(QTransform().rotate(90))
            target = QRectF(x * px_per_pt, y * px_per_pt, w * px_per_pt, h * px_per_pt)
            painter.drawImage(target, img)
            done += 1
    finally:
        painter.end()
    return done


# ------------------------------------------------------------------ anteprima
class SheetPreview(QWidget):
    """Disegna il foglio con la pagina posizionata come verrà stampata."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(360, 460)
        self._paper = (595.0, 842.0, (18, 18, 559, 806))
        self._page_img: QImage | None = None
        self._place = None

    def set_sheet(self, paper_w, paper_h, printable, page_img, place) -> None:
        self._paper = (paper_w, paper_h, printable)
        self._page_img = page_img
        self._place = place
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(420, 560)

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.fillRect(self.rect(), QColor("#e9ebee"))
        pw, ph, (ax, ay, aw, ah) = self._paper
        k = min((self.width() - 30) / pw, (self.height() - 30) / ph)
        ox, oy = (self.width() - pw * k) / 2, (self.height() - ph * k) / 2
        p.fillRect(QRectF(ox + 4, oy + 4, pw * k, ph * k), QColor(0, 0, 0, 50))  # ombra
        p.fillRect(QRectF(ox, oy, pw * k, ph * k), Qt.white)
        p.setPen(QPen(QColor("#c0c4ca"), 1, Qt.DashLine))
        p.drawRect(QRectF(ox + ax * k, oy + ay * k, aw * k, ah * k))
        if self._page_img is not None and self._place is not None:
            rotate, x, y, w, h, _s = self._place
            img = self._page_img.transformed(QTransform().rotate(90)) if rotate else self._page_img
            target = QRectF(ox + x * k, oy + y * k, w * k, h * k)
            p.save()
            p.setClipRect(QRectF(ox, oy, pw * k, ph * k))  # ciò che esce dal foglio non si stampa
            p.drawImage(target, img)
            p.restore()
            p.setPen(QPen(QColor("#8a8f98"), 0.8))
            p.drawRect(target.intersected(QRectF(ox, oy, pw * k, ph * k)))
        p.end()


# ----------------------------------------------------------------- finestra
class PrintDialog(QDialog):
    printed = Signal(int)

    def __init__(self, doc: PdfDocument, current: int, selected: list[int], settings=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Stampa")
        self.doc = doc
        self.current = current
        self.selected = selected
        self.settings = settings
        self.printer: QPrinter | None = None
        self._pages: list[int] = []
        self._preview_index = 0
        self._img_cache: dict = {}

        root = QHBoxLayout(self)
        left = QVBoxLayout()
        root.addLayout(left, 0)

        # Stampante
        g = QGroupBox("Stampante")
        f = QFormLayout(g)
        self.printer_combo = QComboBox()
        names = QPrinterInfo.availablePrinterNames()
        default = QPrinterInfo.defaultPrinterName()
        last = settings.value("print/printer", "") if settings else ""
        self.printer_combo.addItems(names or ["(nessuna stampante installata)"])
        pick = last if last in names else default
        if pick in names:
            self.printer_combo.setCurrentText(pick)
        row = QHBoxLayout()
        row.addWidget(self.printer_combo, 1)
        self.props_btn = QPushButton("Carta…")
        self.props_btn.setToolTip("Formato carta, orientamento e margini")
        row.addWidget(self.props_btn)
        f.addRow(row)
        self.copies = QSpinBox(minimum=1, maximum=999, value=1)
        self.collate = QCheckBox("Fascicola")
        self.collate.setChecked(True)
        crow = QHBoxLayout()
        crow.addWidget(self.copies)
        crow.addWidget(self.collate)
        crow.addStretch()
        f.addRow("Copie:", crow)
        left.addWidget(g)

        # Pagine
        g = QGroupBox("Pagine da stampare")
        grid = QGridLayout(g)
        self.pages_group = QButtonGroup(self)
        self.r_all = QRadioButton(f"Tutte ({doc.page_count})")
        self.r_current = QRadioButton(f"Pagina corrente ({current + 1})")
        self.r_selected = QRadioButton(f"Pagine selezionate nelle miniature ({len(selected)})")
        self.r_selected.setEnabled(len(selected) > 1)
        self.r_range = QRadioButton("Pagine:")
        self.range_edit = QLineEdit()
        self.range_edit.setPlaceholderText("es. 1-3, 5, 8-")
        for k, r in enumerate((self.r_all, self.r_current, self.r_selected)):
            self.pages_group.addButton(r)
            grid.addWidget(r, k, 0, 1, 2)
        self.pages_group.addButton(self.r_range)
        grid.addWidget(self.r_range, 3, 0)
        grid.addWidget(self.range_edit, 3, 1)
        self.range_error = QLabel()
        self.range_error.setStyleSheet("color:#b00020")
        grid.addWidget(self.range_error, 4, 0, 1, 2)
        self.subset = QComboBox()
        self.subset.addItem("Tutte le pagine scelte", "all")
        self.subset.addItem("Solo pagine dispari", "odd")
        self.subset.addItem("Solo pagine pari", "even")
        grid.addWidget(QLabel("Stampa:"), 5, 0)
        grid.addWidget(self.subset, 5, 1)
        self.reverse = QCheckBox("Ordine inverso")
        grid.addWidget(self.reverse, 6, 0, 1, 2)
        (self.r_selected if len(selected) > 1 else self.r_all).setChecked(True)
        left.addWidget(g)

        # Dimensioni
        g = QGroupBox("Dimensioni e orientamento")
        grid = QGridLayout(g)
        self.sizing_group = QButtonGroup(self)
        self.s_fit = QRadioButton("Adatta al foglio")
        self.s_actual = QRadioButton("Dimensioni reali (100%)")
        self.s_shrink = QRadioButton("Riduci solo le pagine più grandi del foglio")
        self.s_custom = QRadioButton("Scala personalizzata:")
        self.scale = QDoubleSpinBox(minimum=10, maximum=400, value=100, suffix=" %", decimals=0)
        for k, r in enumerate((self.s_fit, self.s_actual, self.s_shrink)):
            self.sizing_group.addButton(r)
            grid.addWidget(r, k, 0, 1, 2)
        self.sizing_group.addButton(self.s_custom)
        grid.addWidget(self.s_custom, 3, 0)
        grid.addWidget(self.scale, 3, 1)
        self.auto_rotate = QCheckBox("Ruota automaticamente in base al foglio")
        self.auto_rotate.setChecked(True)
        grid.addWidget(self.auto_rotate, 4, 0, 1, 2)
        self.s_fit.setChecked(True)
        left.addWidget(g)

        # Opzioni
        g = QGroupBox("Opzioni")
        f = QFormLayout(g)
        self.duplex = QComboBox()
        self.duplex.addItem("Solo fronte", "none")
        self.duplex.addItem("Fronte-retro (lato lungo)", "long")
        self.duplex.addItem("Fronte-retro (lato corto)", "short")
        f.addRow("Fronte-retro:", self.duplex)
        self.gray = QCheckBox("Bianco e nero (scala di grigi)")
        self.annots = QCheckBox("Stampa commenti, evidenziazioni e timbri")
        self.annots.setChecked(True)
        f.addRow(self.gray)
        f.addRow(self.annots)
        left.addWidget(g)
        left.addStretch()

        # Anteprima
        right = QVBoxLayout()
        root.addLayout(right, 1)
        right.addWidget(QLabel("<b>Anteprima</b>"))
        self.preview = SheetPreview()
        right.addWidget(self.preview, 1)
        nav = QHBoxLayout()
        self.first_btn = QToolButton(text="⏮")
        self.prev_btn = QToolButton(text="◀")
        self.nav_label = QLabel()
        self.nav_label.setAlignment(Qt.AlignCenter)
        self.next_btn = QToolButton(text="▶")
        self.last_btn = QToolButton(text="⏭")
        for w_ in (self.first_btn, self.prev_btn):
            nav.addWidget(w_)
        nav.addWidget(self.nav_label, 1)
        for w_ in (self.next_btn, self.last_btn):
            nav.addWidget(w_)
        right.addLayout(nav)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        right.addWidget(self.summary)
        buttons = QHBoxLayout()
        buttons.addStretch()
        self.print_btn = QPushButton("Stampa")
        self.print_btn.setDefault(True)
        cancel = QPushButton("Annulla")
        buttons.addWidget(self.print_btn)
        buttons.addWidget(cancel)
        right.addLayout(buttons)

        # Collegamenti
        self.printer_combo.currentIndexChanged.connect(self._printer_changed)
        self.props_btn.clicked.connect(self._page_setup)
        for w_ in (self.r_all, self.r_current, self.r_selected, self.r_range, self.reverse, self.s_fit,
                   self.s_actual, self.s_shrink, self.s_custom, self.auto_rotate, self.gray, self.annots):
            w_.toggled.connect(self._refresh)
        for w_ in (self.subset, self.duplex):
            w_.currentIndexChanged.connect(self._refresh)
        self.copies.valueChanged.connect(self._refresh)
        self.scale.valueChanged.connect(lambda _v: (self.s_custom.setChecked(True), self._refresh()))
        self.range_edit.textEdited.connect(lambda _t: (self.r_range.setChecked(True), self._refresh()))
        self.first_btn.clicked.connect(lambda: self._go(0))
        self.prev_btn.clicked.connect(lambda: self._go(self._preview_index - 1))
        self.next_btn.clicked.connect(lambda: self._go(self._preview_index + 1))
        self.last_btn.clicked.connect(lambda: self._go(len(self._pages) - 1))
        self.print_btn.clicked.connect(self._print)
        cancel.clicked.connect(self.reject)
        self._printer_changed()
        self.resize(980, 700)

    # ------------------------------------------------------------- stato
    def options(self) -> PrintOptions:
        mode = (ALL if self.r_all.isChecked() else CURRENT if self.r_current.isChecked()
                else SELECTED if self.r_selected.isChecked() else RANGE)
        sizing = (FIT if self.s_fit.isChecked() else ACTUAL if self.s_actual.isChecked()
                  else SHRINK if self.s_shrink.isChecked() else CUSTOM)
        return PrintOptions(pages_mode=mode, ranges=self.range_edit.text(), subset=self.subset.currentData(),
                            reverse=self.reverse.isChecked(), sizing=sizing, scale=self.scale.value(),
                            auto_rotate=self.auto_rotate.isChecked(), grayscale=self.gray.isChecked(),
                            annotations=self.annots.isChecked(), duplex=self.duplex.currentData(),
                            copies=self.copies.value(), collate=self.collate.isChecked())

    def _printer_changed(self) -> None:
        name = self.printer_combo.currentText()
        if name in QPrinterInfo.availablePrinterNames():
            self.printer = QPrinter(QPrinterInfo.printerInfo(name), QPrinter.HighResolution)
        else:
            self.printer = QPrinter(QPrinter.HighResolution)  # senza stampanti: solo anteprima
        self._refresh()

    def _page_setup(self) -> None:
        if self.printer is not None and QPageSetupDialog(self.printer, self).exec():
            self._refresh()

    def _refresh(self, *_args) -> None:
        opts = self.options()
        try:
            self._pages = compute_pages(opts, self.doc.page_count, self.current, self.selected)
            self.range_error.setText("")
        except ValueError as exc:
            self._pages = []
            self.range_error.setText(str(exc) if opts.pages_mode == RANGE and opts.ranges.strip()
                                     else "Indica le pagine, es. 1-3, 5, 8-")
        n = len(self._pages)
        has_printer = self.printer_combo.currentText() in QPrinterInfo.availablePrinterNames()
        self.print_btn.setEnabled(n > 0 and has_printer)
        self._preview_index = min(self._preview_index, max(0, n - 1))
        sheets = sheets_needed(n, opts.copies, opts.duplex != "none")
        if n:
            self.summary.setText(f"Verranno stampate <b>{n}</b> pagine"
                                 + (f" × {opts.copies} copie" if opts.copies > 1 else "")
                                 + f" su <b>{sheets}</b> fogli"
                                 + (" (fronte-retro)" if opts.duplex != "none" else "") + ".")
        else:
            self.summary.setText("Nessuna pagina da stampare.")
        self._update_preview()

    def _go(self, index: int) -> None:
        if self._pages:
            self._preview_index = max(0, min(index, len(self._pages) - 1))
            self._update_preview()

    def _update_preview(self) -> None:
        n = len(self._pages)
        for b in (self.first_btn, self.prev_btn):
            b.setEnabled(self._preview_index > 0)
        for b in (self.next_btn, self.last_btn):
            b.setEnabled(self._preview_index < n - 1)
        paper_w, paper_h, printable = paper_geometry(self.printer)
        if not n:
            self.nav_label.setText("—")
            self.preview.set_sheet(paper_w, paper_h, printable, None, None)
            return
        opts = self.options()
        i = self._pages[self._preview_index]
        page = self.doc.page(i)
        self.nav_label.setText(f"Foglio {self._preview_index + 1} di {n} — pagina {i + 1} del documento")
        key = (i, opts.grayscale, opts.annotations)
        if key not in self._img_cache:
            self._img_cache[key] = render_page(page, 60, opts.grayscale, opts.annotations)
        place = placement(page.rect.width, page.rect.height, paper_w, paper_h, printable,
                          opts.sizing, opts.scale, opts.auto_rotate)
        self.preview.set_sheet(paper_w, paper_h, printable, self._img_cache[key], place)
        if place[5] < 0.995 or place[5] > 1.005:
            self.nav_label.setText(self.nav_label.text() + f" — scala {place[5] * 100:.0f}%")

    # ------------------------------------------------------------- stampa
    def _print(self) -> None:
        opts = self.options()
        if not self._pages or self.printer is None:
            return
        configure_printer(self.printer, opts, self.doc.title)
        progress = QProgressDialog("Stampa in corso…", "Annulla", 0, len(self._pages), self)
        progress.setWindowModality(Qt.WindowModal)

        def step(n, total):
            progress.setValue(n)
            progress.setLabelText(f"Invio della pagina {n + 1} di {total} alla stampante…")
            return not progress.wasCanceled()
        try:
            done = print_pages(self.doc, self._pages, self.printer, opts, step)
        except Exception as exc:
            progress.close()
            QMessageBox.critical(self, "Stampa", str(exc))
            return
        progress.close()
        if self.settings is not None:
            self.settings.setValue("print/printer", self.printer_combo.currentText())
        self.printed.emit(done)
        self.accept()
