"""Visualizzatore a scorrimento continuo con strumenti di modifica."""
from __future__ import annotations

import pymupdf
from PySide6.QtCore import QEvent, QObject, QPointF, QRectF, Qt, QTimer, Signal
import re

from PySide6.QtGui import (QBrush, QColor, QCursor, QFont, QImage, QPainter, QPainterPath, QPen, QPixmap,
                           QTextBlockFormat, QTextCursor, QTextOption)
from PySide6.QtWidgets import (QComboBox, QGraphicsPathItem, QGraphicsPixmapItem, QGraphicsRectItem,
                               QGraphicsScene, QGraphicsTextItem, QGraphicsView, QLineEdit, QPlainTextEdit)

FIELD_FILL = QColor(204, 215, 255, 80)      # azzurro dei campi compilabili, come in Acrobat
FIELD_BORDER = QColor(110, 140, 230, 170)
EDITABLE_KINDS = {"text", "multiline", "checkbox", "radio", "combo", "list"}


class _FieldKeys(QObject):
    """Tasti dell'editor di campo: Invio/Tab conferma e passa al successivo, Esc annulla."""

    def __init__(self, view, multiline: bool):
        super().__init__(view)
        self.view = view
        self.multiline = multiline

    def eventFilter(self, obj, event) -> bool:
        if event.type() == QEvent.KeyPress:
            key = event.key()
            if key == Qt.Key_Escape:
                self.view.close_field_editor(commit=False)
                return True
            if key in (Qt.Key_Tab, Qt.Key_Backtab):
                back = key == Qt.Key_Backtab or bool(event.modifiers() & Qt.ShiftModifier)
                self.view.close_field_editor(commit=True, move=-1 if back else 1)
                return True
            if key in (Qt.Key_Return, Qt.Key_Enter) and (not self.multiline or
                                                         event.modifiers() & Qt.ControlModifier):
                self.view.close_field_editor(commit=True, move=1)
                return True
        elif event.type() == QEvent.FocusOut and event.reason() != Qt.PopupFocusReason:
            # Chiude solo se è ancora aperto lo stesso editor (non quello del campo successivo)
            QTimer.singleShot(0, lambda: self.view.close_field_editor(commit=True, only=obj))
        return False

from .document import PdfDocument
from .textselect import PageText

SELECTION_COLOR = QColor(0, 120, 215, 80)

PAGE_GAP = 16.0
DPI_BASE = 72.0

# Strumenti disponibili
HAND, SELECT, HIGHLIGHT, UNDERLINE, STRIKEOUT, TEXT, EDIT_TEXT, NOTE, RECT, ELLIPSE, LINE, ARROW, \
    INK, IMAGE, SIGNATURE, WHITEOUT, REDACT, ERASER, CROP = (
        "hand", "select", "highlight", "underline", "strikeout", "text", "edit_text", "note", "rect",
        "ellipse", "line", "arrow", "ink", "image", "signature", "whiteout", "redact", "eraser", "crop")

DRAG_TOOLS = {SELECT, HIGHLIGHT, UNDERLINE, STRIKEOUT, TEXT, RECT, ELLIPSE, IMAGE, SIGNATURE,
              WHITEOUT, REDACT, CROP}
LINE_TOOLS = {LINE, ARROW}
CLICK_TOOLS = {EDIT_TEXT, NOTE, ERASER}


def pixmap_to_qimage(pix: pymupdf.Pixmap) -> QImage:
    fmt = QImage.Format_RGBA8888 if pix.alpha else QImage.Format_RGB888
    img = QImage(pix.samples, pix.width, pix.height, pix.stride, fmt)
    return img.copy()  # stacca i dati dal buffer di PyMuPDF


def qt_font_family(pdf_font: str) -> str:
    """'ABCDEF+TimesNewRomanPS-BoldMT' → 'Times New Roman' (per l'anteprima di modifica)."""
    name = re.sub(r"^[A-Z]{6}\+", "", pdf_font or "")
    name = re.split(r"[-,]", name)[0]
    name = re.sub(r"(PSMT|MT|PS)$", "", name)
    if " " not in name:
        name = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name)
    name = re.sub(r"\s+(Regular|Bold|Italic|Oblique|Medium|Light|Semibold|Book)\b.*$", "", name).strip()
    return {"Helvetica": "Arial", "Times": "Times New Roman", "Courier": "Courier New"}.get(name, name)


class InlineTextItem(QGraphicsTextItem):
    """Casella di testo modificabile sovrapposta al paragrafo originale."""

    def __init__(self, on_commit, on_cancel):
        super().__init__()
        self._on_commit = on_commit
        self._on_cancel = on_cancel

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Escape:
            self._on_cancel()
            return
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and event.modifiers() & Qt.ControlModifier:
            self._on_commit()
            return
        super().keyPressEvent(event)


