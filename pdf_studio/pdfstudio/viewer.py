"""Visualizzatore a scorrimento continuo con strumenti di modifica."""
from __future__ import annotations

import pymupdf
from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QCursor, QImage, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (QGraphicsPathItem, QGraphicsPixmapItem, QGraphicsRectItem,
                               QGraphicsScene, QGraphicsView)

from .document import PdfDocument

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


class PageView(QGraphicsView):
    """Mostra tutte le pagine in colonna e traduce i gesti in operazioni sul documento."""

    pageChanged = Signal(int)
    zoomChanged = Signal(float)
    # (strumento, indice pagina, dati) — gestiti dalla finestra principale
    toolAction = Signal(str, int, object)
    documentEdited = Signal()

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
        self.verticalScrollBar().valueChanged.connect(self._on_scroll)
        self.setAcceptDrops(False)

    # ------------------------------------------------------------------ setup
    def set_document(self, document: PdfDocument | None, keep_position: bool = False) -> None:
        pos = self.verticalScrollBar().value() if keep_position else 0
        page = self._current_page if keep_position else 0
        self._commit_ink()
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
    def set_tool(self, tool: str) -> None:
        self._commit_ink()
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
        if not self.document or event.button() != Qt.LeftButton or self.tool == HAND:
            if self.tool == HAND and self.document and event.button() == Qt.LeftButton:
                # Clic su un campo modulo con la mano: compila il campo
                sp = self.mapToScene(event.position().toPoint())
                idx = self._page_at(sp)
                if idx >= 0:
                    w = self.document.widget_at(idx, self._scene_to_doc(idx, sp))
                    if w is not None:
                        self.toolAction.emit("form", idx, w)
                        return
            super().mousePressEvent(event)
            return
        sp = self.mapToScene(event.position().toPoint())
        idx = self._page_at(sp)
        if idx < 0:
            return
        if self.tool in CLICK_TOOLS:
            self.toolAction.emit(self.tool, idx, self._scene_to_doc(idx, sp))
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
        if self.document and self.tool == HAND and event.button() == Qt.LeftButton:
            sp = self.mapToScene(event.position().toPoint())
            idx = self._page_at(sp)
            if idx >= 0:
                annot = self.document.annotation_at(idx, self._scene_to_doc(idx, sp))
                if annot is not None:
                    self.toolAction.emit("edit_annot", idx, annot)
                    return
        super().mouseDoubleClickEvent(event)
