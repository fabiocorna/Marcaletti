"""Finestre di dialogo dell'applicazione."""
from __future__ import annotations

import os

import pymupdf
from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QPointF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QColorDialog, QComboBox, QDialog,
                               QDialogButtonBox, QDoubleSpinBox, QFileDialog, QFormLayout, QHBoxLayout,
                               QLabel, QLineEdit, QListWidget, QPlainTextEdit, QPushButton, QRadioButton,
                               QSlider, QSpinBox, QTabWidget, QVBoxLayout, QWidget)

from .document import BASE14, IMAGE_EXTENSIONS


class ColorButton(QPushButton):
    def __init__(self, color: QColor, parent=None):
        super().__init__(parent)
        self.setFixedWidth(60)
        self.set_color(color)
        self.clicked.connect(self._pick)

    def set_color(self, color: QColor) -> None:
        self.color = QColor(color)
        self.setStyleSheet(f"background-color: {self.color.name()}; border: 1px solid #888; min-height: 20px;")

    def _pick(self) -> None:
        c = QColorDialog.getColor(self.color, self, "Scegli colore")
        if c.isValid():
            self.set_color(c)

    def rgb(self) -> tuple[float, float, float]:
        return (self.color.redF(), self.color.greenF(), self.color.blueF())


def _buttons(dialog: QDialog) -> QDialogButtonBox:
    box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    box.button(QDialogButtonBox.Ok).setText("OK")
    box.button(QDialogButtonBox.Cancel).setText("Annulla")
    box.accepted.connect(dialog.accept)
    box.rejected.connect(dialog.reject)
    return box


class TextDialog(QDialog):
    """Inserimento o modifica di testo."""

    def __init__(self, parent=None, title="Aggiungi testo", text="", fontsize=12.0, color=QColor("black"),
                 fontname="helv", show_flatten=True, allow_original=False):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(420, 280)
        lay = QVBoxLayout(self)
        self.edit = QPlainTextEdit(text)
        lay.addWidget(self.edit)
        form = QFormLayout()
        self.font = QComboBox()
        if allow_original:
            self.font.addItem("Font originale del documento", None)
        for label, code in BASE14.items():
            self.font.addItem(label, code)
        idx = 0 if allow_original else self.font.findData(fontname)
        self.font.setCurrentIndex(max(idx, 0))
        self.size = QDoubleSpinBox(minimum=4, maximum=200, value=round(fontsize, 1), decimals=1)
        self.color = ColorButton(color)
        self.align = QComboBox()
        self.align.addItems(["Sinistra", "Centro", "Destra"])
        form.addRow("Carattere:", self.font)
        form.addRow("Dimensione:", self.size)
        form.addRow("Colore:", self.color)
        if show_flatten:
            form.addRow("Allineamento:", self.align)
            self.flatten = QCheckBox("Inserisci nel contenuto della pagina (non come commento)")
            self.flatten.setChecked(True)
            form.addRow(self.flatten)
        else:
            self.flatten = None
        lay.addLayout(form)
        lay.addWidget(_buttons(self))
        self.edit.setFocus()

    def values(self) -> dict:
        return dict(text=self.edit.toPlainText(), fontsize=self.size.value(), color=self.color.rgb(),
                    fontname=self.font.currentData(), flatten=bool(self.flatten and self.flatten.isChecked()),
                    align=self.align.currentIndex())


