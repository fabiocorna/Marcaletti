"""Pannello miniature: navigazione, selezione multipla e riordino a trascinamento."""
from __future__ import annotations

import pymupdf
from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import QAbstractItemView, QListView, QListWidget, QListWidgetItem

from .document import PdfDocument
from .viewer import pixmap_to_qimage

THUMB_W = 120


class ThumbnailList(QListWidget):
    pageClicked = Signal(int)
    orderChanged = Signal(list)  # nuovo ordine (indici originali)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setViewMode(QListView.IconMode)
        self.setFlow(QListView.TopToBottom)
        self.setWrapping(False)
        self.setResizeMode(QListView.Adjust)
        self.setMovement(QListView.Snap)
        self.setIconSize(QSize(THUMB_W, int(THUMB_W * 1.42)))
        self.setSpacing(6)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setUniformItemSizes(False)
        self.setMinimumWidth(THUMB_W + 50)
        self.setStyleSheet("QListWidget { background: #3c3f41; color: white; }"
                           "QListWidget::item:selected { background: #2f65ca; border-radius: 4px; }")
        self.document: PdfDocument | None = None
        self._done: set[int] = set()
        self._timer = QTimer(self, singleShot=True, interval=40, timeout=self._render_visible)
        self.verticalScrollBar().valueChanged.connect(lambda: self._timer.start())
        self.itemClicked.connect(lambda it: self.pageClicked.emit(self.row(it)))

    def set_document(self, document: PdfDocument | None) -> None:
        self.document = document
        self.clear()
        self._done.clear()
        if not document:
            return
        for i in range(document.page_count):
            r = document.page(i).rect
            h = int(THUMB_W * r.height / r.width) if r.width else THUMB_W
            placeholder = QPixmap(THUMB_W, h)
            placeholder.fill(QColor("white"))
            item = QListWidgetItem(QIcon(placeholder), str(i + 1))
            item.setData(Qt.UserRole, i)
            item.setTextAlignment(Qt.AlignHCenter)
            item.setSizeHint(QSize(THUMB_W + 20, h + 30))
            self.addItem(item)
        self._timer.start()

    def refresh(self, index: int | None = None) -> None:
        if index is None:
            self.set_document(self.document)
        else:
            self._done.discard(index)
            self._timer.start()

    def showEvent(self, e) -> None:
        super().showEvent(e)
        self._timer.start()

    def resizeEvent(self, e) -> None:
        super().resizeEvent(e)
        self._timer.start()

    def _render_visible(self) -> None:
        if not self.document:
            return
        vp = self.viewport().rect()
        for row in range(self.count()):
            item = self.item(row)
            if not self.visualItemRect(item).intersects(vp.adjusted(0, -400, 0, 400)):
                continue
            orig = item.data(Qt.UserRole)
            if orig in self._done or orig >= self.document.page_count:
                continue
            page = self.document.page(orig)
            zoom = THUMB_W / page.rect.width
            pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), annots=True, alpha=False)
            item.setIcon(QIcon(QPixmap.fromImage(pixmap_to_qimage(pix))))
            self._done.add(orig)

    def select_page(self, index: int) -> None:
        if 0 <= index < self.count():
            self.blockSignals(True)
            self.setCurrentRow(index)
            self.blockSignals(False)
            self.scrollToItem(self.item(index))

    def selected_pages(self) -> list[int]:
        rows = sorted(self.row(it) for it in self.selectedItems())
        return rows or ([self.currentRow()] if self.currentRow() >= 0 else [])

    def dropEvent(self, event) -> None:
        super().dropEvent(event)
        order = [self.item(r).data(Qt.UserRole) for r in range(self.count())]
        if order != sorted(order):
            self.orderChanged.emit(order)