class PageView(QGraphicsView):
    """Mostra tutte le pagine in colonna e traduce i gesti in operazioni sul documento."""

    pageChanged = Signal(int)
    zoomChanged = Signal(float)
    # (strumento, indice pagina, dati) — gestiti dalla finestra principale
    toolAction = Signal(str, int, object)
    # (campo, nuovo valore) quando l'utente compila un campo del modulo
    fieldEdited = Signal(object, object)
    # (azione, pagina, rettangoli o testo) dal menu del testo selezionato
    selectionAction = Signal(str, int, object)
    selectionChanged = Signal(bool)
    documentEdited = Signal()
    # (pagina, blocco, nuovo testo) al termine della modifica diretta di un paragrafo
    inlineEditFinished = Signal(int, object, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setBackgroundBrush(QColor("#525659"))
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        self.setTransformationAnchor(QGraphicsView.NoAnchor)
        self.document: PdfDocument | None = None
        self.zoom = 1.0
        self.fit_mode: str | None = "width"  # "width", "page" o None
        self.tool = HAND
        self.tool_color = QColor(255, 0, 0)
        self.highlight_color = QColor(255, 235, 0)
        self.line_width = 2.0
        self._pages: list[QGraphicsPixmapItem] = []
        self._frames: list[QGraphicsRectItem] = []
        self._rendered: dict[int, float] = {}
        self._overlays: list = []
        self._search_items: list = []
        self._drag_start: QPointF | None = None
        self._drag_page = -1
        self._rubber: QGraphicsRectItem | None = None
        self._ink_item: QGraphicsPathItem | None = None
        self._ink_strokes: list[list[tuple[float, float]]] = []
        self._ink_page = -1
        self._ink_timer = QTimer(self, singleShot=True, interval=1200, timeout=self._commit_ink)
        self._render_timer = QTimer(self, singleShot=True, interval=30, timeout=self._render_visible)
        self._current_page = 0
        self._inline = None  # (pagina, blocco, sfondo, casella)
        self.show_fields = True
        self._fields: list = []
        self._field_items: list = []
        self._field_editor = None  # (campo, proxy, widget)
        self._ptext: dict[int, PageText] = {}
        self._sel = None          # (pagina, inizio, fine) del testo selezionato
        self._sel_items: list = []
        self._sel_drag = None     # (pagina, ancora) durante il trascinamento
        self._last_dbl = None     # (istante, posizione) per il triplo clic
        self.verticalScrollBar().valueChanged.connect(self._on_scroll)
        self.setAcceptDrops(False)
        self.viewport().setMouseTracking(True)

    # ------------------------------------------------------------------ setup
    def set_document(self, document: PdfDocument | None, keep_position: bool = False) -> None:
        pos = self.verticalScrollBar().value() if keep_position else 0
        page = self._current_page if keep_position else 0
        self._commit_ink()
        self.cancel_inline_edit()
        self.close_field_editor(commit=False)
        self._ptext.clear()
        self._sel = None
        self.document = document
        self._rebuild()
        if keep_position:
            self.verticalScrollBar().setValue(pos)
        else:
            self.go_to_page(0)
        self._current_page = min(page, max(0, (document.page_count - 1) if document else 0))

    def reload(self) -> None:
        """Ridisegna dopo una modifica, mantenendo la posizione."""
        self.set_document(self.document, keep_position=True)

    def _rebuild(self) -> None:
        scene = self.scene()
        self._field_items.clear()  # eliminati insieme alla scena
        scene.clear()
        self._pages.clear()
        self._frames.clear()
        self._rendered.clear()
        self._overlays.clear()
        self._search_items.clear()
        self._rubber = None
        self._ink_item = None
        if not self.document:
            scene.setSceneRect(QRectF())
            return
        self._apply_fit()
        y = PAGE_GAP
        max_w = 0.0
        for i in range(self.document.page_count):
            r = self.document.page(i).rect
            w, h = r.width * self.zoom, r.height * self.zoom
            frame = scene.addRect(QRectF(0, 0, w, h), QPen(QColor("#3a3a3a")), QBrush(Qt.white))
            frame.setPos(0, y)
            item = QGraphicsPixmapItem()
            item.setPos(0, y)
            item.setTransformationMode(Qt.SmoothTransformation)
            item.setZValue(1)
            scene.addItem(item)
            self._frames.append(frame)
            self._pages.append(item)
            max_w = max(max_w, w)
            y += h + PAGE_GAP
        # Centra le pagine più strette
        for frame, item in zip(self._frames, self._pages):
            x = (max_w - frame.rect().width()) / 2
            frame.setX(x)
            item.setX(x)
        scene.setSceneRect(QRectF(-PAGE_GAP, 0, max_w + 2 * PAGE_GAP, y))
        self._build_field_overlays()
        self._sel_items.clear()  # eliminati con la scena; si ridisegnano alla nuova scala
        self._draw_selection()
        self._render_timer.start()

    def _apply_fit(self) -> None:
        if not self.document or not self.fit_mode or not self.document.page_count:
            return
        vp = self.viewport().size()
        widest = max(self.document.page(i).rect.width for i in range(self.document.page_count))
        first = self.document.page(self._current_page if self._current_page < self.document.page_count else 0).rect
        if self.fit_mode == "width":
            z = (vp.width() - 2 * PAGE_GAP - 4) / widest
        else:
            z = min((vp.width() - 2 * PAGE_GAP) / first.width, (vp.height() - 2 * PAGE_GAP) / first.height)
        self.zoom = max(0.1, min(z, 8.0))
        self.zoomChanged.emit(self.zoom)

    def set_zoom(self, zoom: float, fit: str | None = None) -> None:
        if not self.document:
            return
        page = self._current_page
        self.fit_mode = fit
        if fit is None:
            self.zoom = max(0.1, min(zoom, 8.0))
            self.zoomChanged.emit(self.zoom)
        self._rebuild()
        self.go_to_page(page)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self.fit_mode and self.document:
            old = self.zoom
            self._apply_fit()
            if abs(old - self.zoom) > 0.01:
                page = self._current_page
                self._rebuild()
                self.go_to_page(page)

    # --------------------------------------------------------------- rendering
    def _visible_pages(self) -> range:
        if not self._frames:
            return range(0)
        area = self.mapToScene(self.viewport().rect()).boundingRect()
        first = last = None
        for i, f in enumerate(self._frames):
            fr = f.sceneBoundingRect()
            if fr.bottom() >= area.top() and fr.top() <= area.bottom():
                first = i if first is None else first
                last = i
            elif first is not None:
                break
        if first is None:
            return range(0)
        return range(max(0, first - 1), min(len(self._frames), last + 2))

    def _render_visible(self) -> None:
        if not self.document:
            return
        visible = self._visible_pages()
        dpr = self.devicePixelRatioF()
        for i in visible:
            if self._rendered.get(i) == self.zoom:
                continue
            page = self.document.page(i)
            mat = pymupdf.Matrix(self.zoom * dpr, self.zoom * dpr)
            pix = page.get_pixmap(matrix=mat, annots=True, alpha=False)
            qpix = QPixmap.fromImage(pixmap_to_qimage(pix))
            qpix.setDevicePixelRatio(dpr)
            self._pages[i].setPixmap(qpix)
            self._rendered[i] = self.zoom
        # Libera la memoria delle pagine lontane
        for i in list(self._rendered):
            if i < visible.start - 3 or i > visible.stop + 3:
                self._pages[i].setPixmap(QPixmap())
                del self._rendered[i]

    def refresh_page(self, index: int) -> None:
        self._rendered.pop(index, None)
        self._ptext.pop(index, None)
        if self._sel and self._sel[0] == index:
            self.clear_selection()
        self._render_visible()

    def _on_scroll(self) -> None:
        self._render_timer.start()
        if not self._frames:
            return
        center = self.mapToScene(self.viewport().rect().center())
        for i, f in enumerate(self._frames):
            fr = f.sceneBoundingRect()
            if fr.top() - PAGE_GAP <= center.y() <= fr.bottom() + PAGE_GAP / 2:
                if i != self._current_page:
                    self._current_page = i
                    self.pageChanged.emit(i)
                break

    # ------------------------------------------------------------- navigazione
    @property
    def current_page(self) -> int:
        return self._current_page

    def go_to_page(self, index: int, rect: pymupdf.Rect | None = None) -> None:
        if not self._frames:
            return
        index = max(0, min(index, len(self._frames) - 1))
        top = self._frames[index].sceneBoundingRect().top() - PAGE_GAP / 2
        if rect is not None:
            r = self._doc_rect_to_scene(index, rect)
            self.ensureVisible(r, 50, 100)
        else:
            self.verticalScrollBar().setValue(int(top))
        self._current_page = index
        self.pageChanged.emit(index)
        self._render_timer.start()

    def wheelEvent(self, event) -> None:
        if event.modifiers() & Qt.ControlModifier:
            factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
            self.set_zoom(self.zoom * factor)
            event.accept()
            return
        super().wheelEvent(event)

    # ------------------------------------------------------ conversioni coordinate
    def _page_at(self, scene_pt: QPointF) -> int:
        for i, f in enumerate(self._frames):
            if f.sceneBoundingRect().contains(scene_pt):
                return i
        return -1

    def _scene_to_doc(self, index: int, pt: QPointF) -> pymupdf.Point:
        """Punto scena → coordinate non ruotate della pagina."""
        origin = self._frames[index].pos()
        page = self.document.page(index)
        vis = pymupdf.Point((pt.x() - origin.x()) / self.zoom, (pt.y() - origin.y()) / self.zoom)
        return vis * page.derotation_matrix

    def _scene_rect_to_doc(self, index: int, rect: QRectF) -> pymupdf.Rect:
        a = self._scene_to_doc(index, rect.topLeft())
        b = self._scene_to_doc(index, rect.bottomRight())
        return pymupdf.Rect(a, b).normalize()

    def _doc_rect_to_scene(self, index: int, rect: pymupdf.Rect) -> QRectF:
        page = self.document.page(index)
        vis = pymupdf.Rect(rect) * page.rotation_matrix
        origin = self._frames[index].pos()
        return QRectF(origin.x() + vis.x0 * self.zoom, origin.y() + vis.y0 * self.zoom,
                      vis.width * self.zoom, vis.height * self.zoom)

    def _clamp_to_page(self, index: int, pt: QPointF) -> QPointF:
        r = self._frames[index].sceneBoundingRect()
        return QPointF(min(max(pt.x(), r.left()), r.right()), min(max(pt.y(), r.top()), r.bottom()))

    # ------------------------------------------------------------------ ricerca
    def show_search_results(self, results: list[tuple[int, pymupdf.Rect]], current: int = -1) -> None:
        for item in self._search_items:
            self.scene().removeItem(item)
        self._search_items.clear()
        if not self.document:
            return
        for n, (page, rect) in enumerate(results):
            if page >= len(self._frames):
                continue
            color = QColor(255, 120, 0, 120) if n == current else QColor(0, 120, 255, 70)
            item = self.scene().addRect(self._doc_rect_to_scene(page, rect), QPen(Qt.NoPen), QBrush(color))
            item.setZValue(5)
            self._search_items.append(item)

    # ------------------------------------------------------------------ strumenti
    # ------------------------------------------------------- selezione del testo
    def page_text(self, index: int) -> PageText:
        if index not in self._ptext:
            self._ptext[index] = PageText(self.document.page(index))
        return self._ptext[index]

    @property
    def has_selection(self) -> bool:
        return self._sel is not None and self._sel[1] is not None

    def selected_text(self) -> str:
        if not self.has_selection:
            return ""
        page, a, b = self._sel
        return self.page_text(page).text(a, b)

    def selection_rects(self) -> tuple[int, list]:
        page, a, b = self._sel
        return page, self.page_text(page).rects(a, b)

    def set_selection(self, page: int, a: int | None, b: int | None) -> None:
        self._sel = (page, a, b) if a is not None and b is not None else None
        self._draw_selection()
        self.selectionChanged.emit(self.has_selection)

    def clear_selection(self) -> None:
        if self._sel is not None:
            self._sel = None
            self._draw_selection()
            self.selectionChanged.emit(False)

    def _draw_selection(self) -> None:
        for it in self._sel_items:
            try:
                if it.scene() is not None:
                    self.scene().removeItem(it)
            except RuntimeError:
                pass
        self._sel_items.clear()
        if not self.has_selection or not self._frames:
            return
        page, rects = self.selection_rects()
        if page >= len(self._frames):
            return
        for r in rects:
            item = self.scene().addRect(self._doc_rect_to_scene(page, r), QPen(Qt.NoPen), QBrush(SELECTION_COLOR))
            item.setZValue(7)
            self._sel_items.append(item)

    def copy_selection(self) -> bool:
        from PySide6.QtWidgets import QApplication
        text = self.selected_text()
        if text:
            QApplication.clipboard().setText(text)
        return bool(text)

    def select_all_page(self) -> None:
        if not self.document:
            return
        rng = self.page_text(self._current_page).all()
        if rng:
            self.set_selection(self._current_page, *rng)

    def _text_hit(self, scene_pt: QPointF, nearest: bool):
        """(pagina, indice carattere) sotto il punto; con nearest il più vicino della pagina."""
        idx = self._page_at(scene_pt)
        if idx < 0:
            return None
        pt = self._scene_to_doc(idx, scene_pt)
        pt_text = self.page_text(idx)
        i = pt_text.char_at(pt)
        if i is None and nearest:
            i = pt_text.nearest(pt)
        return (idx, i) if i is not None else None

    def _over_text(self, scene_pt: QPointF) -> bool:
        idx = self._page_at(scene_pt)
        return idx >= 0 and self.page_text(idx).is_over_text(self._scene_to_doc(idx, scene_pt))

    def keyPressEvent(self, event) -> None:
        from PySide6.QtGui import QKeySequence
        if event.matches(QKeySequence.Copy) and self.has_selection:
            self.copy_selection()
            self.selectionAction.emit("copied", self._sel[0], self.selected_text())
            return
        if event.matches(QKeySequence.SelectAll):
            self.select_all_page()
            return
        if event.key() == Qt.Key_Escape and self.has_selection:
            self.clear_selection()
            return
        super().keyPressEvent(event)

    def contextMenuEvent(self, event) -> None:
        from PySide6.QtWidgets import QMenu
        if not self.document:
            return
        sp = self.mapToScene(event.pos())
        idx = self._page_at(sp)
        if idx < 0:
            return
        menu = QMenu(self)
        if self.has_selection:
            text = self.selected_text()
            page = self._sel[0]
            preview = " ".join(text.split())[:30] + ("…" if len(text) > 30 else "")
            menu.addAction("Copia", lambda: (self.copy_selection(),
                                             self.selectionAction.emit("copied", page, text)))
            menu.addSeparator()
            for label, kind in (("Evidenzia", "highlight"), ("Sottolinea", "underline"), ("Barra", "strikeout")):
                menu.addAction(label, lambda k=kind: self.selectionAction.emit(k, page, self.selection_rects()[1]))
            menu.addSeparator()
            menu.addAction(f"Cerca «{preview}»", lambda: self.selectionAction.emit("search", page, text))
            menu.addSeparator()
        menu.addAction("Seleziona tutto il testo della pagina", lambda: (self.go_to_page(idx)
                       if idx != self._current_page else None, self._select_page(idx)))
        menu.addAction("Copia il testo della pagina", lambda: self.selectionAction.emit(
            "copy_page", idx, self.page_text(idx).text(*self.page_text(idx).all())
            if self.page_text(idx).all() else ""))
        menu.exec(event.globalPos())

    def _select_page(self, idx: int) -> None:
        rng = self.page_text(idx).all()
        if rng:
            self.set_selection(idx, *rng)

    # ------------------------------------------------------- moduli compilabili
    def refresh_fields(self) -> None:
        self._fields = self.document.form_fields() if self.document else []

    def _build_field_overlays(self) -> None:
        for it in self._field_items:
            try:
                if it.scene() is not None:
                    self.scene().removeItem(it)
            except RuntimeError:  # già eliminato con la scena
                pass
        self._field_items.clear()
        self.refresh_fields()
        if not self.show_fields:
            return
        for f in self._fields:
            if f.readonly or f.kind not in EDITABLE_KINDS or f.page >= len(self._frames):
                continue
            item = self.scene().addRect(self._doc_rect_to_scene(f.page, f.rect), QPen(FIELD_BORDER, 0.8),
                                        QBrush(FIELD_FILL))
            item.setZValue(6)
            item.setToolTip(f.label or f.name)
            self._field_items.append(item)

    def set_show_fields(self, show: bool) -> None:
        self.show_fields = show
        self._build_field_overlays()

    def field_at(self, scene_pt: QPointF):
        idx = self._page_at(scene_pt)
        if idx < 0:
            return None
        pt = self._scene_to_doc(idx, scene_pt)
        hits = [f for f in self._fields if f.page == idx and f.rect.contains(pt) and f.kind in EDITABLE_KINDS]
        return min(hits, key=lambda f: f.rect.width * f.rect.height) if hits else None

    def activate_field(self, field) -> None:
        self.close_field_editor(commit=True)
        if field.readonly:
            return
        if field.kind == "checkbox":
            self.fieldEdited.emit(field, not field.checked)
            return
        if field.kind == "radio":
            if not field.checked:
                self.fieldEdited.emit(field, True)
            return
        rect = self._doc_rect_to_scene(field.page, field.rect)
        self.ensureVisible(rect, 40, 60)
        size = field.fontsize or min(max(field.rect.height * 0.6, 7), 12)
        font = QFont("Arial")
        font.setPixelSize(max(6, round(size * self.zoom)))
        style = "background:#fffbe6; border:1px solid #3d6bd6; padding:0 2px;"
        if field.kind == "text":
            editor = QLineEdit(str(field.value or ""))
            if field.maxlen:
                editor.setMaxLength(field.maxlen)
            editor.selectAll()
        elif field.kind == "multiline":
            editor = QPlainTextEdit(str(field.value or ""))
        else:  # combo e list
            editor = QComboBox()
            editor.addItems(field.choices)
            editor.setCurrentText(str(field.value or ""))
            editor.activated.connect(lambda _i: self.close_field_editor(commit=True))
        editor.setFont(font)
        editor.setStyleSheet(style)
        proxy = self.scene().addWidget(editor)
        proxy.setGeometry(rect)
        proxy.setZValue(30)
        editor.installEventFilter(_FieldKeys(self, field.kind == "multiline"))
        self._field_editor = (field, proxy, editor)
        editor.setFocus()
        if isinstance(editor, QComboBox):
            QTimer.singleShot(0, editor.showPopup)

    def close_field_editor(self, commit: bool = True, move: int = 0, only=None) -> None:
        if self._field_editor is None or (only is not None and self._field_editor[2] is not only):
            return
        field, proxy, editor = self._field_editor
        self._field_editor = None
        if isinstance(editor, QLineEdit):
            value = editor.text()
        elif isinstance(editor, QPlainTextEdit):
            value = editor.toPlainText()
        else:
            value = editor.currentText()
        if proxy.scene() is not None:
            self.scene().removeItem(proxy)
        proxy.deleteLater()
        self.setFocus()
        if commit and value != str(field.value or ""):
            self.fieldEdited.emit(field, value)  # la finestra aggiorna documento e campi
        if move:
            self._activate_next(field, move)

    def _activate_next(self, field, step: int) -> None:
        order = [f for f in self._fields if f.kind in EDITABLE_KINDS and not f.readonly]
        keys = [(f.page, f.xref) for f in order]
        try:
            i = keys.index((field.page, field.xref))
        except ValueError:
            return
        j = i + step
        if 0 <= j < len(order):
            nxt = order[j]
            if nxt.kind in ("checkbox", "radio"):
                # Le caselle si attivano con un clic: si mostra solo il campo
                self.ensureVisible(self._doc_rect_to_scene(nxt.page, nxt.rect), 40, 60)
                self._focus_marker(nxt)
            else:
                self.activate_field(nxt)

    def _focus_marker(self, field) -> None:
        rect = self._doc_rect_to_scene(field.page, field.rect)
        mark = self.scene().addRect(rect.adjusted(-2, -2, 2, 2), QPen(QColor(61, 107, 214), 2))
        mark.setZValue(31)
        QTimer.singleShot(1200, lambda: mark.scene() and self.scene().removeItem(mark))

    # ------------------------------------------------------- modifica diretta
    @property
    def inline_editing(self) -> bool:
        return self._inline is not None

    def start_inline_edit(self, index: int, block) -> None:
        self.commit_inline_edit()
        rect = self._doc_rect_to_scene(index, block.bbox)
        pad = 3
        bg = self.scene().addRect(rect.adjusted(-pad, -pad, pad, pad), QPen(QColor(0, 120, 215), 1, Qt.DashLine),
                                  QBrush(Qt.white))
        bg.setZValue(20)
        item = InlineTextItem(self.commit_inline_edit, self.cancel_inline_edit)
        font = QFont(qt_font_family(block.font))
        font.setPixelSize(max(4, round(block.size * self.zoom)))
        font.setBold(block.bold)
        font.setItalic(block.italic)
        item.setFont(font)
        item.setDefaultTextColor(QColor.fromRgbF(*block.color))
        item.document().setDocumentMargin(0)
        item.setPlainText(block.text)
        item.setTextWidth(rect.width() + 2)
        fmt = QTextBlockFormat()
        fmt.setLineHeight(block.line_height * 100, QTextBlockFormat.LineHeightTypes.ProportionalHeight.value)
        fmt.setAlignment({"center": Qt.AlignHCenter, "right": Qt.AlignRight,
                          "justify": Qt.AlignJustify}.get(block.align, Qt.AlignLeft))
        cur = QTextCursor(item.document())
        cur.select(QTextCursor.Document)
        cur.mergeBlockFormat(fmt)
        item.setPos(rect.topLeft())
        item.setZValue(21)

        def grow():
            # Lo sfondo bianco segue il testo che si allunga
            r = item.sceneBoundingRect().united(rect)
            bg.setRect(r.adjusted(-pad, -pad, pad, pad))
        item.document().contentsChanged.connect(grow)
        item.setTextInteractionFlags(Qt.TextEditorInteraction)
        self.scene().addItem(item)
        item.setFocus()
        cur = item.textCursor()
        cur.movePosition(QTextCursor.End)
        item.setTextCursor(cur)
        self._inline = (index, block, bg, item)
        self.setFocus()
        item.setFocus()

    def commit_inline_edit(self) -> None:
        if self._inline is None:
            return
        index, block, bg, item = self._inline
        text = item.toPlainText()
        self._remove_inline()
        if text.strip() != block.text.strip():
            self.inlineEditFinished.emit(index, block, text)

    def cancel_inline_edit(self) -> None:
        if self._inline is not None:
            self._remove_inline()

    def _remove_inline(self) -> None:
        _index, _block, bg, item = self._inline
        self._inline = None
        for it in (item, bg):
            if it.scene() is not None:
                self.scene().removeItem(it)

    def set_tool(self, tool: str) -> None:
        self._commit_ink()
        self.commit_inline_edit()
        self.tool = tool
        if tool == HAND:
            self.setDragMode(QGraphicsView.ScrollHandDrag)
            self.viewport().setCursor(Qt.OpenHandCursor)
        else:
            self.setDragMode(QGraphicsView.NoDrag)
            cursor = {SELECT: Qt.IBeamCursor, EDIT_TEXT: Qt.IBeamCursor, HIGHLIGHT: Qt.IBeamCursor,
                      UNDERLINE: Qt.IBeamCursor, STRIKEOUT: Qt.IBeamCursor, ERASER: Qt.PointingHandCursor}
            self.viewport().setCursor(cursor.get(tool, Qt.CrossCursor))

    @staticmethod
    def _rgb(color: QColor) -> tuple[float, float, float]:
        return (color.redF(), color.greenF(), color.blueF())

    def mousePressEvent(self, event) -> None:
        if self._inline is not None:
            item = self._inline[3]
            if item.sceneBoundingRect().contains(self.mapToScene(event.position().toPoint())):
                super().mousePressEvent(event)
                return
            self.commit_inline_edit()
            return
        if self._field_editor is not None:
            proxy = self._field_editor[1]
            if proxy.sceneBoundingRect().contains(self.mapToScene(event.position().toPoint())):
                super().mousePressEvent(event)
                return
            self.close_field_editor(commit=True)
        if self.document and event.button() == Qt.LeftButton and self.tool in (HAND, SELECT, EDIT_TEXT):
            # Clic su un campo del modulo: si compila direttamente
            field = self.field_at(self.mapToScene(event.position().toPoint()))
            if field is not None:
                self.activate_field(field)
                return
        if self.document and event.button() == Qt.LeftButton and self.tool in (HAND, SELECT) \
                and not (self.tool == SELECT and event.modifiers() & Qt.AltModifier):
            sp = self.mapToScene(event.position().toPoint())
            # Con la mano si seleziona solo partendo dal testo; altrove si scorre la pagina
            if self.tool == SELECT or self._over_text(sp):
                hit = self._text_hit(sp, nearest=True)
                if hit is not None:
                    page, i = hit
                    pt_text = self.page_text(page)
                    from PySide6.QtWidgets import QApplication
                    if self._last_dbl and (event.timestamp() - self._last_dbl[0]) < \
                            QApplication.doubleClickInterval() and \
                            (event.position() - self._last_dbl[1]).manhattanLength() < 6:
                        self.set_selection(page, *pt_text.line_at(i))  # triplo clic: riga
                        self._last_dbl = None
                        return
                    if event.modifiers() & Qt.ShiftModifier and self.has_selection and self._sel[0] == page:
                        self.set_selection(page, self._sel[1], i)
                    else:
                        self.set_selection(page, i, i)
                        self._sel_moved = False
                    self._sel_drag = (page, self._sel[1])
                    self.viewport().setCursor(Qt.IBeamCursor)
                    self.setFocus()  # per Ctrl+C
                    return
            self.clear_selection()
        if not self.document or event.button() != Qt.LeftButton or self.tool == HAND:
            super().mousePressEvent(event)
            return
        sp = self.mapToScene(event.position().toPoint())
        idx = self._page_at(sp)
        if idx < 0:
            return
        if self.tool in CLICK_TOOLS:
            data = self._scene_to_doc(idx, sp)
            if self.tool == EDIT_TEXT and event.modifiers() & Qt.ShiftModifier:
                self.toolAction.emit("edit_text_dialog", idx, data)
            else:
                self.toolAction.emit(self.tool, idx, data)
            return
        if self.tool == INK:
            if self._ink_page not in (-1, idx):
                self._commit_ink()
            self._ink_timer.stop()
            self._ink_page = idx
            self._ink_strokes.append([tuple(self._scene_to_doc(idx, sp))])
            if self._ink_item is None:
                self._ink_item = QGraphicsPathItem()
                pen = QPen(self.tool_color, self.line_width * self.zoom, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
                self._ink_item.setPen(pen)
                self._ink_item.setZValue(10)
                self._ink_item.setPath(QPainterPath())
                self.scene().addItem(self._ink_item)
            path = self._ink_item.path()
            path.moveTo(sp)
            self._ink_item.setPath(path)
            self._drag_start = sp
            self._drag_page = idx
            return
        self._drag_start = sp
        self._drag_page = idx
        if self.tool in LINE_TOOLS:
            self._rubber = self.scene().addLine(sp.x(), sp.y(), sp.x(), sp.y(), QPen(self.tool_color, 1.5))
        else:
            pen = QPen(QColor(0, 120, 215), 1, Qt.DashLine)
            fill = QColor(0, 120, 215, 30)
            if self.tool == HIGHLIGHT:
                fill = QColor(self.highlight_color.red(), self.highlight_color.green(), self.highlight_color.blue(), 80)
            elif self.tool in (WHITEOUT,):
                fill = QColor(255, 255, 255, 200)
            elif self.tool == REDACT:
                fill = QColor(0, 0, 0, 120)
            self._rubber = self.scene().addRect(QRectF(sp, sp), pen, QBrush(fill))
        self._rubber.setZValue(10)

    def mouseMoveEvent(self, event) -> None:
        if event.buttons() == Qt.NoButton and self._fields and self.tool in (HAND, SELECT, EDIT_TEXT):
            field = self.field_at(self.mapToScene(event.position().toPoint()))
            if field is not None:
                self.viewport().setCursor(Qt.PointingHandCursor if field.kind in ("checkbox", "radio")
                                          else Qt.IBeamCursor)
            else:
                self.viewport().setCursor({HAND: Qt.OpenHandCursor, SELECT: Qt.IBeamCursor,
                                           EDIT_TEXT: Qt.IBeamCursor}[self.tool])
        if self._sel_drag is not None:
            page, anchor = self._sel_drag
            sp = self._clamp_to_page(page, self.mapToScene(event.position().toPoint()))
            j = self.page_text(page).nearest(self._scene_to_doc(page, sp))
            if j is not None and (not self._sel or self._sel[2] != j):
                self._sel_moved = True
                self.set_selection(page, anchor, j)
            return
        if event.buttons() == Qt.NoButton and self.tool == HAND and self.document and \
                self._field_editor is None and self._inline is None:
            if self.field_at(self.mapToScene(event.position().toPoint())) is None:
                over = self._over_text(self.mapToScene(event.position().toPoint()))
                self.viewport().setCursor(Qt.IBeamCursor if over else Qt.OpenHandCursor)
        if self._inline is not None:
            super().mouseMoveEvent(event)
            return
        if self._drag_start is None or self._drag_page < 0:
            super().mouseMoveEvent(event)
            return
        sp = self._clamp_to_page(self._drag_page, self.mapToScene(event.position().toPoint()))
        if self.tool == INK and self._ink_item is not None:
            path = self._ink_item.path()
            path.lineTo(sp)
            self._ink_item.setPath(path)
            self._ink_strokes[-1].append(tuple(self._scene_to_doc(self._drag_page, sp)))
        elif self.tool in LINE_TOOLS and self._rubber is not None:
            self._rubber.setLine(self._drag_start.x(), self._drag_start.y(), sp.x(), sp.y())
        elif self._rubber is not None:
            self._rubber.setRect(QRectF(self._drag_start, sp).normalized())

    def mouseReleaseEvent(self, event) -> None:
        if self._sel_drag is not None:
            self._sel_drag = None
            # Clic semplice senza trascinare: nessuna selezione
            if not getattr(self, "_sel_moved", True) and self._sel and self._sel[1] == self._sel[2]:
                self.clear_selection()
            return
        if self._inline is not None:
            super().mouseReleaseEvent(event)
            return
        if self._drag_start is None or self._drag_page < 0:
            super().mouseReleaseEvent(event)
            return
        idx = self._drag_page
        start = self._drag_start
        end = self._clamp_to_page(idx, self.mapToScene(event.position().toPoint()))
        self._drag_start = None
        self._drag_page = -1
        if self.tool == INK:
            self._ink_timer.start()
            return
        if self._rubber is not None:
            self.scene().removeItem(self._rubber)
            self._rubber = None
        if self.tool in LINE_TOOLS:
            a, b = self._scene_to_doc(idx, start), self._scene_to_doc(idx, end)
            if abs(a - b) > 3:
                self.toolAction.emit(self.tool, idx, (a, b))
            return
        rect_scene = QRectF(start, end).normalized()
        small = rect_scene.width() < 4 and rect_scene.height() < 4
        rect = self._scene_rect_to_doc(idx, rect_scene)
        if small:
            # Clic semplice: rettangolo predefinito attorno al punto
            p = self._scene_to_doc(idx, start)
            if self.tool in (TEXT,):
                rect = pymupdf.Rect(p.x, p.y, p.x + 200, p.y + 40)
            elif self.tool in (IMAGE, SIGNATURE):
                rect = pymupdf.Rect(p.x, p.y, p.x + 180, p.y + 70)
            elif self.tool in (RECT, ELLIPSE):
                rect = pymupdf.Rect(p.x - 30, p.y - 20, p.x + 30, p.y + 20)
            elif self.tool in (HIGHLIGHT, UNDERLINE, STRIKEOUT, SELECT):
                rect = pymupdf.Rect(p.x - 1, p.y - 1, p.x + 1, p.y + 1)
            else:
                return
        self.toolAction.emit(self.tool, idx, rect)

    def _commit_ink(self) -> None:
        if self._ink_item is not None:
            self.scene().removeItem(self._ink_item)
            self._ink_item = None
        strokes = [s for s in self._ink_strokes if len(s) > 1]
        page = self._ink_page
        self._ink_strokes = []
        self._ink_page = -1
        if strokes and self.document and 0 <= page < self.document.page_count:
            self.toolAction.emit(INK, page, strokes)

    def mouseDoubleClickEvent(self, event) -> None:
        if self.document and self.tool in (HAND, SELECT) and event.button() == Qt.LeftButton:
            sp = self.mapToScene(event.position().toPoint())
            if self.field_at(sp) is None and self._over_text(sp):
                hit = self._text_hit(sp, nearest=False)
                if hit is not None:
                    page, i = hit
                    self.set_selection(page, *self.page_text(page).word_at(i))  # doppio clic: parola
                    self._last_dbl = (event.timestamp(), event.position())
                    self._sel_drag = None
                    return
        if self.document and self.tool == HAND and event.button() == Qt.LeftButton:
            sp = self.mapToScene(event.position().toPoint())
            idx = self._page_at(sp)
            if idx >= 0:
                annot = self.document.annotation_at(idx, self._scene_to_doc(idx, sp))
                if annot is not None:
                    self.toolAction.emit("edit_annot", idx, annot)
                    return
        super().mouseDoubleClickEvent(event)