class SignaturePad(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(460, 180)
        self.setCursor(Qt.CrossCursor)
        self.paths: list[QPainterPath] = []
        self.pen_color = QColor(10, 30, 120)
        self.setAttribute(Qt.WA_StaticContents)

    def clear(self) -> None:
        self.paths.clear()
        self.update()

    def mousePressEvent(self, e) -> None:
        p = QPainterPath(e.position())
        self.paths.append(p)
        self.update()

    def mouseMoveEvent(self, e) -> None:
        if self.paths:
            self.paths[-1].lineTo(e.position())
            self.update()

    def paintEvent(self, e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), Qt.white)
        p.setPen(QPen(QColor("#bbb"), 1, Qt.DashLine))
        y = self.height() - 40
        p.drawLine(20, y, self.width() - 20, y)
        p.setPen(QPen(self.pen_color, 2.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        for path in self.paths:
            p.drawPath(path)

    def to_png(self) -> bytes | None:
        if not self.paths:
            return None
        bounds = QPainterPath()
        for path in self.paths:
            bounds.addPath(path)
        r = bounds.boundingRect().adjusted(-4, -4, 4, 4)
        scale = 3  # risoluzione più alta per la stampa
        img = QImage(int(r.width() * scale), int(r.height() * scale), QImage.Format_ARGB32)
        img.fill(Qt.transparent)
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing)
        p.scale(scale, scale)
        p.translate(-r.topLeft())
        p.setPen(QPen(self.pen_color, 2.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        for path in self.paths:
            p.drawPath(path)
        p.end()
        return qimage_to_png(img)


def qimage_to_png(img: QImage) -> bytes:
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.WriteOnly)
    img.save(buf, "PNG")
    return bytes(ba)


class SignatureDialog(QDialog):
    """Crea una firma: disegnata a mano, digitata o caricata da immagine."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Firma")
        lay = QVBoxLayout(self)
        self.tabs = QTabWidget()
        # Disegno
        draw = QWidget()
        dl = QVBoxLayout(draw)
        dl.addWidget(QLabel("Disegna la firma con il mouse o la penna:"))
        self.pad = SignaturePad()
        dl.addWidget(self.pad)
        row = QHBoxLayout()
        clear = QPushButton("Cancella")
        clear.clicked.connect(self.pad.clear)
        self.pad_color = ColorButton(self.pad.pen_color)
        self.pad_color.clicked.connect(lambda: (setattr(self.pad, "pen_color", self.pad_color.color), self.pad.update()))
        row.addWidget(QLabel("Colore:"))
        row.addWidget(self.pad_color)
        row.addStretch()
        row.addWidget(clear)
        dl.addLayout(row)
        self.tabs.addTab(draw, "Disegna")
        # Testo
        typed = QWidget()
        tl = QFormLayout(typed)
        self.typed = QLineEdit()
        self.typed.setPlaceholderText("Nome e cognome")
        self.typed_font = QComboBox()
        self.typed_font.addItems(["Segoe Script", "Brush Script MT", "Lucida Handwriting", "Times New Roman"])
        self.typed_font.setEditable(True)
        tl.addRow("Testo:", self.typed)
        tl.addRow("Carattere:", self.typed_font)
        self.tabs.addTab(typed, "Digita")
        # Immagine
        image = QWidget()
        il = QHBoxLayout(image)
        self.image_path = QLineEdit()
        browse = QPushButton("Sfoglia…")
        browse.clicked.connect(self._browse)
        il.addWidget(self.image_path)
        il.addWidget(browse)
        self.tabs.addTab(image, "Immagine")
        lay.addWidget(self.tabs)
        lay.addWidget(_buttons(self))

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Immagine firma", "", "Immagini (*.png *.jpg *.jpeg *.bmp)")
        if path:
            self.image_path.setText(path)

    def png(self) -> bytes | None:
        tab = self.tabs.currentIndex()
        if tab == 0:
            return self.pad.to_png()
        if tab == 1:
            text = self.typed.text().strip()
            if not text:
                return None
            from PySide6.QtGui import QFont, QFontMetrics
            font = QFont(self.typed_font.currentText(), 48)
            fm = QFontMetrics(font)
            w, h = fm.horizontalAdvance(text) + 20, fm.height() + 10
            img = QImage(w, h, QImage.Format_ARGB32)
            img.fill(Qt.transparent)
            p = QPainter(img)
            p.setRenderHint(QPainter.Antialiasing)
            p.setFont(font)
            p.setPen(QColor(10, 30, 120))
            p.drawText(10, fm.ascent() + 5, text)
            p.end()
            return qimage_to_png(img)
        path = self.image_path.text()
        if path and os.path.exists(path):
            with open(path, "rb") as f:
                return f.read()
        return None


class WatermarkDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Filigrana")
        form = QFormLayout(self)
        self.text = QLineEdit("RISERVATO")
        self.size = QSpinBox(minimum=8, maximum=300, value=60)
        self.angle = QSpinBox(minimum=-180, maximum=180, value=45)
        self.opacity = QSlider(Qt.Horizontal, minimum=5, maximum=100, value=30)
        self.color = ColorButton(QColor(150, 150, 150))
        form.addRow("Testo:", self.text)
        form.addRow("Dimensione:", self.size)
        form.addRow("Angolo (°):", self.angle)
        form.addRow("Opacità:", self.opacity)
        form.addRow("Colore:", self.color)
        form.addRow(_buttons(self))

    def values(self) -> dict:
        return dict(text=self.text.text(), fontsize=self.size.value(), angle=self.angle.value(),
                    opacity=self.opacity.value() / 100, color=self.color.rgb())


class PageNumbersDialog(QDialog):
    POSITIONS = {"In basso al centro": "bottom-center", "In basso a destra": "bottom-right",
                 "In basso a sinistra": "bottom-left", "In alto al centro": "top-center",
                 "In alto a destra": "top-right", "In alto a sinistra": "top-left"}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Numeri di pagina")
        form = QFormLayout(self)
        self.fmt = QComboBox(editable=True)
        self.fmt.addItems(["Pagina {n} di {tot}", "{n}", "{n}/{tot}", "- {n} -"])
        self.pos = QComboBox()
        self.pos.addItems(list(self.POSITIONS))
        self.size = QSpinBox(minimum=6, maximum=40, value=10)
        self.start = QSpinBox(minimum=0, maximum=9999, value=1)
        form.addRow("Formato:", self.fmt)
        form.addRow(QLabel("<small>{n} = numero pagina, {tot} = totale</small>"))
        form.addRow("Posizione:", self.pos)
        form.addRow("Dimensione:", self.size)
        form.addRow("Inizia da:", self.start)
        form.addRow(_buttons(self))

    def values(self) -> dict:
        return dict(fmt=self.fmt.currentText(), position=self.POSITIONS[self.pos.currentText()],
                    fontsize=self.size.value(), start=self.start.value())


class MetadataDialog(QDialog):
    FIELDS = [("title", "Titolo"), ("author", "Autore"), ("subject", "Oggetto"),
              ("keywords", "Parole chiave"), ("creator", "Applicazione"), ("producer", "Produttore")]

    def __init__(self, meta: dict, info: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Proprietà documento")
        form = QFormLayout(self)
        self.edits = {}
        for key, label in self.FIELDS:
            e = QLineEdit(meta.get(key) or "")
            self.edits[key] = e
            form.addRow(label + ":", e)
        info_label = QLabel(info)
        info_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        form.addRow(info_label)
        form.addRow(_buttons(self))

    def values(self) -> dict:
        return {k: e.text() for k, e in self.edits.items()}


class SecurityDialog(QDialog):
    def __init__(self, parent=None, protected=False):
        super().__init__(parent)
        self.setWindowTitle("Protezione con password")
        form = QFormLayout(self)
        self.remove = QCheckBox("Rimuovi la protezione")
        self.remove.setVisible(protected)
        self.user = QLineEdit(echoMode=QLineEdit.Password)
        self.user2 = QLineEdit(echoMode=QLineEdit.Password)
        self.owner = QLineEdit(echoMode=QLineEdit.Password)
        self.owner.setPlaceholderText("facoltativa: per modificare i permessi")
        form.addRow(self.remove)
        form.addRow("Password di apertura:", self.user)
        form.addRow("Conferma password:", self.user2)
        form.addRow("Password proprietario:", self.owner)
        form.addRow(QLabel("<small>Il file verrà cifrato con AES a 256 bit al salvataggio.</small>"))
        self.error = QLabel()
        self.error.setStyleSheet("color: #c00")
        form.addRow(self.error)
        form.addRow(_buttons(self))

    def accept(self) -> None:
        if not self.remove.isChecked():
            if not self.user.text():
                self.error.setText("Inserire una password.")
                return
            if self.user.text() != self.user2.text():
                self.error.setText("Le password non coincidono.")
                return
        super().accept()


class MergeDialog(QDialog):
    """Elenco ordinabile di file da unire."""

    def __init__(self, parent=None, initial: list[str] | None = None):
        super().__init__(parent)
        self.setWindowTitle("Unisci file in un unico PDF")
        self.resize(560, 380)
        lay = QHBoxLayout(self)
        self.list = QListWidget()
        self.list.setDragDropMode(QAbstractItemView.InternalMove)
        for p in initial or []:
            self.list.addItem(p)
        lay.addWidget(self.list)
        col = QVBoxLayout()
        for text, slot in [("Aggiungi…", self._add), ("Rimuovi", self._remove),
                           ("Su", lambda: self._move(-1)), ("Giù", lambda: self._move(1))]:
            b = QPushButton(text)
            b.clicked.connect(slot)
            col.addWidget(b)
        col.addStretch()
        col.addWidget(_buttons(self))
        lay.addLayout(col)

    def _add(self) -> None:
        exts = " ".join("*" + e for e in IMAGE_EXTENSIONS)
        paths, _ = QFileDialog.getOpenFileNames(self, "Aggiungi file", "", f"PDF e immagini (*.pdf {exts});;Tutti i file (*)")
        for p in paths:
            self.list.addItem(p)

    def _remove(self) -> None:
        for it in self.list.selectedItems():
            self.list.takeItem(self.list.row(it))

    def _move(self, delta: int) -> None:
        row = self.list.currentRow()
        new = row + delta
        if row < 0 or not 0 <= new < self.list.count():
            return
        it = self.list.takeItem(row)
        self.list.insertItem(new, it)
        self.list.setCurrentRow(new)

    def files(self) -> list[str]:
        return [self.list.item(i).text() for i in range(self.list.count())]


class SplitDialog(QDialog):
    def __init__(self, page_count: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Dividi documento")
        lay = QVBoxLayout(self)
        self.every = QRadioButton("Ogni")
        self.n = QSpinBox(minimum=1, maximum=max(1, page_count), value=1)
        self.ranges = QRadioButton("Intervalli:")
        self.ranges_text = QLineEdit(f"1-{max(1, page_count // 2)}, {page_count // 2 + 1}-{page_count}")
        self.every.setChecked(True)
        r1 = QHBoxLayout()
        r1.addWidget(self.every)
        r1.addWidget(self.n)
        r1.addWidget(QLabel("pagine per file"))
        r1.addStretch()
        r2 = QHBoxLayout()
        r2.addWidget(self.ranges)
        r2.addWidget(self.ranges_text)
        lay.addLayout(r1)
        lay.addLayout(r2)
        lay.addWidget(QLabel(f"<small>Il documento ha {page_count} pagine. Esempio intervalli: 1-3, 4, 5-</small>"))
        lay.addWidget(_buttons(self))
        self.page_count = page_count

    def ranges_list(self) -> list[tuple[int, int]]:
        from .document import parse_page_ranges
        if self.every.isChecked():
            n = self.n.value()
            return [(a, min(a + n - 1, self.page_count - 1)) for a in range(0, self.page_count, n)]
        return parse_page_ranges(self.ranges_text.text(), self.page_count)


class CompressDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Riduci dimensione file")
        form = QFormLayout(self)
        self.level = QComboBox()
        self.level.addItems(["Alta qualità (immagini 200 dpi)", "Standard (immagini 150 dpi)",
                             "Minima dimensione (immagini 96 dpi)", "Solo pulizia (immagini invariate)"])
        self.level.setCurrentIndex(1)
        form.addRow("Livello:", self.level)
        form.addRow(_buttons(self))

    def settings(self) -> tuple[int | None, int]:
        return [(200, 85), (150, 70), (96, 55), (None, 0)][self.level.currentIndex()]


class ExportImagesDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Esporta pagine come immagini")
        form = QFormLayout(self)
        self.fmt = QComboBox()
        self.fmt.addItems(["png", "jpg"])
        self.dpi = QSpinBox(minimum=36, maximum=600, value=150)
        self.only_selected = QCheckBox("Solo le pagine selezionate")
        form.addRow("Formato:", self.fmt)
        form.addRow("Risoluzione (dpi):", self.dpi)
        form.addRow(self.only_selected)
        form.addRow(_buttons(self))


class FormFieldDialog(QDialog):
    """Compilazione di un campo modulo."""

    def __init__(self, widget, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Campo: {widget.field_name or ''}")
        form = QFormLayout(self)
        self.widget = widget
        t = widget.field_type
        value = widget.field_value
        if t in (pymupdf.PDF_WIDGET_TYPE_CHECKBOX, pymupdf.PDF_WIDGET_TYPE_RADIOBUTTON):
            self.editor = QCheckBox(widget.field_label or widget.field_name or "")
            self.editor.setChecked(value not in (False, "Off", "", None))
        elif t in (pymupdf.PDF_WIDGET_TYPE_COMBOBOX, pymupdf.PDF_WIDGET_TYPE_LISTBOX):
            self.editor = QComboBox(editable=t == pymupdf.PDF_WIDGET_TYPE_COMBOBOX)
            for c in widget.choice_values or []:
                self.editor.addItem(c if isinstance(c, str) else c[1])
            self.editor.setCurrentText(str(value or ""))
        else:
            self.editor = QLineEdit(str(value or ""))
        form.addRow((widget.field_label or widget.field_name or "Valore") + ":", self.editor)
        form.addRow(_buttons(self))

    def value(self):
        e = self.editor
        if isinstance(e, QCheckBox):
            on = self.widget.on_state() if hasattr(self.widget, "on_state") else True
            return on if e.isChecked() else "Off"
        if isinstance(e, QComboBox):
            return e.currentText()
        return e.text()


class PasswordPrompt(QDialog):
    def __init__(self, filename: str, parent=None, retry=False):
        super().__init__(parent)
        self.setWindowTitle("Documento protetto")
        form = QFormLayout(self)
        msg = f"«{filename}» è protetto da password."
        if retry:
            msg += "\n<b>Password errata, riprovare.</b>"
        form.addRow(QLabel(msg))
        self.pw = QLineEdit(echoMode=QLineEdit.Password)
        form.addRow("Password:", self.pw)
        form.addRow(_buttons(self))


class NewDocumentDialog(QDialog):
    SIZES = {"A4 verticale": (595, 842), "A4 orizzontale": (842, 595), "A3 verticale": (842, 1191),
             "A5 verticale": (420, 595), "Lettera (US)": (612, 792), "Legale (US)": (612, 1008)}

    def __init__(self, parent=None, title="Nuovo documento vuoto"):
        super().__init__(parent)
        self.setWindowTitle(title)
        form = QFormLayout(self)
        self.size = QComboBox()
        self.size.addItems(list(self.SIZES))
        self.pages = QSpinBox(minimum=1, maximum=500, value=1)
        form.addRow("Formato:", self.size)
        form.addRow("Pagine:", self.pages)
        form.addRow(_buttons(self))

    def values(self) -> tuple[float, float, int]:
        w, h = self.SIZES[self.size.currentText()]
        return w, h, self.pages.value()


class FindReplaceDialog(QDialog):
    def __init__(self, parent=None, find_text=""):
        super().__init__(parent)
        self.setWindowTitle("Trova e sostituisci")
        form = QFormLayout(self)
        self.find = QLineEdit(find_text)
        self.replace = QLineEdit()
        self.case = QCheckBox("Maiuscole/minuscole")
        self.case.setChecked(True)
        self.current_only = QCheckBox("Solo nella pagina corrente")
        form.addRow("Trova:", self.find)
        form.addRow("Sostituisci con:", self.replace)
        form.addRow(self.case)
        form.addRow(self.current_only)
        form.addRow(QLabel("<small>Il testo sostituito mantiene font, dimensione e colore originali.</small>"))
        box = _buttons(self)
        box.button(QDialogButtonBox.Ok).setText("Sostituisci tutto")
        form.addRow(box)


class PdfADialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        from .pdfa import LEVELS
        self.setWindowTitle("Salva come PDF/A")
        form = QFormLayout(self)
        self.level = QComboBox()
        for label, lvl in LEVELS.items():
            self.level.addItem(label, lvl)
        self.level.setCurrentIndex(1)
        form.addRow("Formato:", self.level)
        form.addRow(QLabel("<small>PDF/A è il formato per l'archiviazione a lungo termine e la conservazione "
                           "sostitutiva. I font vengono incorporati, i colori convertiti in sRGB e la "
                           "protezione con password rimossa.<br>Per pratiche, PEC e portali della PA è in "
                           "genere richiesto PDF/A-1b o PDF/A-2b.</small>", wordWrap=True))
        form.addRow(_buttons(self))


class SignaturesDialog(QDialog):
    """Esito della verifica delle firme di un file .p7m."""

    def __init__(self, filename: str, signers, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Firme digitali")
        self.resize(520, 360)
        lay = QVBoxLayout(self)
        ok = signers and all(s.integrity_ok for s in signers)
        head = QLabel(f"<h3>{'✔' if ok else '✘'} {filename}</h3>"
                      f"<p>{len(signers)} firma/e trovate. "
                      + ("Tutte le firme sono integre: il documento non è stato modificato dopo la firma."
                         if ok else "<b style='color:#b00020'>Attenzione: almeno una firma non è valida.</b>")
                      + "</p>")
        head.setWordWrap(True)
        lay.addWidget(head)
        from PySide6.QtWidgets import QTextBrowser
        body = QTextBrowser()
        body.setHtml("<hr>".join(s.summary() for s in signers))
        lay.addWidget(body)
        note = QLabel("<small>Verificata l'integrità crittografica. L'appartenenza del certificatore "
                      "all'elenco pubblico dei certificatori (AgID/eIDAS) e lo stato di revoca non sono "
                      "controllati: per una verifica con valore legale usare un servizio di verifica "
                      "ufficiale.</small>")
        note.setWordWrap(True)
        lay.addWidget(note)
        box = QDialogButtonBox(QDialogButtonBox.Close)
        box.rejected.connect(self.reject)
        box.button(QDialogButtonBox.Close).setText("Chiudi")
        lay.addWidget(box)


class DxfDialog(QDialog):
    """Opzioni di esportazione in DXF."""

    def __init__(self, page_count: int, current: int, vector_info: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Esporta in DXF (CAD)")
        self.page_count = page_count
        self.current = current
        form = QFormLayout(self)
        info = QLabel(vector_info)
        info.setWordWrap(True)
        form.addRow(info)
        self.pages = QComboBox()
        self.pages.addItems([f"Pagina corrente ({current + 1})", "Tutte le pagine (un file per pagina)",
                             "Intervallo…"])
        self.range = QLineEdit(f"{current + 1}")
        self.range.setEnabled(False)
        self.pages.currentIndexChanged.connect(lambda i: self.range.setEnabled(i == 2))
        form.addRow("Pagine:", self.pages)
        form.addRow("Intervallo:", self.range)
        row = QHBoxLayout()
        row.addWidget(QLabel("1 :"))
        self.scale = QDoubleSpinBox(minimum=0.001, maximum=100000, value=1, decimals=3)
        self.scale.setToolTip("Scala del disegno: per una tavola in scala 1:100 inserire 100,\n"
                              "così le misure nel DXF sono quelle reali")
        row.addWidget(self.scale)
        row.addStretch()
        form.addRow("Scala del disegno:", row)
        self.units = QComboBox()
        for label, code in [("Millimetri", "mm"), ("Centimetri", "cm"), ("Metri", "m")]:
            self.units.addItem(label, code)
        form.addRow("Unità del DXF:", self.units)
        self.text = QCheckBox("Testi")
        self.fills = QCheckBox("Riempimenti (retini pieni)")
        self.annots = QCheckBox("Commenti e disegni aggiunti al PDF")
        self.circles = QCheckBox("Riconosci i cerchi")
        for cb in (self.text, self.fills, self.annots, self.circles):
            cb.setChecked(True)
            form.addRow(cb)
        form.addRow(QLabel("<small>I layer del PDF (se creati dal programma CAD) vengono mantenuti; "
                           "altrimenti le linee sono raggruppate in layer per colore.<br>"
                           "Le parti scansionate (immagini) non vengono convertite in linee.</small>",
                           wordWrap=True))
        form.addRow(_buttons(self))

    def page_list(self) -> list[int]:
        from .document import parse_page_ranges
        i = self.pages.currentIndex()
        if i == 0:
            return [self.current]
        if i == 1:
            return list(range(self.page_count))
        return [p for a, b in parse_page_ranges(self.range.text(), self.page_count) for p in range(a, b + 1)]

    def options(self):
        from .dxf_export import DxfOptions
        return DxfOptions(scale=self.scale.value(), units=self.units.currentData(),
                          include_text=self.text.isChecked(), include_fills=self.fills.isChecked(),
                          include_annotations=self.annots.isChecked(), detect_circles=self.circles.isChecked())
